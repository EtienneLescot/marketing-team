#!/usr/bin/env python3
"""
Enhanced state models for LLM-based routing with structured JSON output.
Updated with proper task delegation support.
"""

from typing import TypedDict, Optional, Dict, Any, List, Literal, Annotated
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import operator


# ============================================================================
# Pydantic Models for Structured Routing
# ============================================================================

class RoutingDecision(BaseModel):
    """Base model for routing decisions"""
    next_node: str = Field(description="Next node to route to")
    reasoning: str = Field(description="Reasoning for the decision")
    instructions: str = Field(description="Specific, actionable instructions for the next agent to execute")
    confidence: float = Field(description="Confidence score (0-1)", ge=0, le=1)
    should_terminate: bool = Field(
        description="Whether to terminate the workflow", 
        default=False
    )


class MainSupervisorDecision(RoutingDecision):
    """Routing decision for main supervisor"""
    next_node: Literal[
        "research_team", 
        "content_team", 
        "social_media_team", 
        "strategy_agent", 
        "FINISH"
    ]


class ResearchTeamDecision(RoutingDecision):
    """Routing decision for research team supervisor"""
    next_node: Literal["web_researcher", "data_analyst", "FINISH"]


class ContentTeamDecision(RoutingDecision):
    """Routing decision for content team supervisor"""
    next_node: Literal["content_writer", "seo_specialist", "visual_designer", "FINISH"]


class SocialMediaTeamDecision(RoutingDecision):
    """Routing decision for social media team supervisor"""
    next_node: Literal["linkedin_manager", "twitter_manager", "publisher", "FINISH"]


# ============================================================================
# Enhanced State Classes with Task Delegation Support
# ============================================================================

class TaskDelegationState(MessagesState):
    """State with task delegation support for hierarchical agent systems"""
    
    # Core task information
    original_task: str = Field(description="The original user task")
    current_task: str = Field(description="Current task being worked on")
    task_status: str = Field(description="Status of current task", default="pending")
    
    # Task delegation tracking
    parent_agent: Optional[str] = Field(description="Agent that delegated this task", default=None)
    delegated_by: Optional[str] = Field(description="Name of agent that delegated this task", default=None)
    subtasks: Annotated[List[Dict[str, Any]], operator.add] = Field(description="List of subtasks created from the main task", default_factory=list)
    current_subtask_index: int = Field(description="Index of current subtask being worked on", default=0)
    
    # Agent tracking
    current_agent: Optional[str] = Field(description="Current agent working on the task", default=None)
    agent_history: Annotated[List[Dict[str, Any]], operator.add] = Field(description="History of agent executions", default_factory=list)
    
    # Workflow metadata
    workflow_id: Optional[str] = Field(description="Unique workflow ID", default=None)
    iteration_count: Annotated[int, operator.add] = Field(description="Number of iterations", default=0)
    max_iterations: int = Field(description="Maximum iterations allowed", default=10)
    
    # Results tracking
    results: Annotated[List[Dict[str, Any]], operator.add] = Field(description="Results from agent executions", default_factory=list)
    final_result: Optional[str] = Field(description="Final synthesized result", default=None)
    
    # Performance metrics
    start_time: Optional[datetime] = Field(description="Workflow start time", default=None)
    total_agent_calls: Annotated[int, operator.add] = Field(description="Total agent calls", default=0)
    total_tool_calls: Annotated[int, operator.add] = Field(description="Total tool calls", default=0)
    
    def get_current_subtask(self) -> Optional[Dict[str, Any]]:
        """Get the current subtask being worked on"""
        if self.subtasks and self.current_subtask_index < len(self.subtasks):
            return self.subtasks[self.current_subtask_index]
        return None
    
    def add_subtask(self, description: str, assigned_to: str, dependencies: List[str] = None) -> Dict[str, Any]:
        """Add a new subtask"""
        subtask = {
            "id": len(self.subtasks),
            "description": description,
            "assigned_to": assigned_to,
            "status": "pending",
            "dependencies": dependencies or [],
            "result": None,
            "created_at": datetime.now().isoformat()
        }
        self.subtasks.append(subtask)
        return subtask
    
    def mark_subtask_complete(self, subtask_id: int, result: str):
        """Mark a subtask as complete"""
        if subtask_id < len(self.subtasks):
            self.subtasks[subtask_id]["status"] = "completed"
            self.subtasks[subtask_id]["result"] = result
            self.subtasks[subtask_id]["completed_at"] = datetime.now().isoformat()
    
    def get_pending_subtasks(self) -> List[Dict[str, Any]]:
        """Get all pending subtasks"""
        return [st for st in self.subtasks if st["status"] == "pending"]
    
    def get_completed_subtasks(self) -> List[Dict[str, Any]]:
        """Get all completed subtasks"""
        return [st for st in self.subtasks if st["status"] == "completed"]
    
    def can_proceed_to_next_subtask(self) -> bool:
        """Check if we can proceed to the next subtask"""
        current = self.get_current_subtask()
        if not current:
            return False
        
        # Check if all dependencies are satisfied
        for dep_id in current.get("dependencies", []):
            if dep_id < len(self.subtasks) and self.subtasks[dep_id]["status"] != "completed":
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = dict(self)
        
        # Handle datetime serialization
        if data.get("start_time"):
            data["start_time"] = data["start_time"].isoformat()
        
        # Handle subtasks datetime fields
        for subtask in data.get("subtasks", []):
            for key in ["created_at", "completed_at"]:
                if key in subtask and isinstance(subtask[key], datetime):
                    subtask[key] = subtask[key].isoformat()
        
        return data


