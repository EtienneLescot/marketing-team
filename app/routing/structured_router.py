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
        
        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=self._create_system_prompt()),
            HumanMessage(content="{task_description}")
        ])
        
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

Your task is to analyze the current task and decide which node should handle it next.

{format_instructions}

Important rules:
1. Only route to nodes that are in the available nodes list
2. Use FINISH when the task is complete or no further processing is needed
3. Provide clear reasoning for your decision
4. Include a confidence score between 0 and 1
5. Set should_terminate=True only when the entire workflow should end

Example output format:
{{
    "next_node": "research_team",
    "reasoning": "The task requires market research and competitor analysis",
    "confidence": 0.85,
    "should_terminate": false
}}"""
    
    async def route(self, state: Dict[str, Any]) -> T:
        """Route based on current state"""
        self.call_count += 1
        
        # Extract task description from state
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
            # Get LLM response
            chain = self.prompt | self.llm | self.parser
            decision = await chain.ainvoke({"task_description": task_description})
            
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
        research_keywords = ['research', 'analyze', 'data', 'market', 'trend', 'competitor']
        content_keywords = ['content', 'write', 'blog', 'article', 'create', 'draft']
        social_keywords = ['social', 'media', 'post', 'tweet', 'linkedin', 'twitter']
        
        if any(keyword in task_lower for keyword in research_keywords):
            # Route to first available research node
            research_nodes = [n for n in self.available_nodes if 'research' in n.lower() or 'analyst' in n.lower()]
            next_node = research_nodes[0] if research_nodes else self.available_nodes[0]
        elif any(keyword in task_lower for keyword in content_keywords):
            # Route to first available content node
            content_nodes = [n for n in self.available_nodes if 'content' in n.lower() or 'writer' in n.lower()]
            next_node = content_nodes[0] if content_nodes else self.available_nodes[0]
        elif any(keyword in task_lower for keyword in social_keywords):
            # Route to first available social media node
            social_nodes = [n for n in self.available_nodes if 'social' in n.lower() or 'media' in n.lower()]
            next_node = social_nodes[0] if social_nodes else self.available_nodes[0]
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
    available_nodes = ["research_team", "content_team", "social_media_team", "strategy_agent"]
    return StructuredRouter(
        llm=llm,
        decision_model=MainSupervisorDecision,
        available_nodes=available_nodes,
        max_iterations=3
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