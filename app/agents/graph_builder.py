#!/usr/bin/env python3
"""
Configuration-driven graph builder for marketing agents.
This module creates the hierarchical marketing workflow from YAML configuration.
"""

import asyncio
from typing import Literal, List, Optional, Dict, Any
from datetime import datetime
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from langgraph.errors import GraphInterrupt
from langchain_core.messages import HumanMessage, AIMessage

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


class ConfigDrivenGraphBuilder:
    """Builds hierarchical marketing workflow from YAML configuration"""
    
    def __init__(self):
        # Load configuration
        self.config_loader = ConfigurationLoader()
        self.agent_config_manager = self.config_loader.load_agents()
        
        # Inject managed agents into prompts
        inject_managed_agents_into_prompts(self.agent_config_manager)
        
        # Initialize tool registry
        from app.utils.config_loader import GLOBAL_TOOL_REGISTRY
        self.tool_registry = GLOBAL_TOOL_REGISTRY
    
    def get_agent_config(self, agent_name: str):
        """Get agent configuration by name"""
        return self.agent_config_manager.get_agent_config(agent_name)
    
    def create_team_graph(self, team_name: str, supervisor_name: str, worker_names: List[str]) -> StateGraph:
        """Create a team graph with supervisor and workers"""
        builder = StateGraph(TeamState)
        
        # Add supervisor node
        builder.add_node("supervisor", self._create_supervisor_node(supervisor_name, worker_names))
        
        # Add worker nodes
        for worker_name in worker_names:
            builder.add_node(worker_name, self._create_worker_node(worker_name))
        
        # Add edges
        builder.add_edge(START, "supervisor")
        for worker_name in worker_names:
            builder.add_edge(worker_name, "supervisor")
        
        return builder.compile()
    
    def _create_supervisor_node(self, supervisor_name: str, worker_names: List[str]):
        """Create supervisor node function"""
        
        @monitor_agent_call(supervisor_name)
        async def supervisor_node(state: TeamState) -> Command:
            """Supervisor with LLM routing"""
            # Check iteration limit
            if state.get("iteration_count", 0) >= 3:
                return Command(goto=END, update={"team_status": "completed"})
            
            try:
                # Get supervisor config
                supervisor_config = self.get_agent_config(supervisor_name)
                
                # Create routing prompt with available workers
                routing_prompt = f"""{supervisor_config.system_prompt}

Available agents: {', '.join(worker_names)}

Current task: {state['messages'][-1].content if state['messages'] else 'No task provided'}

Please route to the most appropriate agent or FINISH if complete.

Output format: {{"next_node": "agent_name", "reasoning": "explanation", "confidence": 0.95, "should_terminate": false}}"""
                
                # Get LLM model
                llm = supervisor_config.get_model()
                
                # Get routing decision
                response = await llm.ainvoke([{"role": "user", "content": routing_prompt}])
                
                # Parse JSON response (simplified - in production use structured output)
                import json
                decision = json.loads(response.content)
                
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
                return self._fallback_routing(state, worker_names)
        
        return supervisor_node
    
    def _create_worker_node(self, worker_name: str):
        """Create worker node function"""
        
        @monitor_agent_call(worker_name)
        async def worker_node(state: TeamState) -> Command:
            """Worker agent with tools"""
            try:
                # Get worker config
                worker_config = self.get_agent_config(worker_name)
                
                # Extract task
                original_task = state["messages"][-1].content if state["messages"] else "No task provided"
                context = "\n".join([f"{msg.name}: {msg.content}" for msg in state["messages"] if hasattr(msg, "name") and msg.name not in ["user", "system"]])
                
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
                
                # Execute LLM call
                response = await asyncio.wait_for(llm.ainvoke([{"role": "user", "content": prompt}]), timeout=60.0)
                result = response.content
                
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
                
                return Command(
                    goto="supervisor",
                    update={
                        "messages": response_messages,
                        "task_completed": True,
                        "agent_executed": worker_name
                    }
                )
                
            except Exception as e:
                print(f"{worker_name} failed: {e}")
                error_response = f"{worker_name} failed: {str(e)[:200]}"
                return Command(
                    goto="supervisor",
                    update={
                        "messages": [AIMessage(content=error_response, name=worker_name)],
                        "task_completed": False,
                        "error": str(e)
                    }
                )
        
        return worker_node
    
    async def _handle_worker_tools(self, worker_name: str, worker_config, result: str, original_task: str) -> str:
        """Handle tool execution for workers"""
        # For now, just handle LinkedIn posting for linkedin_manager
        if worker_name == "linkedin_manager" and "linkedin_post" in [tool.metadata.name for tool in worker_config.tools]:
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
                    try:
                        # Execute tool with company URN for company page posting
                        result = await tool.execute(content_to_publish)
                    except Exception as e:
                        result = f"❌ Publishing exception: {str(e)}"
                else:
                    result = "❌ Error: LinkedIn tool not found in registry."
            else:
                result = f"❌ Publication rejected. Feedback: {user_feedback}"
        
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
    
    def create_main_workflow(self, checkpointer=None) -> StateGraph:
        """Create the complete hierarchical marketing workflow"""
        
        # Create team graphs
        research_team_graph = self.create_team_graph(
            "research_team",
            "research_team_supervisor",
            ["web_researcher", "data_analyst"]
        )
        
        content_team_graph = self.create_team_graph(
            "content_team",
            "content_team_supervisor",
            ["content_writer", "seo_specialist", "visual_designer"]
        )
        
        social_media_team_graph = self.create_team_graph(
            "social_media_team",
            "social_media_team_supervisor",
            ["linkedin_manager", "twitter_manager", "analytics_tracker"]
        )
        
        async def call_research_team(state: EnhancedMarketingState) -> Command:
            """Call research team"""
            try:
                sanitized_messages = sanitize_messages_for_agent(state["messages"])
                
                response = await research_team_graph.ainvoke({
                    "messages": sanitized_messages,
                    "team_name": "research_team",
                    "iteration_count": 0
                })
                
                # Extract result
                result_message = None
                for msg in reversed(response["messages"]):
                    if isinstance(msg, AIMessage) and msg.name in ["web_researcher", "data_analyst"]:
                        result_message = msg
                        break
                
                if not result_message and response["messages"]:
                    result_message = response["messages"][-1]
                
                return Command(
                    goto="supervisor",
                    update={
                        "messages": [result_message] if result_message else [],
                        "current_team": "research_team",
                        "team_result": response.get("task_completed", False)
                    }
                )
                
            except Exception as e:
                print(f"Research team failed: {e}")
                return Command(
                    goto="supervisor",
                    update={
                        "messages": [AIMessage(content=f"Research team error: {str(e)[:200]}", name="system")],
                        "current_team": "research_team",
                        "team_result": False,
                        "error": str(e)
                    }
                )
        
        async def call_content_team(state: EnhancedMarketingState) -> Command:
            """Call content team"""
            try:
                sanitized_messages = sanitize_messages_for_agent(state["messages"])
                
                response = await content_team_graph.ainvoke({
                    "messages": sanitized_messages,
                    "team_name": "content_team",
                    "iteration_count": 0
                })
                
                # Extract result
                result_message = None
                for msg in reversed(response["messages"]):
                    if isinstance(msg, AIMessage) and msg.name in ["content_writer", "seo_specialist", "visual_designer"]:
                        result_message = msg
                        break
                
                if not result_message and response["messages"]:
                    result_message = response["messages"][-1]
                
                return Command(
                    goto="supervisor",
                    update={
                        "messages": [result_message] if result_message else [],
                        "current_team": "content_team",
                        "team_result": response.get("task_completed", False)
                    }
                )
                
            except GraphInterrupt:
                # Re-raise for main loop to handle
                raise
            except Exception as e:
                print(f"Content team failed: {e}")
                return Command(
                    goto="supervisor",
                    update={
                        "messages": [AIMessage(content=f"Content team error: {str(e)[:200]}", name="system")],
                        "current_team": "content_team",
                        "team_result": False,
                        "error": str(e)
                    }
                )
        
        async def call_social_media_team(state: EnhancedMarketingState) -> Command:
            """Call social media team"""
            try:
                sanitized_messages = sanitize_messages_for_agent(state["messages"])
                
                response = await social_media_team_graph.ainvoke({
                    "messages": sanitized_messages,
                    "team_name": "social_media_team",
                    "iteration_count": 0
                })
                
                # Extract result
                result_message = None
                for msg in reversed(response["messages"]):
                    if isinstance(msg, AIMessage) and msg.name in ["linkedin_manager", "twitter_manager", "analytics_tracker"]:
                        result_message = msg
                        break
                
                if not result_message and response["messages"]:
                    result_message = response["messages"][-1]
                
                return Command(
                    goto="supervisor",
                    update={
                        "messages": [result_message] if result_message else [],
                        "current_team": "social_media_team",
                        "team_result": response.get("task_completed", False)
                    }
                )
                
            except GraphInterrupt:
                # Re-raise for main loop to handle
                raise
            except Exception as e:
                print(f"Social media team failed: {e}")
                return Command(
                    goto="supervisor",
                    update={
                        "messages": [AIMessage(content=f"Social media team error: {str(e)[:200]}", name="system")],
                        "current_team": "social_media_team",
                        "team_result": False,
                        "error": str(e)
                    }
                )
        
        @monitor_agent_call("main_supervisor")
        async def main_supervisor_node(state: EnhancedMarketingState) -> Command:
            """Main supervisor with LLM routing"""
            # Check iteration limit
            if state.get("iteration_count", 0) >= 3:
                return Command(goto=END, update={"workflow_status": "completed"})
            
            # Check for message nesting
            if detect_message_nesting(state["messages"]):
                print("⚠️  Message nesting detected, resetting messages")
                state["messages"] = reset_message_nesting(state["messages"])
            
            try:
                # Get main supervisor config
                supervisor_config = self.get_agent_config("main_supervisor")
                
                # Create routing prompt
                routing_prompt = f"""{supervisor_config.system_prompt}

Current task: {state['messages'][-1].content if state['messages'] else 'No task provided'}

Please route to the most appropriate team or FINISH if complete.

Output format: {{"next_node": "team_name", "reasoning": "explanation", "confidence": 0.95, "should_terminate": false}}"""
                
                # Get LLM model
                llm = supervisor_config.get_model()
                
                # Get routing decision
                response = await llm.ainvoke([{"role": "user", "content": routing_prompt}])
                
                # Parse JSON response
                import json
                decision = json.loads(response.content)
                
                # Log routing decision
                monitor = get_global_monitor()
                monitor.record_routing_decision(
                    supervisor_name="main_supervisor",
                    decision=decision,
                    duration_ms=0
                )
                
                # Update state
                update_data = {
                    "iteration_count": state.get("iteration_count", 0) + 1,
                    "current_team": decision["next_node"] if decision["next_node"] != "FINISH" else None,
                    "routing_decision": decision,
                    "routing_confidence": decision["confidence"],
                    "routing_reasoning": decision["reasoning"]
                }
                
                if decision.get("should_terminate", False) or decision["next_node"] == "FINISH":
                    update_data["workflow_status"] = "completed"
                    return Command(goto=END, update=update_data)
                
                return Command(goto=decision["next_node"], update=update_data)
                
            except Exception as e:
                # Fallback to keyword routing
                print(f"Main supervisor routing failed: {e}")
                return self._main_fallback_routing(state)
        
        def _main_fallback_routing(state: EnhancedMarketingState) -> Command:
            """Fallback routing for main supervisor"""
            if state.get("iteration_count", 0) >= 4:
                return Command(goto=END, update={"workflow_status": "completed"})
            
            last_message = state["messages"][-1].content.lower() if state["messages"] else ""
            
            # Simple keyword routing
            if "research" in last_message or "analyze" in last_message:
                goto = "research_team"
            elif "content" in last_message or "write" in last_message:
                goto = "content_team"
            elif "social" in last_message or "post" in last_message:
                goto = "social_media_team"
            else:
                goto = "research_team" if state.get("iteration_count", 0) == 0 else END
            
            return Command(
                goto=goto,
                update={
                    "iteration_count": state.get("iteration_count", 0) + 1,
                    "current_team": goto if goto != END else None
                }
            )
        
        # Build main graph
        main_builder = StateGraph(EnhancedMarketingState)
        main_builder.add_node("supervisor", main_supervisor_node)
        main_builder.add_node("research_team", call_research_team)
        main_builder.add_node("content_team", call_content_team)
        main_builder.add_node("social_media_team", call_social_media_team)
        
        main_builder.add_edge(START, "supervisor")
        main_builder.add_edge("research_team", "supervisor")
        main_builder.add_edge("content_team", "supervisor")
        main_builder.add_edge("social_media_team", "supervisor")
        
        return main_builder.compile(checkpointer=checkpointer)


def create_config_driven_workflow(checkpointer=None) -> StateGraph:
    """Create the complete hierarchical marketing workflow from configuration"""
    builder = ConfigDrivenGraphBuilder()
    return builder.create_main_workflow(checkpointer=checkpointer)