class TeamDelegationState(TaskDelegationState):
    """State for team-level task delegation"""
    team_name: str = Field(description="Name of the team")
    team_members: List[str] = Field(description="List of team member agents")
    team_supervisor: str = Field(description="Name of team supervisor")
    
    def get_available_members(self) -> List[str]:
        """Get available team members (excluding supervisor)"""
        return [m for m in self.team_members if m != self.team_supervisor]


# ============================================================================
# Handoff Tool Models
# ============================================================================

class HandoffToolMetadata(BaseModel):
    """Metadata for handoff tools"""
    agent_name: str = Field(description="Name of agent to handoff to")
    tool_name: str = Field(description="Name of the handoff tool")
    description: str = Field(description="Description of when to use this tool")
    requires_task_description: bool = Field(description="Whether task description is required", default=True)


class HandoffRequest(BaseModel):
    """Request for handing off a task to another agent"""
    task_description: str = Field(description="Detailed description of what the next agent should do, including all relevant context")
    priority: Literal["low", "medium", "high"] = Field(description="Priority of the task", default="medium")
    expected_output: Optional[str] = Field(description="Expected output format or requirements", default=None)


# ============================================================================
# Error Models
# ============================================================================

class ErrorSeverity(str, Enum):
    """Error severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories"""
    LLM_ERROR = "llm_error"
    API_ERROR = "api_error"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    CONFIGURATION_ERROR = "configuration_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    AUTHORIZATION_ERROR = "authorization_error"
    RESOURCE_ERROR = "resource_error"
    UNKNOWN_ERROR = "unknown_error"


class SystemError(Exception):
    """Base system error with enhanced metadata"""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        component: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
        retryable: bool = True,
        suggested_action: Optional[str] = None
    ):
        self.message = message
        self.category = category
        self.severity = severity
        self.component = component
        self.operation = operation
        self.context = context or {}
        self.original_exception = original_exception
        self.retryable = retryable
        self.suggested_action = suggested_action
        
        super().__init__(self.__str__())
    
    def __str__(self) -> str:
        """Enhanced string representation"""
        base = f"[{self.category.value}] {self.message}"
        if self.component:
            base = f"{base} (component: {self.component})"
        if self.operation:
            base = f"{base} (operation: {self.operation})"
        return base
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "component": self.component,
            "operation": self.operation,
            "context": self.context,
            "retryable": self.retryable,
            "suggested_action": self.suggested_action,
            "timestamp": datetime.now().isoformat(),
            "original_exception": str(self.original_exception) if self.original_exception else None
        }


# Specialized error types
class LLMError(SystemError):
    """LLM-related errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.LLM_ERROR, **kwargs)


class APIError(SystemError):
    """External API errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.API_ERROR, **kwargs)


class RateLimitError(APIError):
    """Rate limit errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)
        self.retryable = True
        self.suggested_action = "Wait before retrying or use alternative provider"


class TimeoutError(SystemError):
    """Timeout errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.TIMEOUT_ERROR, **kwargs)
        self.retryable = True


class ValidationError(SystemError):
    """Validation errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.VALIDATION_ERROR, **kwargs)
        self.retryable = False
