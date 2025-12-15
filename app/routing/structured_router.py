#!/usr/bin/env python3
"""
Structured router with JSON output handling for LLM-based routing decisions.
"""

import json
import re
from typing import Type, TypeVar, List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, ValidationError as PydanticValidationError

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel

from app.models.state_models import (
    RoutingDecision, 
    MainSupervisorDecision,
    ResearchTeamDecision,
    ContentTeamDecision,
    SocialMediaTeamDecision,
    SystemError,
    ErrorCategory
)

T = TypeVar('T', bound=RoutingDecision)


class JSONOutputValidator:
    """Validate and sanitize JSON outputs from LLMs"""
    
    def __init__(self, schema: Optional[Dict[str, Any]] = None):
        self.schema = schema
    
    def validate_and_fix(self, json_str: str) -> Dict[str, Any]:
        """Validate JSON and attempt to fix common issues"""
        
        # Try to parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Attempt to fix common JSON issues
            fixed_json = self._fix_json_issues(json_str)
            try:
                data = json.loads(fixed_json)
            except json.JSONDecodeError:
                raise SystemError(
                    message=f"Invalid JSON output from LLM: {e}",
                    category=ErrorCategory.VALIDATION_ERROR,
                    component="JSONOutputValidator",
                    operation="validate_and_fix",
                    context={"original_json": json_str[:500]},
                    retryable=True
                )
        
        return data
    
    def _fix_json_issues(self, json_str: str) -> str:
        """Fix common JSON issues"""
        # Remove markdown code blocks
        json_str = json_str.replace("```json", "").replace("```", "")
        
        # Fix trailing commas
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # Fix missing quotes around keys (simple pattern)
        # Match word characters followed by colon, not already quoted
        json_str = re.sub(r'(\b\w+\b):', r'"\1":', json_str)
        
        # Fix single quotes to double quotes
        json_str = json_str.replace("'", '"')
        
        # Remove any leading/trailing whitespace
        json_str = json_str.strip()
        
        return json_str


