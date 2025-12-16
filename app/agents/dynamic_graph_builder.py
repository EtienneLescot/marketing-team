#!/usr/bin/env python3
"""
Dynamic, configuration-driven graph builder for agent workflows.
This module creates hierarchical workflows dynamically from YAML configuration,
supporting multiple config files and configurable entry points.
"""

import asyncio
from typing import Literal, List, Optional, Dict, Any, Set, TypedDict
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from pathlib import Path
import json

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from langgraph.errors import GraphInterrupt
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from app.models.state_models import EnhancedMarketingState, TeamState
from app.utils.config_loader import ConfigurationLoader, inject_managed_agents_into_prompts
from app.utils.message_utils import (
    extract_original_task,
    create_agent_response,
    sanitize_messages_for_agent,
    detect_message_nesting,
    reset_message_nesting
)
from app.monitoring.basic_monitor import (
    get_global_monitor,
    TimerContext,
    monitor_agent_call
)


class GraphType(Enum):
    """Type of graph to build based on entry point"""
    SINGLE_AGENT = "single_agent"
    TEAM_SUPERVISOR = "team_supervisor"
    FULL_HIERARCHY = "full_hierarchy"


class AgentType(Enum):
    """Type of agent based on configuration"""
    SUPERVISOR = "supervisor"
    WORKER = "worker"


@dataclass
class GraphBuildState:
    """State for recursive graph building"""
    builder: StateGraph
    node_registry: Dict[str, Any]  # agent_name -> node_function
    edge_registry: Dict[str, List[str]]  # from_node -> [to_nodes]
    processed_agents: Set[str]  # Track processed agents to avoid cycles
    parent_map: Dict[str, str]  # child_agent -> parent_supervisor


class SingleAgentState(TypedDict):
    """State for single agent workflows"""
    messages: List[BaseMessage]
    task: str
    result: Optional[str]
    status: str  # "pending", "processing", "completed", "error"


