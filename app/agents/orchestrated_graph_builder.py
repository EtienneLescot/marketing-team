#!/usr/bin/env python3
"""
Orchestrated graph builder with dependency resolution and sequential execution.
Simplified version focusing on core functionality.
"""

import asyncio
from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from pathlib import Path
import json

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage, AIMessage

from app.models.orchestration_state import OrchestrationState, DependencyGraph, ExecutionPlan
from app.utils.config_loader import ConfigurationLoader, inject_managed_agents_into_prompts
from app.utils.message_utils import extract_original_task


class GraphType(Enum):
    """Type of graph to build based on entry point"""
    SINGLE_AGENT = "single_agent"
    TEAM_SUPERVISOR = "team_supervisor"
    ORCHESTRATED = "orchestrated"


class AgentType(Enum):
    """Type of agent based on configuration"""
    SUPERVISOR = "supervisor"
    WORKER = "worker"


@dataclass
class GraphBuildState:
    """State for recursive graph building"""
    builder: StateGraph
    node_registry: Dict[str, Any]
    processed_agents: Set[str]


class OrchestratedGraphBuilder:
    """Builds orchestrated agent workflows with dependency resolution"""
    
    def __init__(self, config_path: str = "config/agents.yaml"):
        self.config_path = self._resolve_config_path(config_path)
        self.config_loader = ConfigurationLoader(self.config_path)
        self.agent_config_manager = self.config_loader.load_agents()
        
        inject_managed_agents_into_prompts(self.agent_config_manager)
        
        from app.utils.config_loader import GLOBAL_TOOL_REGISTRY
        self.tool_registry = GLOBAL_TOOL_REGISTRY
        
        self.dependency_graph = DependencyGraph(self.agent_config_manager.agents)
        self._node_cache: Dict[str, Any] = {}
        self._agent_type_cache: Dict[str, AgentType] = {}
    
    def _resolve_config_path(self, config_path: str) -> str:
        """Resolve configuration file path with fallback logic"""
        path = Path(config_path)
        
        if path.is_absolute() and path.exists():
            return str(path)
        
        if path.exists():
            return str(path)
        
        config_dir_path = Path("config") / path
        if config_dir_path.exists():
            return str(config_dir_path)
        
        if not path.suffix:
            yaml_path = Path(str(path) + ".yaml")
            if yaml_path.exists():
                return str(yaml_path)
            
            config_yaml_path = Path("config") / yaml_path
            if config_yaml_path.exists():
                return str(config_yaml_path)
        
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
    
    def validate_entry_point(self, entry_point: str) -> bool:
        """Check if entry point is valid"""
        return entry_point in self.agent_config_manager.agents
    
    def validate_config_for_graph(self) -> List[str]:
        """Validate configuration for graph building"""
        errors = []
        
        # Check for cycles in dependency graph
        try:
            order = self.dependency_graph.get_topological_order()
            if not order:
                errors.append("No agents found in configuration")
        except ValueError as e:
            errors.append(f"Cycle detected in dependency graph: {e}")
        
        # Check that all agents have valid configurations
        for agent_name in self.agent_config_manager.agents:
            config = self.get_agent_config(agent_name)
            if not config:
                errors.append(f"Agent '{agent_name}' has no configuration")
            elif not config.system_prompt:
                errors.append(f"Agent '{agent_name}' has no system prompt")
        
        return errors
    
    def list_available_entry_points(self) -> List[Dict[str, Any]]:
        """List available entry points with metadata"""
        entry_points = []
        
        for agent_name in self.agent_config_manager.agents:
            config = self.get_agent_config(agent_name)
            if not config:
                continue
                
            entry_points.append({
                "name": agent_name,
                "type": "supervisor" if config.managed_agents else "worker",
                "managed_agents": config.managed_agents or [],
                "has_tools": bool(config.tools),
                "require_approval": config.require_approval or False
            })
        
        return entry_points
    
    def build_graph(self, entry_point: str = "main_supervisor", 
                   checkpointer=None) -> StateGraph:
        """
        Build graph recursively starting from entry_point.
        """
        if not self.validate_entry_point(entry_point):
            raise ValueError(f"Entry point '{entry_point}' not found in configuration")
        
        agent_type = self._get_agent_type(entry_point)
        
        if agent_type == AgentType.WORKER:
            return self._build_single_agent_graph(entry_point, checkpointer)
        elif entry_point == "main_supervisor":
            return self._build_orchestrated_graph(entry_point, checkpointer)
        else:
            return self._build_team_graph(entry_point, checkpointer)
    
    def _build_single_agent_graph(self, agent_name: str, checkpointer=None):
        """Build graph for a single worker agent"""
        builder = StateGraph(OrchestrationState)
        
        worker_node = self._create_worker_node(agent_name)
        builder.add_node(agent_name, worker_node)
        
        # Add human approval node if agent requires approval
        agent_config = self.get_agent_config(agent_name)
        if agent_config and agent_config.require_approval and agent_config.tools:
            human_approval_node = self._create_human_approval_node()
            builder.add_node("human_approval", human_approval_node)
            builder.add_edge(agent_name, "human_approval")
            builder.add_edge("human_approval", END)
        else:
            builder.add_edge(agent_name, END)
        
        builder.add_edge(START, agent_name)
        
        return builder.compile(checkpointer=checkpointer)
    
    def _build_team_graph(self, supervisor_name: str, checkpointer=None):
        """Build graph for a team supervisor and its managed agents"""
        builder = StateGraph(OrchestrationState)
        
        supervisor_config = self.get_agent_config(supervisor_name)
        supervisor_node = self._create_supervisor_node(
            supervisor_name,
            supervisor_config.managed_agents
        )
        builder.add_node(supervisor_name, supervisor_node)
        
        for worker_name in supervisor_config.managed_agents:
            worker_node = self._create_worker_node(worker_name, supervisor_name)
            builder.add_node(worker_name, worker_node)
        
        builder.add_edge(START, supervisor_name)
        
        return builder.compile(checkpointer=checkpointer)
    
    def _build_orchestrated_graph(self, entry_point: str, checkpointer=None):
        """Build orchestrated graph with dependency resolution"""
        builder = StateGraph(OrchestrationState)
        
        # Create task analysis node
        task_analysis_node = self._create_task_analysis_node(entry_point)
        builder.add_node("task_analysis", task_analysis_node)
        
        # Get execution order and filter out supervisors (only workers execute in orchestrated mode)
        execution_order = self.dependency_graph.get_topological_order()
        worker_execution_order = [
            agent_name for agent_name in execution_order
            if self._get_agent_type(agent_name) == AgentType.WORKER
        ]
        
        # Create agent execution nodes for workers only
        for agent_name in worker_execution_order:
            node_func = self._create_worker_node(agent_name)
            builder.add_node(agent_name, node_func)
        
        # Create human approval node
        human_approval_node = self._create_human_approval_node()
        builder.add_node("human_approval", human_approval_node)
        
        # Create result synthesis node
        synthesis_node = self._create_result_synthesis_node(entry_point)
        builder.add_node("result_synthesis", synthesis_node)
        
        # Build edges
        builder.add_edge(START, "task_analysis")
        
        if worker_execution_order:
            builder.add_edge("task_analysis", worker_execution_order[0])
            
            for i in range(len(worker_execution_order) - 1):
                current = worker_execution_order[i]
                next_agent = worker_execution_order[i + 1]
                builder.add_edge(current, next_agent)
            
            last_agent = worker_execution_order[-1]
            builder.add_edge(last_agent, "result_synthesis")
        else:
            builder.add_edge("task_analysis", "result_synthesis")
        
        # Human approval can go to result synthesis or back to the agent
        builder.add_edge("human_approval", "result_synthesis")
        
        builder.add_edge("result_synthesis", END)
        
        return builder.compile(checkpointer=checkpointer)
    
    def _create_task_analysis_node(self, entry_point: str):
        """Create node for task analysis and planning"""
        async def task_analysis_node(state: Dict[str, Any]) -> Command:
            """Analyze task and create execution plan"""
            try:
                original_task = extract_original_task(state.get("messages", []))
                if not original_task:
                    original_task = state.get("original_task", "No task provided")
                
                # Get execution order from dependency graph and filter out supervisors
                execution_order = self.dependency_graph.get_topological_order()
                worker_execution_order = [
                    agent_name for agent_name in execution_order
                    if self._get_agent_type(agent_name) == AgentType.WORKER
                ]
                
                # Create simple execution plan
                execution_plan = ExecutionPlan(
                    task_id=f"task_{datetime.now().timestamp()}",
                    original_task=original_task,
                    subtasks=[
                        {
                            "description": f"Execute {agent}'s part of: {original_task}",
                            "assigned_to": agent,
                            "dependencies": [] if i == 0 else [worker_execution_order[i-1]]
                        }
                        for i, agent in enumerate(worker_execution_order)
                    ],
                    execution_order=worker_execution_order,
                    current_step=0,
                    completed_steps=[],
                    agent_results={}
                )
                
                # Record task analysis in monitoring
                try:
                    from app.monitoring.streaming_monitor import get_global_streaming_monitor
                    monitor = get_global_streaming_monitor()
                    monitor.record_agent_output("task_analysis", f"Created execution plan with {len(worker_execution_order)} agents: {', '.join(worker_execution_order)}")
                except Exception as e:
                    print(f"Failed to record task analysis: {e}")
                
                first_agent = execution_plan.get_current_agent()
                if first_agent:
                    # Record handoff to first agent
                    try:
                        from app.monitoring.streaming_monitor import get_global_streaming_monitor
                        monitor = get_global_streaming_monitor()
                        monitor.record_agent_interaction(
                            "task_analysis",
                            first_agent,
                            "start_execution",
                            {"plan_summary": f"Execute {len(worker_execution_order)} agents"}
                        )
                    except Exception as e:
                        print(f"Failed to record handoff: {e}")
                    
                    return Command(
                        goto=first_agent,
                        update={
                            "current_agent": first_agent,
                            "task_status": "execution_started",
                            "execution_plan": execution_plan.dict(),
                            "original_task": original_task
                        }
                    )
                else:
                    return Command(
                        goto="result_synthesis",
                        update={
                            "task_status": "no_agents_to_execute",
                            "execution_plan": execution_plan.dict(),
                            "original_task": original_task
                        }
                    )
                    
            except Exception as e:
                print(f"Task analysis error: {e}")
                return Command(
                    goto="result_synthesis",
                    update={
                        "error": f"Task analysis failed: {e}",
                        "task_status": "analysis_failed"
                    }
                )
        
        return task_analysis_node
    
    def _tailor_task_for_agent(self, original_task: str, agent_name: str, agent_role: str) -> str:
        """Tailor task for specific agent based on its role and context"""
        agent_config = self.get_agent_config(agent_name)
        if not agent_config:
            return original_task
            
        # Get agent's dependencies to understand context
        dependencies = getattr(agent_config, 'depends_on', [])
        
        # Task tailoring logic based on agent role and dependencies
        tailored_task = original_task
        
        # SEO Specialist: Focus on optimization and visibility
        if agent_name == "seo_specialist":
            tailored_task = f"Optimize the following content for SEO to maximize search engine visibility and engagement:\n\n{original_task}"
            
        # LinkedIn Manager: Focus on professional posting
        elif agent_name == "linkedin_manager":
            tailored_task = f"Create a professional and engaging LinkedIn post based on this content:\n\n{original_task}"
            
        # Content Writer: Focus on content creation
        elif agent_name == "content_writer":
            tailored_task = f"Write compelling content based on this request:\n\n{original_task}"
            
        # Web Researcher: Focus on information gathering
        elif agent_name == "web_researcher":
            tailored_task = f"Research and gather information related to:\n\n{original_task}"
            
        # Data Analyst: Focus on analysis
        elif agent_name == "data_analyst":
            tailored_task = f"Analyze data and provide insights related to:\n\n{original_task}"
            
        # Add context about dependencies if available
        if dependencies:
            context_info = ", ".join(dependencies)
            tailored_task += f"\n\nContext: This task depends on output from: {context_info}"
            
        return tailored_task

    def _create_worker_node(self, worker_name: str, supervisor_name: Optional[str] = None):
        """Create worker node function"""
        cache_key = f"{worker_name}:{supervisor_name}" if supervisor_name else worker_name
        if cache_key in self._node_cache:
            return self._node_cache[cache_key]
        
        async def worker_node(state: Dict[str, Any]) -> Command:
            """Worker agent with tools"""
            try:
                worker_config = self.get_agent_config(worker_name)
                
                # Get task from state dict
                current_task = state.get("current_task") or state.get("original_task") or "No task provided"
                
                # Tailor task for this specific agent
                tailored_task = self._tailor_task_for_agent(current_task, worker_name, worker_config.role)
                
                # Get LLM model
                llm = worker_config.get_model()
                 
                # Check for human feedback and incorporate it
                human_feedback = state.get("human_feedback")
                feedback_section = ""
                if human_feedback:
                    feedback_section = f"\n\n📝 HUMAN FEEDBACK RECEIVED:\n{human_feedback}\n\nPlease revise your work based on this feedback."
                 
                # Create prompt with tailored task and feedback
                prompt = f"""{worker_config.system_prompt}

Task to execute: {tailored_task}
{feedback_section}

Please complete this specific task."""
                
                # Record prompt in monitoring
                try:
                    from app.monitoring.streaming_monitor import get_global_streaming_monitor
                    monitor = get_global_streaming_monitor()
                    monitor.record_agent_prompt(worker_name, prompt)
                except Exception as e:
                    print(f"Failed to record prompt: {e}")
                
                # Execute LLM call
                try:
                    response = await asyncio.wait_for(
                        llm.ainvoke([{"role": "user", "content": prompt}]),
                        timeout=30.0
                    )
                    result = response.content
                except asyncio.TimeoutError:
                    result = f"LLM call timed out after 30 seconds."
                    print(f"{worker_name}: LLM timeout")
                except Exception as e:
                    result = f"LLM call failed: {str(e)[:200]}"
                    print(f"{worker_name}: LLM error: {e}")
                
                # Check if human approval is required before executing tools
                if worker_config.require_approval and worker_config.tools:
                    # Record that approval is needed
                    try:
                        from app.monitoring.streaming_monitor import get_global_streaming_monitor
                        monitor = get_global_streaming_monitor()
                        monitor.record_agent_interaction(
                            worker_name,
                            "human_approval",
                            "awaiting_approval",
                            {"tool_count": len(worker_config.tools), "content_preview": result[:200]}
                        )
                    except Exception as e:
                        print(f"Failed to record approval request: {e}")
                    
                    # Return to human approval node
                    return Command(
                        goto="human_approval",
                        update={
                            "messages": state.get("messages", []) + [
                                AIMessage(content=result, name=worker_name)
                            ],
                            "pending_approval": {
                                "agent": worker_name,
                                "content": result,
                                "tools": [tool.metadata.name if hasattr(tool, 'metadata') and hasattr(tool.metadata, 'name') else str(tool) for tool in worker_config.tools],
                                "require_approval": True
                            },
                            "agent_results": {**state.get("agent_results", {}), worker_name: f"[AWAITING APPROVAL] {result[:100]}..."}
                        }
                    )
                
                # Handle tools if worker has them (no approval required)
                if worker_config.tools:
                    result = await self._handle_worker_tools(worker_name, result, worker_config.tools)
                
                # Record output in monitoring
                try:
                    from app.monitoring.streaming_monitor import get_global_streaming_monitor
                    monitor = get_global_streaming_monitor()
                    monitor.record_agent_output(worker_name, result)
                except Exception as e:
                    print(f"Failed to record output: {e}")
                
                # Update state with result
                update_data = {
                    "messages": state.get("messages", []) + [
                        AIMessage(content=result, name=worker_name)
                    ],
                    "agent_results": {**state.get("agent_results", {}), worker_name: result}
                }
                
                # Get next agent from execution plan if available
                execution_plan = state.get("execution_plan")
                if execution_plan:
                    # Convert dict to ExecutionPlan if needed
                    if isinstance(execution_plan, dict):
                        from app.models.orchestration_state import ExecutionPlan
                        execution_plan = ExecutionPlan(**execution_plan)
                    
                    # Mark agent as complete
                    execution_plan.mark_agent_complete(worker_name, result)
                    
                    # Get next agent
                    next_agent = execution_plan.get_current_agent()
                    if next_agent:
                        update_data["execution_plan"] = execution_plan.dict()
                        update_data["current_agent"] = next_agent
                        
                        # Record handoff decision
                        try:
                            from app.monitoring.streaming_monitor import get_global_streaming_monitor
                            monitor = get_global_streaming_monitor()
                            monitor.record_agent_interaction(
                                worker_name,
                                next_agent,
                                "handoff",
                                {"reason": "Dependency chain", "result_summary": result[:100]}
                            )
                        except Exception as e:
                            print(f"Failed to record handoff: {e}")
                        
                        return Command(goto=next_agent, update=update_data)
                
                # No next agent, go to result synthesis
                return Command(goto="result_synthesis", update=update_data)
                    
            except Exception as e:
                print(f"{worker_name} failed: {e}")
                error_result = f"{worker_name} failed: {str(e)[:200]}"
                
                # Record error output
                try:
                    from app.monitoring.streaming_monitor import get_global_streaming_monitor
                    monitor = get_global_streaming_monitor()
                    monitor.record_agent_output(worker_name, error_result)
                except Exception as e:
                    print(f"Failed to record error output: {e}")
                
                update_data = {
                    "messages": state.get("messages", []) + [
                        AIMessage(content=error_result, name=worker_name)
                    ],
                    "agent_results": {**state.get("agent_results", {}), worker_name: error_result}
                }
                
                # Try to get next agent
                execution_plan = state.get("execution_plan")
                if execution_plan:
                    if isinstance(execution_plan, dict):
                        from app.models.orchestration_state import ExecutionPlan
                        execution_plan = ExecutionPlan(**execution_plan)
                    
                    execution_plan.mark_agent_complete(worker_name, error_result)
                    next_agent = execution_plan.get_current_agent()
                    if next_agent:
                        update_data["execution_plan"] = execution_plan.dict()
                        update_data["current_agent"] = next_agent
                        return Command(goto=next_agent, update=update_data)
                
                return Command(goto="result_synthesis", update=update_data)
        
        self._node_cache[cache_key] = worker_node
        return worker_node
    
    async def _handle_worker_tools(self, worker_name: str, content: str, tools: List[Any]) -> str:
        """Handle worker tools based on tool objects"""
        result = content
        
        for tool in tools:
            if not tool:
                print(f"Tool object is None for {worker_name}")
                continue
                
            try:
                tool_name = tool.metadata.name if hasattr(tool, 'metadata') and hasattr(tool.metadata, 'name') else str(tool)
                
                if tool_name == "tavily_search" or tool_name == "mock_search":
                    # For web_researcher, use the generated query to perform search
                    search_query = content.strip()
                    if search_query:
                        search_result = await tool.execute(search_query)
                        # Format search results nicely
                        if isinstance(search_result, dict):
                            answer = search_result.get('answer', 'No answer found')
                            total_results = search_result.get('total_results', 0)
                            results = search_result.get('results', [])
                            
                            formatted_results = f"Search query: {search_query}\n\n"
                            formatted_results += f"Answer: {answer}\n\n"
                            formatted_results += f"Found {total_results} results:\n"
                            
                            for i, res in enumerate(results[:3]):  # Show top 3 results
                                title = res.get('title', 'No title')
                                url = res.get('url', 'No URL')
                                content_snippet = res.get('content', '')[:200]
                                formatted_results += f"\n{i+1}. {title}\n   URL: {url}\n   {content_snippet}...\n"
                            
                            result = formatted_results
                        else:
                            result = f"Search query: {search_query}\n\nSearch results:\n{search_result}"
                    else:
                        result = f"No search query generated for {tool_name}"
                        
                elif tool_name == "linkedin_post":
                    # For linkedin_manager, post the content
                    post_result = await tool.execute(content)
                    # Format LinkedIn post result nicely
                    result = f"🚀 LINKEDIN POST TOOL EXECUTED:\n\n"
                    result += f"Post content:\n{content}\n\n"
                    result += f"Post result: {post_result}\n\n"
                    result += f"Note: This is a {'MOCK' if 'mock' in str(tool).lower() else 'REAL'} LinkedIn post"
                    
                else:
                    # Generic tool execution
                    tool_result = await tool.execute(content)
                    result = f"Tool {tool_name} executed: {tool_result[:200]}..."
                    
            except Exception as e:
                result = f"Tool {tool_name if 'tool_name' in locals() else 'unknown'} failed: {str(e)}"
                print(f"{worker_name}: {result}")
        
        return result
    
    def _create_supervisor_node(self, supervisor_name: str, managed_agents: List[str]):
        """Create supervisor node function with dynamic routing and task tailoring"""
        async def supervisor_node(state: Dict[str, Any]) -> Command:
            try:
                supervisor_config = self.get_agent_config(supervisor_name)
                
                # Get current task
                current_task = state.get('messages', [])[-1].content if state.get('messages') else state.get('original_task', 'No task provided')
                
                # Provide tailored instructions for each managed agent
                agent_specific_instructions = "\n".join([
                    f"- {agent}: {self._tailor_task_for_agent(current_task, agent, 'worker')}"
                    for agent in managed_agents
                ])
                
                routing_prompt = f"""{supervisor_config.system_prompt}

Available agents: {', '.join(managed_agents)}

Current task: {current_task}

Agent-specific task variations:
{agent_specific_instructions}

Please route to the most appropriate agent or FINISH if complete.

Output format: {{"next_node": "agent_name", "reasoning": "explanation", "confidence": 0.95, "should_terminate": false}}"""
                
                llm = supervisor_config.get_model()
                
                try:
                    response = await asyncio.wait_for(
                        llm.ainvoke([{"role": "user", "content": routing_prompt}]),
                        timeout=30.0
                    )
                    decision = json.loads(response.content)
                except Exception as e:
                    print(f"{supervisor_name}: LLM error: {e}")
                    # Fallback to first agent
                    decision = {"next_node": managed_agents[0] if managed_agents else "FINISH", "reasoning": "Fallback", "confidence": 0.5, "should_terminate": False}
                
                update_data = {
                    "iteration_count": state.get("iteration_count", 0) + 1,
                    "current_agent": decision["next_node"] if decision["next_node"] != "FINISH" else None,
                    "routing_decision": decision
                }
                
                if decision.get("instructions"):
                    update_data["messages"] = state.get("messages", []) + [HumanMessage(content=decision["instructions"], name="supervisor_instructions")]
                
                if decision.get("should_terminate", False) or decision["next_node"] == "FINISH":
                    update_data["team_status"] = "completed"
                    return Command(goto=END, update=update_data)
                
                return Command(goto=decision["next_node"], update=update_data)
                
            except Exception as e:
                print(f"{supervisor_name} routing failed: {e}")
                # Fallback to first agent
                return Command(
                    goto=managed_agents[0] if managed_agents else END,
                    update={"iteration_count": state.get("iteration_count", 0) + 1}
                )
        
        return supervisor_node
    
    def _create_human_approval_node(self):
        """Create node for human-in-the-loop approval"""
        async def human_approval_node(state: Dict[str, Any]) -> Command:
            """Handle human approval for agent actions"""
            print("DEBUG: human_approval_node called!")
            print(f"DEBUG: state keys: {list(state.keys())}")
            print(f"DEBUG: pending_approval: {state.get('pending_approval')}")
            
            try:
                pending_approval = state.get("pending_approval")
                if not pending_approval:
                    print("DEBUG: No pending_approval, returning to END")
                    # No pending approval, continue to END
                    return Command(goto=END, update={})
                
                agent_name = pending_approval.get("agent")
                content = pending_approval.get("content", "")
                tools = pending_approval.get("tools", [])
                
                # Record approval request in monitoring
                try:
                    from app.monitoring.streaming_monitor import get_global_streaming_monitor
                    monitor = get_global_streaming_monitor()
                    monitor.record_agent_interaction(
                        "human_approval",
                        agent_name,
                        "approval_request",
                        {
                            "tools": tools,
                            "content_preview": content[:200],
                            "status": "awaiting_decision"
                        }
                    )
                except Exception as e:
                    print(f"Failed to record approval request: {e}")
                
                # Display approval request to user
                print("\n" + "="*80)
                print("🔔 HUMAN APPROVAL REQUIRED")
                print("="*80)
                print(f"Agent: {agent_name}")
                print(f"Tools to execute: {tools}")
                print(f"\nContent to publish:")
                print("-"*40)
                print(content[:500] + ("..." if len(content) > 500 else ""))
                print("-"*40)
                
                # Get user decision
                while True:
                    print("\nOptions:")
                    print("1. Approve - Execute the tools")
                    print("2. Reject - Skip tool execution")
                    print("3. View full content")
                    print("4. Provide feedback - Give guidance to improve the content")
                    print("\nEnter your choice (1/2/3/4): ", end="", flush=True)
                     
                    # Use asyncio to run input in executor since input() is blocking
                    import sys
                    if sys.version_info >= (3, 8):
                        import asyncio
                        loop = asyncio.get_event_loop()
                        choice = await loop.run_in_executor(None, input)
                    else:
                        # Fallback for older Python versions
                        choice = input()
                     
                    choice = choice.strip()
                     
                    if choice == "1":
                        decision = "approve"
                        break
                    elif choice == "2":
                        decision = "reject"
                        break
                    elif choice == "3":
                        print("\n" + "="*80)
                        print("FULL CONTENT:")
                        print("="*80)
                        print(content)
                        print("="*80)
                        continue
                    elif choice == "4":
                        print("\n" + "="*80)
                        print("📝 PROVIDE FEEDBACK")
                        print("="*80)
                        print("Enter your feedback to guide the agent (e.g., 'Make it more technical', 'Add examples', etc.):")
                        print("Type 'cancel' to go back to the main menu.")
                        
                        # Get feedback input
                        if sys.version_info >= (3, 8):
                            feedback = await loop.run_in_executor(None, input)
                        else:
                            feedback = input()
                        
                        feedback = feedback.strip()
                        
                        if feedback.lower() == 'cancel':
                            continue
                        
                        if feedback:
                            # Store feedback and return to agent for revision
                            decision = "feedback"
                            feedback_data = feedback
                            break
                        else:
                            print("Feedback cannot be empty. Please try again.")
                            continue
                    else:
                        print("Invalid choice. Please enter 1, 2, 3, or 4.")
                        continue
                
                if decision == "approve":
                    print(f"\n✅ APPROVED: Tools will be executed for {agent_name}")
                    
                    # Get agent config and execute tools
                    worker_config = self.get_agent_config(agent_name)
                    if worker_config and worker_config.tools:
                        # Execute tools
                        result = await self._handle_worker_tools(agent_name, content, worker_config.tools)
                        
                        # Record approval decision
                        try:
                            from app.monitoring.streaming_monitor import get_global_streaming_monitor
                            monitor = get_global_streaming_monitor()
                            monitor.record_agent_interaction(
                                "human_approval",
                                agent_name,
                                "approved",
                                {"decision": "approved", "tools_executed": tools}
                            )
                            monitor.record_agent_output(agent_name, result)
                        except Exception as e:
                            print(f"Failed to record approval decision: {e}")
                        
                        # Update state with tool execution result
                        update_data = {
                            "messages": state.get("messages", []) + [
                                AIMessage(content=result, name=agent_name)
                            ],
                            "agent_results": {**state.get("agent_results", {}), agent_name: result},
                            "pending_approval": None  # Clear pending approval
                        }
                        
                        # Get next agent from execution plan (for orchestrated graph)
                        execution_plan = state.get("execution_plan")
                        if execution_plan:
                            if isinstance(execution_plan, dict):
                                from app.models.orchestration_state import ExecutionPlan
                                execution_plan = ExecutionPlan(**execution_plan)
                            
                            execution_plan.mark_agent_complete(agent_name, result)
                            next_agent = execution_plan.get_current_agent()
                            if next_agent:
                                update_data["execution_plan"] = execution_plan.dict()
                                update_data["current_agent"] = next_agent
                                return Command(goto=next_agent, update=update_data)
                            else:
                                # No next agent, go to result synthesis
                                return Command(goto="result_synthesis", update=update_data)
                        else:
                            # Single agent graph, go to END
                            return Command(goto=END, update=update_data)
                    else:
                        # No tools to execute
                        execution_plan = state.get("execution_plan")
                        if execution_plan:
                            return Command(goto="result_synthesis", update={"pending_approval": None})
                        else:
                            return Command(goto=END, update={"pending_approval": None})

                elif decision == "feedback":
                    print(f"\n📝 FEEDBACK PROVIDED: '{feedback_data}'")
                    print(f"Agent will revise the content based on your feedback...")
                     
                    # Return to the agent with feedback for revision
                    # Store feedback in state and send back to agent
                    update_data = {
                        "messages": state.get("messages", []) + [
                            HumanMessage(content=f"HUMAN FEEDBACK: {feedback_data}\n\nPlease revise your work based on this feedback:", name="human_feedback")
                        ],
                        "agent_results": {**state.get("agent_results", {}), agent_name: f"[FEEDBACK RECEIVED] {feedback_data}"},
                        "pending_approval": None,  # Clear pending approval
                        "human_feedback": feedback_data  # Store feedback for agent
                    }
                     
                    # Send back to the agent for revision
                    return Command(goto=agent_name, update=update_data)
                
                elif decision == "reject":
                    print(f"\n❌ REJECTED: Tool execution skipped for {agent_name}")
                    
                    # Record rejection
                    try:
                        from app.monitoring.streaming_monitor import get_global_streaming_monitor
                        monitor = get_global_streaming_monitor()
                        monitor.record_agent_interaction(
                            "human_approval",
                            agent_name,
                            "rejected",
                            {"decision": "rejected", "reason": "Human rejected the action"}
                        )
                    except Exception as e:
                        print(f"Failed to record rejection: {e}")
                    
                    # Update state with rejection
                    rejection_result = f"[REJECTED BY HUMAN] Tool execution was rejected for {agent_name}"
                    update_data = {
                        "messages": state.get("messages", []) + [
                            AIMessage(content=rejection_result, name=agent_name)
                        ],
                        "agent_results": {**state.get("agent_results", {}), agent_name: rejection_result},
                        "pending_approval": None
                    }
                    
                    # Get next agent
                    execution_plan = state.get("execution_plan")
                    if execution_plan:
                        if isinstance(execution_plan, dict):
                            from app.models.orchestration_state import ExecutionPlan
                            execution_plan = ExecutionPlan(**execution_plan)
                        
                        execution_plan.mark_agent_complete(agent_name, rejection_result)
                        next_agent = execution_plan.get_current_agent()
                        if next_agent:
                            update_data["execution_plan"] = execution_plan.dict()
                            update_data["current_agent"] = next_agent
                            return Command(goto=next_agent, update=update_data)
                        else:
                            # No next agent, go to result synthesis
                            return Command(goto="result_synthesis", update=update_data)
                    else:
                        # Single agent graph, go to END
                        return Command(goto=END, update=update_data)
                
                else:
                    # Should not reach here
                    execution_plan = state.get("execution_plan")
                    if execution_plan:
                        return Command(goto="result_synthesis", update={"pending_approval": None})
                    else:
                        return Command(goto=END, update={"pending_approval": None})
                    
            except Exception as e:
                print(f"Human approval node failed: {e}")
                # Clear pending approval and continue
                execution_plan = state.get("execution_plan") if 'state' in locals() else None
                if execution_plan:
                    return Command(
                        goto="result_synthesis",
                        update={
                            "pending_approval": None,
                            "error": f"Human approval failed: {e}"
                        }
                    )
                else:
                    return Command(
                        goto=END,
                        update={
                            "pending_approval": None,
                            "error": f"Human approval failed: {e}"
                        }
                    )
        
        return human_approval_node
    
    def _create_result_synthesis_node(self, entry_point: str):
        """Create node for synthesizing results"""
        async def result_synthesis_node(state: Dict[str, Any]) -> Command:
            """Synthesize results from all agents"""
            try:
                agent_results = state.get("agent_results", {})
                
                if not agent_results:
                    final_result = "No results were generated."
                else:
                    result_summary = "## Task Execution Results\n\n"
                    for agent_name, result in agent_results.items():
                        result_summary += f"### {agent_name}\n{result}\n\n"
                    
                    final_result = result_summary
                
                # Record final result in monitoring
                try:
                    from app.monitoring.streaming_monitor import get_global_streaming_monitor
                    monitor = get_global_streaming_monitor()
                    monitor.record_agent_output("result_synthesis", f"Synthesized results from {len(agent_results)} agents")
                    monitor.record_agent_interaction(
                        "result_synthesis",
                        "END",
                        "complete",
                        {"agents_executed": len(agent_results)}
                    )
                except Exception as e:
                    print(f"Failed to record result synthesis: {e}")
                
                return Command(
                    goto=END,
                    update={
                        "final_result": final_result,
                        "task_status": "completed"
                    }
                )
                
            except Exception as e:
                print(f"Result synthesis failed: {e}")
                return Command(
                    goto=END,
                    update={
                        "final_result": f"Result synthesis failed: {e}",
                        "task_status": "synthesis_failed"
                    }
                )
        
        return result_synthesis_node


def create_orchestrated_workflow(config_path: str = "config/agents.yaml",
                                entry_point: str = "main_supervisor",
                                checkpointer=None) -> StateGraph:
    """
    Create workflow using orchestrated graph builder.
    """
    builder = OrchestratedGraphBuilder(config_path)
    return builder.build_graph(entry_point, checkpointer)