class StructuredRouter:
    """Factory for creating LLM-based routers with structured output"""
    
    def __init__(
        self,
        llm: BaseChatModel,
        decision_model: Type[T],
        available_nodes: List[str],
        max_iterations: int = 5
    ):
        self.llm = llm
        self.decision_model = decision_model
        self.available_nodes = available_nodes
        self.max_iterations = max_iterations
        
        # Create output parser
        self.parser = PydanticOutputParser(pydantic_object=decision_model)
        
        # JSON validator
        self.validator = JSONOutputValidator()
        
        # Statistics
        self.call_count = 0
        self.success_count = 0
        self.fallback_count = 0
    
    def _create_system_prompt(self) -> str:
        """Create system prompt with available nodes and format instructions"""
        format_instructions = self.parser.get_format_instructions()
        
        return f"""You are a routing supervisor for a hierarchical marketing agent system.

Available nodes to route to: {', '.join(self.available_nodes)}

Your task is to analyze the CURRENT STATE and decide which node should handle it next.

CRITICAL GUIDANCE FOR COMPLEX TASKS:
1. **High-level tasks** (e.g., "promote my product", "create marketing plan", "launch campaign") require MULTIPLE teams working in sequence
2. **Typical workflow for complex tasks**: research_team → content_team → social_media_team
3. **Research tasks**: Market analysis, competitor research, data gathering, trend analysis
4. **Content tasks**: Writing, SEO optimization, visual design, content creation
5. **Social media tasks**: Publishing, scheduling, engagement, analytics
6. **Strategy tasks**: Planning, coordination, multi-phase execution

DECISION GUIDELINES:
- **Analyze what's been done**: Check if research has been completed (look for web_researcher or data_analyst in messages)
- **If research is done**: Route to content_team for content creation
- **If content is done**: Route to social_media_team for publishing
- **If all phases are complete**: Route to FINISH with should_terminate=True

SPECIFIC RULES:
1. If task mentions "promote", "market", "launch", "campaign" AND no research has been done → Start with research_team
2. If research results are present in messages → Route to content_team
3. If content has been created → Route to social_media_team
4. If social media planning is done → Route to FINISH

{format_instructions}

Important rules:
1. Only route to nodes that are in the available nodes list
2. Use FINISH when the current phase is complete (not necessarily the entire task)
3. Provide clear reasoning for your decision, including what's been done so far
4. Include a confidence score between 0 and 1
5. Set should_terminate=True ONLY when the ENTIRE multi-phase task is complete

Example output for complex task "Promote my GitHub repository" AFTER research:
{{
    "next_node": "content_team",
    "reasoning": "Research phase completed (web_researcher provided search results). Now need content creation phase: write blog posts, create social media content based on research findings",
    "confidence": 0.9,
    "should_terminate": false
}}"""
    
    async def route(self, state: Dict[str, Any]) -> T:
        """Route based on current state"""
        self.call_count += 1
        
        # Extract task description and analyze what's been done
        messages = state.get("messages", [])
        if messages:
            # Get the last human message (original task)
            human_messages = [
                msg for msg in messages
                if hasattr(msg, 'type') and msg.type == 'human'
            ]
            if human_messages:
                task_description = human_messages[-1].content
            else:
                task_description = messages[-1].content
        else:
            task_description = state.get("task", "")
        
        # Analyze what agents have already worked on the task
        agents_worked = []
        for msg in messages:
            if hasattr(msg, 'name') and msg.name:
                agents_worked.append(msg.name)
        
        # Get unique agents
        unique_agents = list(set(agents_worked))
        work_summary = f"Agents that have worked on this task: {', '.join(unique_agents) if unique_agents else 'None'}"
        
        # Check iteration limit
        iteration_count = state.get("iteration_count", 0)
        if iteration_count >= self.max_iterations:
            return self.decision_model(
                next_node="FINISH",
                reasoning=f"Max iterations reached ({self.max_iterations})",
                confidence=1.0,
                should_terminate=True
            )
        
        try:
            # Get LLM response with context about what's been done
            context = {
                "task_description": task_description,
                "work_summary": work_summary,
                "iteration_count": iteration_count,
                "available_nodes": ', '.join(self.available_nodes)
            }
            
            # Create a more detailed prompt
            detailed_prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=self._create_system_prompt()),
                HumanMessage(content=f"""Task: {task_description}

Current State:
- {work_summary}
- Iteration: {iteration_count + 1} of {self.max_iterations}
- Available next steps: {', '.join(self.available_nodes)}

Based on what's been done so far, what should happen next?""")
            ])
            
            chain = detailed_prompt | self.llm | self.parser
            decision = await chain.ainvoke({})
            
            # Validate the decision
            self._validate_decision(decision)
            
            self.success_count += 1
            return decision
            
        except Exception as e:
            # Fallback to keyword-based routing
            self.fallback_count += 1
            return self._fallback_routing(task_description, e)
    
    def _validate_decision(self, decision: T):
        """Validate routing decision"""
        # Check if selected node is valid
        if decision.next_node != "FINISH" and decision.next_node not in self.available_nodes:
            raise SystemError(
                message=f"Invalid node selected: {decision.next_node}",
                category=ErrorCategory.VALIDATION_ERROR,
                component="StructuredRouter",
                operation="validate_decision",
                context={
                    "selected_node": decision.next_node,
                    "available_nodes": self.available_nodes
                },
                retryable=True
            )
        
        # Check confidence bounds
        if not 0 <= decision.confidence <= 1:
            raise SystemError(
                message=f"Confidence out of bounds: {decision.confidence}",
                category=ErrorCategory.VALIDATION_ERROR,
                component="StructuredRouter",
                operation="validate_decision",
                context={"confidence": decision.confidence},
                retryable=True
            )
    
    def _fallback_routing(self, task_description: str, error: Exception) -> T:
        """Fallback routing when LLM fails"""
        task_lower = task_description.lower()
        
        # Simple keyword matching
        next_node = "FINISH"  # Default to finish
        
        # Check for keywords to determine routing
        research_keywords = ['research', 'analyze', 'data', 'market', 'trend', 'competitor', 'study', 'investigate']
        content_keywords = ['content', 'write', 'blog', 'article', 'create', 'draft', 'post', 'seo', 'optimize']
        
        if any(keyword in task_lower for keyword in research_keywords):
            # Route to research_team if available, otherwise first available node
            if "research_team" in self.available_nodes:
                next_node = "research_team"
            else:
                next_node = self.available_nodes[0] if self.available_nodes else "FINISH"
        elif any(keyword in task_lower for keyword in content_keywords):
            # Route to content_team if available, otherwise first available node
            if "content_team" in self.available_nodes:
                next_node = "content_team"
            else:
                next_node = self.available_nodes[0] if self.available_nodes else "FINISH"
        else:
            # Default to first available node
            next_node = self.available_nodes[0] if self.available_nodes else "FINISH"
        
        return self.decision_model(
            next_node=next_node,
            reasoning=f"Fallback routing: LLM routing failed ({str(error)[:100]})",
            confidence=0.5,
            should_terminate=False
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics"""
        success_rate = self.success_count / max(self.call_count, 1)
        fallback_rate = self.fallback_count / max(self.call_count, 1)
        
        return {
            "call_count": self.call_count,
            "success_count": self.success_count,
            "fallback_count": self.fallback_count,
            "success_rate": success_rate,
            "fallback_rate": fallback_rate,
            "available_nodes": self.available_nodes,
            "max_iterations": self.max_iterations
        }


# Factory functions for creating specific routers
def create_main_supervisor_router(llm: BaseChatModel) -> StructuredRouter:
    """Create router for main supervisor"""
    # Include all teams for proper routing of complex tasks
    # Note: social_media_team and strategy_agent are not fully implemented yet
    # but are included so the router can plan the complete workflow
    available_nodes = ["research_team", "content_team", "social_media_team", "strategy_agent", "FINISH"]
    return StructuredRouter(
        llm=llm,
        decision_model=MainSupervisorDecision,
        available_nodes=available_nodes,
        max_iterations=5  # Increased for complex multi-phase tasks
    )


def create_research_team_router(llm: BaseChatModel) -> StructuredRouter:
    """Create router for research team supervisor"""
    available_nodes = ["web_researcher", "data_analyst"]
    return StructuredRouter(
        llm=llm,
        decision_model=ResearchTeamDecision,
        available_nodes=available_nodes,
        max_iterations=2
    )


def create_content_team_router(llm: BaseChatModel) -> StructuredRouter:
    """Create router for content team supervisor"""
    available_nodes = ["content_writer", "seo_specialist", "visual_designer"]
    return StructuredRouter(
        llm=llm,
        decision_model=ContentTeamDecision,
        available_nodes=available_nodes,
        max_iterations=2
    )


def create_social_media_team_router(llm: BaseChatModel) -> StructuredRouter:
    """Create router for social media team supervisor"""
    available_nodes = ["linkedin_manager", "twitter_manager", "analytics_tracker"]
    return StructuredRouter(
        llm=llm,
        decision_model=SocialMediaTeamDecision,
        available_nodes=available_nodes,
        max_iterations=2
    )