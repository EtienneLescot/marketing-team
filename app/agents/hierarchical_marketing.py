#!/usr/bin/env python3
"""
Hierarchical marketing agents with LLM-based routing and proper message processing.
"""

import asyncio
from typing import Literal, List, Optional, Dict, Any
from datetime import datetime
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from langgraph.errors import GraphInterrupt
from langchain_core.messages import HumanMessage, AIMessage

from app.models.state_models import EnhancedMarketingState, TeamState
from app.routing.structured_router import (
    create_main_supervisor_router,
    create_research_team_router,
    create_content_team_router,
    create_social_media_team_router
)
from app.tools import create_tool_registry
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


# ============================================================================
# Agent Configuration
# ============================================================================

class AgentConfig:
    """Configuration for agents"""
    
    def __init__(self):
        # Initialize tool registry
        self.tool_registry = create_tool_registry()
        
        # Get LLM from agent_config.py
        from agent_config import agent_config as global_config
        self.llm_provider = global_config
        
        # Create routers
        self.main_supervisor_router = create_main_supervisor_router(
            self.llm_provider.get_agent_config("main_supervisor").get_model()
        )
        self.research_team_router = create_research_team_router(
            self.llm_provider.get_agent_config("research_team_supervisor").get_model()
        )
        self.content_team_router = create_content_team_router(
            self.llm_provider.get_agent_config("content_team_supervisor").get_model()
        )
        self.social_media_team_router = create_social_media_team_router(
            self.llm_provider.get_agent_config("social_media_team_supervisor").get_model()
        )


# ============================================================================
# Research Team Agents
# ============================================================================