class DynamicGraphBuilder:
    """Builds hierarchical agent workflows dynamically from YAML configuration"""
    
    def __init__(self, config_path: str = "config/agents.yaml"):
        """
        Initialize with configuration file path.
        
        Args:
            config_path: Path to YAML configuration file. Can be:
                - Relative path: "config/agents.yaml"
                - Absolute path: "/path/to/config.yaml"
                - Special name: "research_team" (resolves to config/research_team.yaml)
        """
        self.config_path = self._resolve_config_path(config_path)
        self.config_loader = ConfigurationLoader(self.config_path)
        self.agent_config_manager = self.config_loader.load_agents()
        
        # Inject managed agents into prompts
        inject_managed_agents_into_prompts(self.agent_config_manager)
        
        # Initialize tool registry
        from app.utils.config_loader import GLOBAL_TOOL_REGISTRY
        self.tool_registry = GLOBAL_TOOL_REGISTRY
        
        # Cache for created nodes
        self._node_cache: Dict[str, Any] = {}
        
        # Cache for agent types
        self._agent_type_cache: Dict[str, AgentType] = {}
    
    def _resolve_config_path(self, config_path: str) -> str:
        """Resolve configuration file path with fallback logic"""
        path = Path(config_path)
        
        # If absolute path exists, use it
        if path.is_absolute() and path.exists():
            return str(path)
        
        # Try relative to cwd
        if path.exists():
            return str(path)
        
        # Try in config/ directory
        config_dir_path = Path("config") / path
        if config_dir_path.exists():
            return str(config_dir_path)
        
        # Try with .yaml extension
        if not path.suffix:
            yaml_path = Path(str(path) + ".yaml")
            if yaml_path.exists():
                return str(yaml_path)
            
            config_yaml_path = Path("config") / yaml_path
            if config_yaml_path.exists():
                return str(config_yaml_path)
        
        # Not found
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    def get_agent_config(self, agent_name: str):
        """Get agent configuration by name"""
        return self.agent_config_manager.get_agent_config(agent_name)
    
    def _get_agent_type(self, agent_name: str) -> AgentType:
        """Determine if agent is supervisor or worker"""
        if agent_name in self._agent_type_cache:
            return self._agent_type_cache[agent_name]
        
        config = self.get_agent_config(agent_name)
        if not config:
            raise ValueError(f"Agent '{agent_name}' not found in configuration")
        
        if config.managed_agents and len(config.managed_agents) > 0:
            agent_type = AgentType.SUPERVISOR
        else:
            agent_type = AgentType.WORKER
        
        self._agent_type_cache[agent_name] = agent_type
        return agent_type
    
    def _determine_graph_type(self, entry_point: str) -> GraphType:
        """Determine what type of graph to build based on entry point"""
        agent_type = self._get_agent_type(entry_point)
        
        if agent_type == AgentType.WORKER:
            return GraphType.SINGLE_AGENT
        elif entry_point == "main_supervisor":
            return GraphType.FULL_HIERARCHY
        else:
            return GraphType.TEAM_SUPERVISOR
    
    def build_graph(self, entry_point: str = "main_supervisor", 
                   checkpointer=None) -> StateGraph:
        """
        Build graph recursively starting from entry_point.
        
        Args:
            entry_point: Name of agent to start building from
            checkpointer: Optional checkpointer for compiled graph
            
        Returns:
            Compiled StateGraph
        """
        # Validate entry point
        if not self.validate_entry_point(entry_point):
            raise ValueError(f"Entry point '{entry_point}' not found in configuration")
        
        # Determine graph type
        graph_type = self._determine_graph_type(entry_point)
        
        # Build appropriate graph
        if graph_type == GraphType.SINGLE_AGENT:
            return self._build_single_agent_graph(entry_point, checkpointer)
        elif graph_type == GraphType.TEAM_SUPERVISOR:
            return self._build_team_graph(entry_point, checkpointer)
        else:  # GraphType.FULL_HIERARCHY
            return self._build_full_hierarchy(entry_point, checkpointer)
    
    def _build_single_agent_graph(self, agent_name: str, checkpointer=None):
        """Build graph for a single worker agent"""
        builder = StateGraph(SingleAgentState)
        
        # Create worker node
        worker_node = self._create_worker_node(agent_name)
        builder.add_node(agent_name, worker_node)
        
        # Simple linear flow: START -> worker -> END
        builder.add_edge(START, agent_name)
        builder.add_edge(agent_name, END)
        
        return builder.compile(checkpointer=checkpointer)
    
    def _build_team_graph(self, supervisor_name: str, checkpointer=None):
        """Build graph for a team supervisor and its managed agents"""
        builder = StateGraph(TeamState)
        
        # Create supervisor node
        supervisor_config = self.get_agent_config(supervisor_name)
        supervisor_node = self._create_supervisor_node(
            supervisor_name,
            supervisor_config.managed_agents
        )
        builder.add_node(supervisor_name, supervisor_node)
        
        # Add worker nodes with supervisor context
        for worker_name in supervisor_config.managed_agents:
            worker_node = self._create_worker_node(worker_name, supervisor_name)
            builder.add_node(worker_name, worker_node)
        
        # Start with supervisor
        builder.add_edge(START, supervisor_name)
        
        # Add conditional routing based on supervisor's Command
        # The supervisor node returns Command(goto=worker_name) or Command(goto=END)
        # LangGraph will handle the routing automatically
        
        return builder.compile(checkpointer=checkpointer)
    
    def _build_full_hierarchy(self, entry_point: str, checkpointer=None):
        """Build complete hierarchical graph recursively"""
        # Initialize build state
        state = GraphBuildState(
            builder=StateGraph(EnhancedMarketingState),
            node_registry={},
            edge_registry={},
            processed_agents=set(),
            parent_map={}
        )
        
        # Recursively build from entry point
        self._build_recursive(entry_point, state, None)
        
        # Add START edge to entry point
        state.builder.add_edge(START, entry_point)
        
        # Add conditional edges for completion
        self._add_conditional_edges(state)
        
        return state.builder.compile(checkpointer=checkpointer)
    
    def _build_recursive(self, agent_name: str, state: GraphBuildState, parent: Optional[str]):
        """Recursively build graph for agent"""
        # Check for cycles
        if agent_name in state.processed_agents:
            return agent_name
        
        state.processed_agents.add(agent_name)
        
        # Store parent relationship
        if parent:
            state.parent_map[agent_name] = parent
        
        # Get agent type
        agent_type = self._get_agent_type(agent_name)
        
        if agent_type == AgentType.WORKER:
            # Create worker node
            node_func = self._create_worker_node(agent_name)
            state.builder.add_node(agent_name, node_func)
            state.node_registry[agent_name] = node_func
            return agent_name
            
        else:  # Supervisor
            # Get supervisor config
            supervisor_config = self.get_agent_config(agent_name)
            
            # Create supervisor node
            supervisor_node_func = self._create_supervisor_node(
                agent_name, 
                supervisor_config.managed_agents
            )
            state.builder.add_node(agent_name, supervisor_node_func)
            state.node_registry[agent_name] = supervisor_node_func
            
            # Process each managed agent
            for managed_agent in supervisor_config.managed_agents:
                # Recursively build managed agent
                managed_node_name = self._build_recursive(managed_agent, state, agent_name)
                
                # Add edges: supervisor <-> managed_agent
                state.builder.add_edge(agent_name, managed_agent)
                state.builder.add_edge(managed_agent, agent_name)
                
                # Register edges
                state.edge_registry.setdefault(agent_name, []).append(managed_agent)
                state.edge_registry.setdefault(managed_agent, []).append(agent_name)
            
            return agent_name
    
    def _add_conditional_edges(self, state: GraphBuildState):
        """Add conditional edges for team completion"""
        # For now, use simple completion logic
        # In a more advanced implementation, this would handle
        # team_status-based routing back to parent supervisors
        
        # This is a simplified version - the actual implementation
        # would need to track parent-child relationships and add
        # appropriate conditional edges
        
        pass
    
    def _create_supervisor_node(self, supervisor_name: str, managed_agents: List[str]):
        """Create supervisor node function with dynamic routing"""
        # Check cache first
        if supervisor_name in self._node_cache:
            return self._node_cache[supervisor_name]
        
        @monitor_agent_call(supervisor_name)
        async def supervisor_node(state: TeamState) -> Command:
            # Check iteration limit
            if state.get("iteration_count", 0) >= 3:
                return Command(goto=END, update={"team_status": "completed"})
            
            try:
                # Get supervisor config
                supervisor_config = self.get_agent_config(supervisor_name)
                
                # Create routing prompt with available workers
                routing_prompt = f"""{supervisor_config.system_prompt}

Available agents: {', '.join(managed_agents)}

Current task: {state['messages'][-1].content if state['messages'] else 'No task provided'}

Please route to the most appropriate agent or FINISH if complete.

Output format: {{"next_node": "agent_name", "reasoning": "explanation", "confidence": 0.95, "should_terminate": false}}"""
                
                # Get LLM model
                llm = supervisor_config.get_model()
                
                # Get routing decision with timeout
                try:
                    response = await asyncio.wait_for(llm.ainvoke([{"role": "user", "content": routing_prompt}]), timeout=30.0)
                    # Parse JSON response
                    decision = json.loads(response.content)
                except asyncio.TimeoutError:
                    print(f"{supervisor_name}: LLM timeout, using fallback routing")
                    return self._fallback_routing(state, managed_agents)
                except Exception as e:
                    print(f"{supervisor_name}: LLM error: {e}, using fallback routing")
                    return self._fallback_routing(state, managed_agents)
                
                # Log routing decision
                monitor = get_global_monitor()
                monitor.record_routing_decision(
                    supervisor_name=supervisor_name,
                    decision=decision,
                    duration_ms=0
                )
                
                # Update state
                update_data = {
                    "iteration_count": state.get("iteration_count", 0) + 1,
                    "current_agent": decision["next_node"] if decision["next_node"] != "FINISH" else None,
                    "routing_decision": decision
                }
                
                # Add instructions if present
                if decision.get("instructions"):
                    update_data["messages"] = state.get("messages", []) + [HumanMessage(content=decision["instructions"], name="supervisor_instructions")]
                
                if decision.get("should_terminate", False) or decision["next_node"] == "FINISH":
                    update_data["team_status"] = "completed"
                    return Command(goto=END, update=update_data)
                
                return Command(goto=decision["next_node"], update=update_data)
                
            except Exception as e:
                # Fallback to keyword routing
                print(f"{supervisor_name} routing failed: {e}")
                return self._fallback_routing(state, managed_agents)
        
        # Cache and return
        self._node_cache[supervisor_name] = supervisor_node
        return supervisor_node
    
    def _create_worker_node(self, worker_name: str, supervisor_name: Optional[str] = None):
        """Create worker node function with supervisor tracking"""
        # Check cache first (with supervisor context)
        cache_key = f"{worker_name}:{supervisor_name}" if supervisor_name else worker_name
        if cache_key in self._node_cache:
            return self._node_cache[cache_key]
        
        @monitor_agent_call(worker_name)
        async def worker_node(state: TeamState) -> Command:
            """Worker agent with tools"""
            try:
                # Get worker config
                worker_config = self.get_agent_config(worker_name)
                
                # Extract task - use original user task, not last message
                from app.utils.message_utils import extract_original_task
                original_task = extract_original_task(state.get("messages", [])) or "No task provided"
                context = "\n".join([f"{msg.name}: {msg.content}" for msg in state.get("messages", []) if hasattr(msg, "name") and msg.name not in ["user", "system"]])
                
                # Get LLM model
                llm = worker_config.get_model()
                
                # Create prompt
                prompt = f"""{worker_config.system_prompt}

Task: {original_task}

Context:
{context}

Please complete the task."""
                
                # Record prompt
                monitor = get_global_monitor()
                monitor.record_agent_prompt(worker_name, prompt)
                
                # Execute LLM call with timeout
                try:
                    response = await asyncio.wait_for(llm.ainvoke([{"role": "user", "content": prompt}]), timeout=30.0)
                    result = response.content
                except asyncio.TimeoutError:
                    result = f"LLM call timed out after 30 seconds. Please check API connectivity."
                    print(f"{worker_name}: LLM timeout")
                except Exception as e:
                    result = f"LLM call failed: {str(e)[:200]}"
                    print(f"{worker_name}: LLM error: {e}")
                
                # Handle tools if worker has them
                if worker_config.tools:
                    result = await self._handle_worker_tools(worker_name, worker_config, result, original_task)
                
                # Record output
                monitor.record_agent_output(worker_name, result)
                
                # Create response
                response_messages = create_agent_response(
                    content=result,
                    agent_name=worker_name,
                    include_original_task=True,
                    original_task=original_task
                )
                
                # Determine which supervisor to return to
                # Use the supervisor_name parameter if provided, otherwise try to get from state
                target_supervisor = supervisor_name or state.get("current_supervisor", "supervisor")
                
                return Command(
                    goto=target_supervisor,
                    update={
                        "messages": response_messages,
                        "task_completed": True,
                        "agent_executed": worker_name,
                        "last_worker": worker_name
                    }
                )
                
            except GraphInterrupt:
                # Re-raise GraphInterrupt to let LangGraph handle it
                raise
            except Exception as e:
                print(f"{worker_name} failed: {e}")
                error_response = f"{worker_name} failed: {str(e)[:200]}"
                target_supervisor = supervisor_name or state.get("current_supervisor", "supervisor")
                return Command(
                    goto=target_supervisor,
                    update={
                        "messages": [AIMessage(content=error_response, name=worker_name)],
                        "task_completed": False,
                        "error": str(e),
                        "last_worker": worker_name
                    }
                )
        
        # Cache and return
        self._node_cache[cache_key] = worker_node
        return worker_node
    
    async def _handle_worker_tools(self, worker_name: str, worker_config, result: str, original_task: str) -> str:
        """Handle tool execution for workers"""
        # For LinkedIn posting
        if worker_name == "linkedin_manager" and worker_config.tools:
            # Check if linkedin_post tool is in the tools list
            linkedin_tools = [tool for tool in worker_config.tools if hasattr(tool, 'metadata') and tool.metadata.name == "linkedin_post"]
            if linkedin_tools:
                # Extract content to publish
                content_to_publish = result
                
                # Create approval request
                approval_request = f"Please review this LinkedIn post:\n\n{content_to_publish}\n\nType 'approved' to publish or provide feedback."
                
                # INTERRUPT FOR HUMAN APPROVAL
                monitor = get_global_monitor()
                monitor.record_event(agent_name="linkedin_manager", event_type="waiting_for_approval", data={"content": content_to_publish})
                
                user_feedback = interrupt(approval_request)
                
                if str(user_feedback).lower().strip() == "approved":
                    # Use the LinkedIn Tool
                    tool = self.tool_registry.get_tool("linkedin_post")
                    
                    if tool:
                        print(f"DEBUG: LinkedIn tool found, executing with content length: {len(content_to_publish)}")
                        try:
                            # Execute tool with company URN for company page posting
                            result = await tool.execute(content_to_publish)
                            print(f"DEBUG: LinkedIn tool executed successfully: {result[:100]}")
                        except Exception as e:
                            result = f"❌ Publishing exception: {str(e)}"
                            print(f"DEBUG: LinkedIn tool exception: {e}")
                    else:
                        result = "❌ Error: LinkedIn tool not found in registry."
                        print("DEBUG: LinkedIn tool not found in registry")
                else:
                    result = f"❌ Publication rejected. Feedback: {user_feedback}"
                    print(f"DEBUG: Publication rejected: {user_feedback}")
        
        # Add handling for other tools here
        elif worker_name == "web_researcher" and worker_config.tools:
            # Check if tavily_search tool is in the tools list
            tavily_tools = [tool for tool in worker_config.tools if hasattr(tool, 'metadata') and tool.metadata.name == "tavily_search"]
            if tavily_tools:
                # For web researcher with tavily search
                tool = self.tool_registry.get_tool("tavily_search")
                if tool:
                    try:
                        search_result = await tool.execute(original_task)
                        result = f"{result}\n\nSearch Results:\n{search_result}"
                    except Exception as e:
                        result = f"{result}\n\n❌ Search failed: {e}"
        
        return result
    
    def _fallback_routing(self, state: TeamState, worker_names: List[str]) -> Command:
        """Fallback routing for supervisors"""
        if state.get("iteration_count", 0) >= 3:
            return Command(goto=END, update={"team_status": "completed"})
        
        last_message = state["messages"][-1].content.lower() if state["messages"] else ""
        
        # Simple keyword routing
        if "data" in last_message or "analytics" in last_message:
            goto = worker_names[1] if len(worker_names) > 1 else worker_names[0]  # data_analyst
        else:
            goto = worker_names[0]  # web_researcher
        
        return Command(
            goto=goto,
            update={"iteration_count": state.get("iteration_count", 0) + 1}
        )
    
    def validate_entry_point(self, entry_point: str) -> bool:
        """Check if entry point is valid"""
        return entry_point in self.agent_config_manager.agents
    
    def list_available_entry_points(self) -> List[Dict]:
        """List all possible entry points with their types"""
        entry_points = []
        for name, config in self.agent_config_manager.agents.items():
            agent_type = self._get_agent_type(name)
            entry_points.append({
                "name": name,
                "type": agent_type.value,
                "description": f"{config.role} agent",
                "managed_agents": config.managed_agents or [],
                "has_tools": bool(config.tool_names),
                "require_approval": config.require_approval
            })
        return entry_points
    
    def validate_config_for_graph(self) -> List[str]:
        """Validate configuration for graph building"""
        errors = []
        
        # Check for cycles
        errors.extend(self._detect_cycles())
        
        # Check for missing managed agents
        errors.extend(self._check_missing_managed_agents())
        
        # Check for missing tools
        errors.extend(self._check_missing_tools())
        
        return errors
    
    def _detect_cycles(self) -> List[str]:
        """Detect cycles in agent hierarchy using DFS"""
        errors = []
        visited = set()
        recursion_stack = set()
        
        def dfs(agent_name: str, path: List[str]):
            if agent_name in recursion_stack:
                cycle = " -> ".join(path + [agent_name])
                errors.append(f"Cycle detected: {cycle}")
                return
            
            if agent_name in visited:
                return
            
            visited.add(agent_name)
            recursion_stack.add(agent_name)
            
            config = self.get_agent_config(agent_name)
            if config and config.managed_agents:
                for managed in config.managed_agents:
                    dfs(managed, path + [agent_name])
            
            recursion_stack.remove(agent_name)
        
        # Start DFS from all agents
        for agent_name in self.agent_config_manager.agents.keys():
            if agent_name not in visited:
                dfs(agent_name, [])
        
        return errors
    
    def _check_missing_managed_agents(self) -> List[str]:
        """Check for missing managed agents references"""
        errors = []
        all_agents = set(self.agent_config_manager.agents.keys())
        
        for agent_name, config in self.agent_config_manager.agents.items():
            if config.managed_agents:
                for managed in config.managed_agents:
                    if managed not in all_agents:
                        errors.append(f"Agent '{agent_name}' references unknown managed agent '{managed}'")
        
        return errors
    
    def _check_missing_tools(self) -> List[str]:
        """Check for missing tool references"""
        errors = []
        
        for agent_name, config in self.agent_config_manager.agents.items():
            if config.tool_names:
                for tool_name in config.tool_names:
                    if not self.tool_registry.get_tool(tool_name):
                        errors.append(f"Agent '{agent_name}' references unknown tool '{tool_name}'")
        
        return errors
    
    @classmethod
    def from_default(cls):
        """Create builder with default configuration"""
        return cls("config/agents.yaml")
    
    @classmethod
    def from_research_team(cls):
        """Create builder with research team configuration"""
        return cls("config/research_team.yaml")
    
    @classmethod
    def from_content_team(cls):
        """Create builder with content team configuration"""
        return cls("config/content_team.yaml")
    
    @classmethod
    def from_config_name(cls, name: str):
        """Create builder from configuration name"""
        return cls(name)


def create_dynamic_workflow(config_path: str = "config/agents.yaml",
                           entry_point: str = "main_supervisor",
                           checkpointer=None) -> StateGraph:
    """
    Create workflow using dynamic graph builder.
    
    Args:
        config_path: Path to configuration file
        entry_point: Agent to start from
        checkpointer: Optional checkpointer
        
    Returns:
        Compiled StateGraph
    """
    builder = DynamicGraphBuilder(config_path)
    return builder.build_graph(entry_point, checkpointer)


# Backward compatibility wrapper
def create_config_driven_workflow(checkpointer=None) -> StateGraph:
    """Legacy function - uses new builder with default entry point"""
    builder = DynamicGraphBuilder()
    return builder.build_graph("main_supervisor", checkpointer)