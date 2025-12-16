from pydantic import BaseModel, Field
from typing import Literal

class RouterResponse(BaseModel):
    """Schema for routing decisions"""
    next_node: str = Field(description="The name of the next agent")
    reasoning: str = Field(description="Explanation for the routing decision")
    confidence: float = Field(description="Confidence score between 0 and 1")
    should_terminate: bool = Field(description="True if the task is complete and no further processing is needed")