def create_research_team(config: AgentConfig) -> StateGraph:
    """Create research team with LLM-based routing"""
    
    @monitor_agent_call("research_supervisor")
    async def research_supervisor_node(state: TeamState) -> Command[Literal["web_researcher", "data_analyst", "__end__"]]:
        """Research team supervisor with LLM routing"""
        # Check iteration limit
        if state.get("iteration_count", 0) >= 2:
            return Command(goto=END, update={"team_status": "completed"})
        
        try:
            # Get routing decision
            decision = await config.research_team_router.route(state)
            
            # Log routing decision
            monitor = get_global_monitor()
            monitor.record_routing_decision(
                supervisor_name="research_supervisor",
                decision=decision.dict(),
                duration_ms=0
            )
            
            # Update state with decision metadata
            update_data = {
                "iteration_count": state.get("iteration_count", 0) + 1,
                "current_agent": decision.next_node if decision.next_node != "FINISH" else None,
                "routing_decision": decision.dict()
            }
            
            # Add instructions to messages if present
            if decision.instructions:
                update_data["messages"] = state.get("messages", []) + [HumanMessage(content=decision.instructions, name="supervisor_instructions")]
            
            if decision.should_terminate or decision.next_node == "FINISH":
                update_data["team_status"] = "completed"
                return Command(goto=END, update=update_data)
            
            return Command(goto=decision.next_node, update=update_data)
            
        except Exception as e:
            # Fallback to keyword routing
            print(f"Research supervisor routing failed: {e}")
            return _research_fallback_routing(state)
    
    @monitor_agent_call("web_researcher")
    async def web_researcher_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Web researcher agent with real search tool"""
        monitor = get_global_monitor()
        
        try:
            # Extract specific task from supervisor instructions
            original_task = state["messages"][-1].content if state["messages"] else "No task provided"
            
            # Get search tool
            search_tool = config.tool_registry.get_tool("tavily_search") or \
                         config.tool_registry.get_tool("mock_search")
            
            # Get researcher model (reusing data analyst model config if specific one doesn't exist, or we can add one)
            # For now, we'll request "web_researcher" config, assuming it exists or falls back
            try:
                llm = config.llm_provider.get_agent_config("web_researcher").get_model()
            except:
                # Fallback to data analyst model if web_researcher not explicitly configured with model
                llm = config.llm_provider.get_agent_config("data_analyst").get_model()

            # Generate search query using LLM
            query_prompt = f"You are an expert web researcher. Given the user's task: '{original_task}', generate a single, highly effective search query to find relevant information. Return ONLY the query, no quotes or explanation."
            
            # Record prompt
            monitor.record_agent_prompt("web_researcher", f"System: Generate search query\nUser: {query_prompt}")
            
            print(f"DEBUG: Web Researcher generating query for: {original_task[:50]}...")
            try:
                # Use a specific timeout for query generation
                response = await asyncio.wait_for(llm.ainvoke([{"role": "user", "content": query_prompt}]), timeout=30.0)
                search_query = response.content.strip().strip('"').strip("'")
                print(f"DEBUG: Web Researcher generated query: {search_query}")
            except Exception as e:
                print(f"DEBUG: Web Researcher query generation failed: {e}")
                search_query = original_task  # Fallback to original task

            if not search_tool:
                result = "Search tool not available"
                monitor.record_event(
                    agent_name="web_researcher",
                    event_type="tool_unavailable",
                    data={"tool_name": "search_tool"}
                )
            else:
                # Execute search with monitoring
                with TimerContext(monitor, "web_researcher", "search_tool"):
                    search_result = await search_tool.execute(
                        query=search_query,
                        max_results=5,
                        search_depth="basic"
                    )
                
                # Record tool call
                monitor.record_tool_call(
                    agent_name="web_researcher",
                    tool_name=search_tool.metadata.name,
                    params={"query": search_query, "max_results": 5},
                    result=f"Found {search_result.get('total_results', 0)} results",
                    duration_ms=None  # Already recorded by TimerContext
                )
                
            # Format result
                if search_result.get("answer"):
                    result = f"Search results for query '{search_query}' (Task: '{original_task}'):\n\n{search_result['answer']}"
                    
                    # Add summary of top results
                    if search_result.get("results"):
                        top_results = search_result["results"][:3]
                        result += "\n\nTop results:\n"
                        for i, res in enumerate(top_results, 1):
                            result += f"{i}. {res.get('title', 'No title')}\n"
                            result += f"   {res.get('content', '')[:150]}...\n"
                else:
                    result = f"Found {search_result.get('total_results', 0)} results for '{original_task}'"
            
            # Record agent output
            monitor.record_agent_output("web_researcher", result)

            # Create agent response
            response_messages = create_agent_response(
                content=result,
                agent_name="web_researcher",
                include_original_task=True,
                original_task=original_task
            )
            
            return Command(
                goto="supervisor",
                update={
                    "messages": response_messages,
                    "task_completed": True,
                    "agent_executed": "web_researcher"
                }
            )
            
        except Exception as e:
            print(f"Web researcher failed: {e}")
            error_response = f"Web research failed: {str(e)[:200]}"
            return Command(
                goto="supervisor",
                update={
                    "messages": [AIMessage(content=error_response, name="web_researcher")],
                    "task_completed": False,
                    "error": str(e)
                }
            )
    
    @monitor_agent_call("data_analyst")
    async def data_analyst_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Data analyst agent"""
        try:
            # Extract specific task from supervisor instructions
            original_task = state["messages"][-1].content if state["messages"] else "No task provided"
            
            # Get data analyst model
            llm = config.llm_provider.get_agent_config("data_analyst").get_model()
            
            # Create prompt
            system_prompt = config.llm_provider.get_agent_config("data_analyst").system_prompt
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Please analyze the following task/data and provide insights:\n\n{original_task}"}
            ]
            
            # Record prompt
            monitor = get_global_monitor()
            formatted_prompt = f"System: {system_prompt}\n\nUser: Please analyze the following task/data and provide insights:\n\n{original_task}"
            monitor.record_agent_prompt("data_analyst", formatted_prompt)
            
            # Execute LLM call
            print(f"DEBUG: Data Analyst calling LLM for task: {original_task[:50]}...")
            try:
                response = await asyncio.wait_for(llm.ainvoke(messages), timeout=60.0)
                print("DEBUG: Data Analyst received response")
                analysis_result = response.content
            except asyncio.TimeoutError:
                print("DEBUG: Data Analyst timeout")
                analysis_result = "Targeted analysis: Timeout waiting for detailed analysis. Focusing on key metrics based on available data."
            except Exception as e:
                print(f"DEBUG: Data Analyst analysis failed: {e}")
                analysis_result = f"Analysis failed: {str(e)}"
            
            # Record agent output
            monitor = get_global_monitor()
            monitor.record_agent_output("data_analyst", analysis_result)
            
            # Create agent response
            response_messages = create_agent_response(
                content=analysis_result,
                agent_name="data_analyst",
                include_original_task=True,
                original_task=original_task
            )
            
            return Command(
                goto="supervisor",
                update={
                    "messages": response_messages,
                    "task_completed": True,
                    "agent_executed": "data_analyst"
                }
            )
            
        except Exception as e:
            print(f"Data analyst failed: {e}")
            error_response = f"Data analysis failed: {str(e)[:200]}"
            return Command(
                goto="supervisor",
                update={
                    "messages": [AIMessage(content=error_response, name="data_analyst")],
                    "task_completed": False,
                    "error": str(e)
                }
            )

    def _research_fallback_routing(state: TeamState) -> Command[Literal["web_researcher", "data_analyst", "__end__"]]:
        """Fallback routing for research team"""
        if state.get("iteration_count", 0) >= 2:
            return Command(goto=END, update={"team_status": "completed"})
        
        last_message = state["messages"][-1].content.lower() if state["messages"] else ""
        
        # Simple keyword routing
        if "data" in last_message or "analytics" in last_message or "metric" in last_message:
            goto = "data_analyst"
        else:
            goto = "web_researcher"
        
        return Command(
            goto=goto,
            update={"iteration_count": state.get("iteration_count", 0) + 1}
        )
    
    # Build research team graph
    research_builder = StateGraph(TeamState)
    research_builder.add_node("supervisor", research_supervisor_node)
    research_builder.add_node("web_researcher", web_researcher_node)
    research_builder.add_node("data_analyst", data_analyst_node)
    
    research_builder.add_edge(START, "supervisor")
    research_builder.add_edge("web_researcher", "supervisor")
    research_builder.add_edge("data_analyst", "supervisor")
    
    return research_builder.compile()


