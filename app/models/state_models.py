#!/usr/bin/env python3
"""
Enhanced state models for LLM-based routing with structured JSON output.
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
# Enhanced State Classes
# ============================================================================

class EnhancedMarketingState(MessagesState):
    """Enhanced state with routing metadata and persistence support"""
    
    # Core workflow metadata
    workflow_id: Optional[str] = None
    user_id: Optional[str] = None
    workflow_status: str = "running"
    
    # Routing metadata
    current_team: Optional[str] = None
    task_status: str = "pending"
    iteration_count: Annotated[int, operator.add] = 0
    
    # Persistence tracking
    last_checkpoint: Optional[str] = None
    checkpoint_count: Annotated[int, operator.add] = 0
    persistence_enabled: bool = True
    
    # Execution metadata
    start_time: Optional[datetime] = None
    agent_execution_history: Annotated[List[Dict[str, Any]], operator.add] = []
    routing_decision_history: Annotated[List[Dict[str, Any]], operator.add] = []
    
    # Performance metrics
    total_agent_calls: Annotated[int, operator.add] = 0
    total_tool_calls: Annotated[int, operator.add] = 0
    estimated_cost: Annotated[float, operator.add] = 0.0
    
    # Error tracking
    error_count: Annotated[int, operator.add] = 0
    last_error: Optional[str] = None
    
    @property
    def average_confidence(self) -> float:
        """Calculate average confidence of routing decisions"""
        if not self.routing_decision_history:
            return 0.0
        
        confidences = [
            decision.get("confidence", 0.0)
            for decision in self.routing_decision_history
            if "confidence" in decision
        ]
        
        if not confidences:
            return 0.0
        
        return sum(confidences) / len(confidences)
    
    def to_persistable_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for persistence"""
        # Exclude non-serializable fields
        exclude_fields = {'messages'}  # Messages are handled separately
        
        data = {}
        for key, value in self.items():
            if key in exclude_fields:
                continue
            
            # Handle datetime serialization
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            else:
                data[key] = value
        
        # Add messages separately with proper serialization
        if 'messages' in self:
            from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
            
            data['messages'] = []
            for msg in self['messages']:
                msg_dict = {
                    'type': msg.__class__.__name__,
                    'content': msg.content,
                }
                
                # Add optional fields
                if hasattr(msg, 'name') and msg.name:
                    msg_dict['name'] = msg.name
                
                if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs:
                    msg_dict['additional_kwargs'] = msg.additional_kwargs
                
                data['messages'].append(msg_dict)
        
        return data
    
    @classmethod
    def from_persistable_dict(cls, data: Dict[str, Any]) -> 'EnhancedMarketingState':
        """Create state from persisted dictionary"""
        # Handle message deserialization
        messages = []
        if 'messages' in data:
            from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
            
            message_map = {
                'HumanMessage': HumanMessage,
                'AIMessage': AIMessage,
                'SystemMessage': SystemMessage
            }
            
            for msg_data in data['messages']:
                msg_class = message_map.get(msg_data['type'], HumanMessage)
                
                # Extract message arguments
                kwargs = {'content': msg_data['content']}
                
                if 'name' in msg_data:
                    kwargs['name'] = msg_data['name']
                
                if 'additional_kwargs' in msg_data:
                    kwargs['additional_kwargs'] = msg_data['additional_kwargs']
                
                messages.append(msg_class(**kwargs))
            
            data['messages'] = messages
        
        # Handle datetime deserialization
        datetime_fields = ['start_time']
        for field in datetime_fields:
            if field in data and data[field]:
                data[field] = datetime.fromisoformat(data[field])
        
        return cls(**data)


class TeamState(MessagesState):
    """State for specialized teams"""
    team_name: str
    iteration_count: Annotated[int, operator.add] = 0
    current_agent: Optional[str] = None
    task_completed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return dict(self)


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
        self.suggested_action = "Check input data and fix validation issues"