# ============================================================================
# Content Team Agents
# ============================================================================

def create_content_team(config: AgentConfig) -> StateGraph:
    """Create content team with LLM-based routing"""
    
    @monitor_agent_call("content_supervisor")
    async def content_supervisor_node(state: TeamState) -> Command[Literal["content_writer", "seo_specialist", "__end__"]]:
        """Content team supervisor with LLM routing"""
        # Check iteration limit
        if state.get("iteration_count", 0) >= 2:
            return Command(goto=END)
        
        try:
            # Get routing decision
            decision = await config.content_team_router.route(state)

            # Log routing decision
            monitor = get_global_monitor()
            monitor.record_routing_decision(
                supervisor_name="content_supervisor",
                decision=decision.dict(),
                duration_ms=0
            )
            
            # Update state with decision metadata
            update_data = {
                "iteration_count": state.get("iteration_count", 0) + 1,
                "current_agent": decision.next_node if decision.next_node != "FINISH" else None,
                "routing_decision": decision.dict()
            }

            # Add instructions to messages if present
            if decision.instructions:
                update_data["messages"] = state.get("messages", []) + [HumanMessage(content=decision.instructions, name="supervisor_instructions")]
            
            if decision.should_terminate or decision.next_node == "FINISH":
                return Command(goto=END, update=update_data)
            
            return Command(goto=decision.next_node, update=update_data)
            
        except Exception as e:
            # Fallback to keyword routing
            print(f"Content supervisor routing failed: {e}")
            return _content_fallback_routing(state)
    
    @monitor_agent_call("content_writer")
    async def content_writer_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Content writer agent"""
        try:
            # Extract specific task from supervisor instructions
            original_task = state["messages"][-1].content if state["messages"] else "No task provided"
                
            # Get context from previous messages (e.g. research results)
            context = "\n".join([f"{msg.name}: {msg.content}" for msg in state["messages"] if hasattr(msg, "name") and msg.name not in ["user", "system"]])
            
            # Get content writer model
            llm = config.llm_provider.get_agent_config("content_writer").get_model()
            
            # Create prompt
            system_prompt = config.llm_provider.get_agent_config("content_writer").system_prompt
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Task: {original_task}\n\nContext/Research:\n{context}\n\nPlease create high-quality marketing content based on the above."}
            ]
            
            # Record prompt
            monitor = get_global_monitor()
            formatted_prompt = f"System: {system_prompt}\n\nUser: Task: {original_task}\n\nContext/Research:\n{context}\n\nPlease create high-quality marketing content based on the above."
            monitor.record_agent_prompt("content_writer", formatted_prompt)
            
            # Execute LLM call
            print(f"DEBUG: Content Writer calling LLM for task: {original_task[:50]}...")
            try:
                response = await asyncio.wait_for(llm.ainvoke(messages), timeout=60.0)
                print("DEBUG: Content Writer received response")
                content = response.content
            except asyncio.TimeoutError:
                print("DEBUG: Content Writer timeout")
                content = f"Content outline for {original_task}: (Generation timed out, please refine prompt)"
            
            # Record agent output
            monitor = get_global_monitor()
            monitor.record_agent_output("content_writer", content)
            
            # Create agent response
            response_messages = create_agent_response(
                content=content,
                agent_name="content_writer",
                include_original_task=True,
                original_task=original_task
            )
            
            return Command(
                goto="supervisor",
                update={
                    "messages": response_messages,
                    "task_completed": True,
                    "agent_executed": "content_writer"
                }
            )
            
        except Exception as e:
            print(f"Content writer failed: {e}")
            error_response = f"Content creation failed: {str(e)[:200]}"
            return Command(
                goto="supervisor",
                update={
                    "messages": [AIMessage(content=error_response, name="content_writer")],
                    "task_completed": False,
                    "error": str(e)
                }
            )
    
    @monitor_agent_call("seo_specialist")
    async def seo_specialist_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """SEO specialist agent"""
        try:
            # Extract specific task from supervisor instructions
            original_task = state["messages"][-1].content if state["messages"] else "No task provided"
                
            # Get content to optimize (from last message if possible)
            content_to_optimize = state["messages"][-1].content if state["messages"] else ""
            
            # Get SEO model
            llm = config.llm_provider.get_agent_config("seo_specialist").get_model()
            
            # Create prompt
            system_prompt = config.llm_provider.get_agent_config("seo_specialist").system_prompt
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Task: {original_task}\n\nContent to analyze/optimize:\n{content_to_optimize}\n\nPlease provide SEO analysis and recommendations."}
            ]
            
            # Record prompt
            monitor = get_global_monitor()
            formatted_prompt = f"System: {system_prompt}\n\nUser: Task: {original_task}\n\nContent to analyze/optimize:\n{content_to_optimize}\n\nPlease provide SEO analysis and recommendations."
            monitor.record_agent_prompt("seo_specialist", formatted_prompt)
            
            # Execute LLM call
            print(f"DEBUG: SEO Specialist calling LLM for task: {original_task[:50]}...")
            try:
                response = await asyncio.wait_for(llm.ainvoke(messages), timeout=60.0)
                print("DEBUG: SEO Specialist received response")
                seo_analysis = response.content
            except asyncio.TimeoutError:
                print("DEBUG: SEO Specialist timeout")
                seo_analysis = "Basic SEO Checklist: (Generation timed out)"
            
            # Record agent output
            monitor = get_global_monitor()
            monitor.record_agent_output("seo_specialist", seo_analysis)
            
            # Create agent response
            response_messages = create_agent_response(
                content=seo_analysis,
                agent_name="seo_specialist",
                include_original_task=True,
                original_task=original_task
            )
            
            return Command(
                goto="supervisor",
                update={
                    "messages": response_messages,
                    "task_completed": True,
                    "agent_executed": "seo_specialist"
                }
            )
            
        except Exception as e:
            print(f"SEO specialist failed: {e}")
            error_response = f"SEO analysis failed: {str(e)[:200]}"
            return Command(
                goto="supervisor",
                update={
                    "messages": [AIMessage(content=error_response, name="seo_specialist")],
                    "task_completed": False,
                    "error": str(e)
                }
            )
    
    def _content_fallback_routing(state: TeamState) -> Command[Literal["content_writer", "seo_specialist", "__end__"]]:
        """Fallback routing for content team"""
        if state.get("iteration_count", 0) >= 2:
            return Command(goto=END)
        
        last_message = state["messages"][-1].content.lower() if state["messages"] else ""
        
        # Simple keyword routing
        if "seo" in last_message or "optimize" in last_message or "keyword" in last_message:
            goto = "seo_specialist"
        else:
            goto = "content_writer"
        
        return Command(
            goto=goto,
            update={"iteration_count": state.get("iteration_count", 0) + 1}
        )
    
    # Build content team graph
    content_builder = StateGraph(TeamState)
    content_builder.add_node("supervisor", content_supervisor_node)
    content_builder.add_node("content_writer", content_writer_node)
    content_builder.add_node("seo_specialist", seo_specialist_node)
    
    content_builder.add_edge(START, "supervisor")
    content_builder.add_edge("content_writer", "supervisor")
    content_builder.add_edge("seo_specialist", "supervisor")
    
    return content_builder.compile()


# ============================================================================
# Main Supervisor
# ============================================================================

def create_main_supervisor(config: AgentConfig, checkpointer=None) -> StateGraph:
    """Create main supervisor with LLM-based routing"""
    
    # Create team graphs
    research_team_graph = create_research_team(config)
    content_team_graph = create_content_team(config)
    social_media_team_graph = create_social_media_team(config)
    
    async def call_research_team(state: EnhancedMarketingState) -> Command[Literal["supervisor"]]:
        """Call research team"""
        try:
            # Sanitize messages to prevent nesting
            sanitized_messages = sanitize_messages_for_agent(state["messages"])
            
            response = await research_team_graph.ainvoke({
                "messages": sanitized_messages,
                "team_name": "research_team",
                "iteration_count": 0
            })
            
            # Extract the result from research team
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
    
    async def call_content_team(state: EnhancedMarketingState) -> Command[Literal["supervisor"]]:
        """Call content team"""
        try:
            # Sanitize messages to prevent nesting
            sanitized_messages = sanitize_messages_for_agent(state["messages"])
            
            response = await content_team_graph.ainvoke({
                "messages": sanitized_messages,
                "team_name": "content_team",
                "iteration_count": 0
            })
            
            # Extract the result from content team
            result_message = None
            for msg in reversed(response["messages"]):
                if isinstance(msg, AIMessage) and msg.name in ["content_writer", "seo_specialist"]:
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
            print("DEBUG: CAUGHT GRAPH INTERRUPT IN SUBGRAPH (content_team)")
            raise
        except Exception as e:
            print(f"DEBUG: CAUGHT EXCEPTION IN SUBGRAPH (content_team): {type(e)}")
            monitor = get_global_monitor()
            await monitor.record_event(
                agent_name="content_team",
                event_type="error",
                data={"error": str(e)}
            )
            print(f"Content team failed: {e}")
            return Command(
                goto="supervisor",
                update={
                    "messages": [AIMessage(content=f"Content team error ({type(e).__module__}.{type(e).__name__}): {str(e)[:200]}", name="system")],
                    "current_team": "content_team",
                    "team_result": False,
                    "error": str(e)
                }
            )

    async def call_social_media_team(state: EnhancedMarketingState) -> Command[Literal["supervisor"]]:
        """Call social media team"""
        try:
            # Sanitize messages to prevent nesting
            sanitized_messages = sanitize_messages_for_agent(state["messages"])
            
            response = await social_media_team_graph.ainvoke({
                "messages": sanitized_messages,
                "team_name": "social_media_team",
                "iteration_count": 0
            })
            
            # Extract the result from social media team
            result_message = None
            for msg in reversed(response["messages"]):
                if isinstance(msg, AIMessage) and msg.name in ["publisher", "linkedin_manager", "twitter_manager"]:
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
            # Re-raise GraphInterrupt so it can be handled by the main loop
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
    async def main_supervisor_node(state: EnhancedMarketingState) -> Command[Literal["research_team", "content_team", "social_media_team", "__end__"]]:
        """Main supervisor with LLM routing"""
        # Check iteration limit
        if state.get("iteration_count", 0) >= 3:
            return Command(goto=END, update={"workflow_status": "completed"})
        
        # Check for message nesting
        if detect_message_nesting(state["messages"]):
            print("⚠️  Message nesting detected, resetting messages")
            state["messages"] = reset_message_nesting(state["messages"])
        
        try:
            # Get routing decision from LLM
            decision = await config.main_supervisor_router.route(state)

            # Log routing decision
            monitor = get_global_monitor()
            monitor.record_routing_decision(
                supervisor_name="main_supervisor",
                decision=decision.dict(),
                duration_ms=0
            )
            
            # Update state with decision metadata
            update_data = {
                "iteration_count": state.get("iteration_count", 0) + 1,
                "current_team": decision.next_node if decision.next_node != "FINISH" else None,
                "routing_decision": decision.dict(),
                "routing_confidence": decision.confidence,
                "routing_reasoning": decision.reasoning
            }
            
            if decision.should_terminate or decision.next_node == "FINISH":
                update_data["workflow_status"] = "completed"
                return Command(goto=END, update=update_data)
            
            return Command(goto=decision.next_node, update=update_data)
            
        except Exception as e:
            # Fallback to keyword routing
            print(f"Main supervisor routing failed: {e}")
            return _main_fallback_routing(state)
    
    def _main_fallback_routing(state: EnhancedMarketingState) -> Command[Literal["research_team", "content_team", "social_media_team", "__end__"]]:
        """Fallback routing for main supervisor"""
        if state.get("iteration_count", 0) >= 4:
            return Command(goto=END, update={"workflow_status": "completed"})
        
        last_message = state["messages"][-1].content.lower() if state["messages"] else ""
        
        # Simple keyword routing
        if "research" in last_message or "analyze" in last_message or "data" in last_message:
            goto = "research_team"
        elif "content" in last_message or "write" in last_message or "create" in last_message:
            goto = "content_team"
        elif "social" in last_message or "post" in last_message or "publish" in last_message:
            goto = "social_media_team"
        else:
            # Default to research team for first iteration
            if state.get("iteration_count", 0) >= 1:
                goto = END
                return Command(goto=END, update={
                    "iteration_count": state.get("iteration_count", 0) + 1,
                    "current_team": None,
                    "workflow_status": "completed"
                })
            else:
                goto = "research_team"
        
        return Command(
            goto=goto,
            update={
                "iteration_count": state.get("iteration_count", 0) + 1,
                "current_team": goto if goto != END else None
            }
        )
    
    # Build main supervisor graph
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


# ============================================================================
# Factory Function and Test
# ============================================================================

def create_marketing_workflow(checkpointer=None) -> StateGraph:
    """Create the complete hierarchical marketing workflow"""
    config = AgentConfig()
    return create_main_supervisor(config, checkpointer=checkpointer)


async def test_hierarchical_marketing():
    """Test the hierarchical marketing system"""
    print("=" * 60)
    print("Testing Hierarchical Marketing Agents with LLM Routing")
    print("=" * 60)
    
    # Create workflow and config
    config = AgentConfig()
    workflow = create_main_supervisor(config)
    
    # Test 1: Research task
    print("\n1. Testing research task:")
    print("-" * 40)
    task = "Research AI marketing trends for 2024"
    print(f"Task: {task}")
    
    try:
        result = await workflow.ainvoke({
            "messages": [HumanMessage(content=task)],
            "iteration_count": 0,
            "workflow_status": "running",
            "start_time": datetime.now()
        })
        
        print("\n✅ Research task completed!")
        print(f"Status: {result.get('workflow_status', 'unknown')}")
        print(f"Iterations: {result.get('iteration_count', 0)}")
        print(f"Current team: {result.get('current_team', 'none')}")
        
        # Print messages
        print("\nMessages:")
        for i, msg in enumerate(result.get("messages", [])):
            if hasattr(msg, 'name'):
                print(f"  {i+1}. {msg.name}: {msg.content[:100]}...")
            else:
                print(f"  {i+1}. {msg.content[:100]}...")
        
    except Exception as e:
        print(f"\n❌ Research task failed: {e}")
        return False
    
    # Test 2: Content task
    print("\n\n2. Testing content task:")
    print("-" * 40)
    task = "Create content about GitHub project promotion"
    print(f"Task: {task}")
    
    try:
        result = await workflow.ainvoke({
            "messages": [HumanMessage(content=task)],
            "iteration_count": 0,
            "workflow_status": "running",
            "start_time": datetime.now()
        })
        
        print("\n✅ Content task completed!")
        print(f"Status: {result.get('workflow_status', 'unknown')}")
        print(f"Iterations: {result.get('iteration_count', 0)}")
        print(f"Current team: {result.get('current_team', 'none')}")
        
        # Print messages
        print("\nMessages:")
        for i, msg in enumerate(result.get("messages", [])):
            if hasattr(msg, 'name'):
                print(f"  {i+1}. {msg.name}: {msg.content[:100]}...")
            else:
                print(f"  {i+1}. {msg.content[:100]}...")
        
    except Exception as e:
        print(f"\n❌ Content task failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
    
    # Print tool statistics
    print("\nTool Statistics:")
    stats = config.tool_registry.get_all_stats()
    for tool_name, tool_stats in stats.items():
        if tool_name != "summary":
            print(f"  {tool_name}: {tool_stats.get('call_count', 0)} calls, "
                  f"{tool_stats.get('success_rate', 0)*100:.1f}% success rate")
    
    # Print monitoring summary
    print("\n📊 Monitoring Summary:")
    monitor = get_global_monitor()
    monitor.print_summary()
    
    return True


if __name__ == "__main__":
    import asyncio
    
    print("Starting hierarchical marketing agents test...")
    success = asyncio.run(test_hierarchical_marketing())
    
    if success:
        print("\n🎉 Hierarchical marketing agents are working!")
        print("\nKey improvements implemented:")
        print("1. LLM-based routing with structured JSON output")
        print("2. Proper message processing to prevent nesting")
        print("3. Real search tool integration (Tavily or mock)")
        print("4. Enhanced state management with metadata")
        print("5. Comprehensive error handling and fallbacks")
    else:
        print("\n❌ Some tests failed. Check the errors above.")
# ============================================================================
# Social Media Team Agents
# ============================================================================

def create_social_media_team(config: AgentConfig) -> StateGraph:
    """Create social media team with HITL for publishing"""
    
    @monitor_agent_call("social_media_supervisor")
    async def social_media_supervisor_node(state: TeamState) -> Command[Literal["linkedin_manager", "twitter_manager", "publisher", "__end__"]]:
        """Social media team supervisor with LLM routing"""
        if state.get("iteration_count", 0) >= 3:
            return Command(goto=END)
        
        try:
            decision = await config.social_media_team_router.route(state)
            print(f"DEBUG: Social Media Supervisor Decision: {decision.next_node}")

            monitor = get_global_monitor()
            monitor.record_routing_decision(
                supervisor_name="social_media_supervisor",
                decision=decision.dict(),
                duration_ms=0
            )
            
            update_data = {
                "iteration_count": state.get("iteration_count", 0) + 1,
                "current_agent": decision.next_node if decision.next_node != "FINISH" else None,
                "routing_decision": decision.dict()
            }

            if decision.instructions:
                update_data["messages"] = state.get("messages", []) + [HumanMessage(content=decision.instructions, name="supervisor_instructions")]
            
            if decision.should_terminate or decision.next_node == "FINISH":
                return Command(goto=END, update=update_data)
            
            return Command(goto=decision.next_node, update=update_data)
            
        except Exception as e:
            print(f"Social media supervisor routing failed: {e}")
            # Fallback to publisher if content exists, otherwise finish
            return Command(goto="publisher", update={"iteration_count": state.get("iteration_count", 0) + 1})

    @monitor_agent_call("linkedin_manager")
    async def linkedin_manager_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """LinkedIn Manager Agent"""
        monitor = get_global_monitor()
        try:
            original_task = state["messages"][-1].content if state["messages"] else "No task provided"
            context = "\n".join([f"{msg.name}: {msg.content}" for msg in state["messages"] if hasattr(msg, "name") and msg.name not in ["user", "system"]])
            
            # Using content writer model for now
            llm = config.llm_provider.get_agent_config("content_writer").get_model() 
            
            prompt = f"You are a LinkedIn Manager. Create a professional LinkedIn post based on:\nTask: {original_task}\nContext: {context}"
            monitor.record_agent_prompt("linkedin_manager", prompt)
            
            response = await asyncio.wait_for(llm.ainvoke([{"role": "user", "content": prompt}]), timeout=60.0)
            content = response.content
            
            monitor.record_agent_output("linkedin_manager", content)
            
            return Command(
                goto="supervisor",
                update={
                    "messages": create_agent_response(content, "linkedin_manager", True, original_task),
                    "task_completed": True
                }
            )
        except Exception as e:
            return Command(goto="supervisor", update={"error": str(e)})

    @monitor_agent_call("twitter_manager")
    async def twitter_manager_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Twitter Manager Agent"""
        monitor = get_global_monitor()
        try:
            original_task = state["messages"][-1].content if state["messages"] else "No task provided"
            context = "\n".join([f"{msg.name}: {msg.content}" for msg in state["messages"] if hasattr(msg, "name") and msg.name not in ["user", "system"]])
            
            llm = config.llm_provider.get_agent_config("content_writer").get_model()
            
            prompt = f"You are a Twitter Manager. Create a threaded tweet based on:\nTask: {original_task}\nContext: {context}"
            monitor.record_agent_prompt("twitter_manager", prompt)
            
            response = await asyncio.wait_for(llm.ainvoke([{"role": "user", "content": prompt}]), timeout=60.0)
            content = response.content
            
            monitor.record_agent_output("twitter_manager", content)
            
            return Command(
                goto="supervisor",
                update={
                    "messages": create_agent_response(content, "twitter_manager", True, original_task),
                    "task_completed": True
                }
            )
        except Exception as e:
            return Command(goto="supervisor", update={"error": str(e)})

    @monitor_agent_call("publisher")
    async def publisher_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Publisher Agent - Executes after human approval"""
        monitor = get_global_monitor()
        
        # Get content to publish (from last manager message)
        content_to_publish = "No content found"
        platform = "Unknown"
        
        for msg in reversed(state["messages"]):
            if hasattr(msg, "name") and msg.name in ["linkedin_manager", "twitter_manager"]:
                content_to_publish = msg.content
                platform = "LinkedIn" if msg.name == "linkedin_manager" else "Twitter"
                break
        
        print(f"DEBUG: Publisher executing for {platform}...")

        # NOTE: This node runs AFTER the graph has been resumed from an interrupt.
        # The interrupt logic is handled by 'interrupt_before=["publisher"]' in compile().
        
        result = ""
        try:
            if platform == "LinkedIn":
                # Use the LinkedIn Tool
                from app.utils.config_loader import GLOBAL_TOOL_REGISTRY
                tool = GLOBAL_TOOL_REGISTRY.get_tool("linkedin_post")
                
                if tool:
                    # Execute tool
                    result = await tool.execute(content_to_publish)
                else:
                    result = "❌ Error: LinkedIn tool not found in registry."
            else:
                # Mock for Twitter
                result = f"✅ (Mock) Successfully published to {platform}!"

        except Exception as e:
            result = f"❌ Publishing exception: {str(e)}"

        monitor.record_agent_output("publisher", result)
        
        return Command(
            goto="supervisor", 
            update={
                "messages": [AIMessage(content=result, name="publisher")],
                "task_completed": "✅ Success" in result
            }
        )

    # Build social media team graph
    builder = StateGraph(TeamState)
    builder.add_node("supervisor", social_media_supervisor_node)
    builder.add_node("linkedin_manager", linkedin_manager_node)
    builder.add_node("twitter_manager", twitter_manager_node)
    builder.add_node("publisher", publisher_node)
    
    builder.add_edge(START, "supervisor")
    builder.add_edge("linkedin_manager", "supervisor")
    builder.add_edge("twitter_manager", "supervisor")
    builder.add_edge("publisher", "supervisor")
    
    # Enable HITL by interrupting before the publisher node runs
    return builder.compile(interrupt_before=["publisher"])
