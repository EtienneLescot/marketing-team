# LLM-Based Routing Design with Structured JSON Output

## Overview
This document outlines the design for implementing intelligent LLM-based routing in the hierarchical marketing agents system, replacing the current keyword-based routing with proper structured JSON output handling.

## Current Limitations
1. **Keyword-based routing**: Limited to simple string matching
2. **No reasoning**: Decisions lack explanation or context
3. **No fallback**: No graceful degradation when keywords don't match
4. **Limited flexibility**: Cannot handle complex multi-step workflows

## Design Goals
1. **Intelligent routing**: LLM-based decisions with reasoning
2. **Structured output**: Consistent JSON format for reliable parsing
3. **Fallback mechanisms**: Graceful degradation when LLM fails
4. **Multi-provider support**: OpenAI, Anthropic, OpenRouter, etc.
5. **Cost optimization**: Use appropriate models for each routing level

## Architecture

### 1. Routing Decision Models

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class RoutingDecision(BaseModel):
    """Base model for routing decisions"""
    next_node: str = Field(description="Next node to route to")
    reasoning: str = Field(description="Reasoning for the decision")
    confidence: float = Field(description="Confidence score (0-1)", ge=0, le=1)
    should_terminate: bool = Field(description="Whether to terminate the workflow", default=False)

class MainSupervisorDecision(RoutingDecision):
    """Routing decision for main supervisor"""
    next_node: Literal["research_team", "content_team", "social_media_team", "strategy_agent", "FINISH"]

class ResearchTeamDecision(RoutingDecision):
    """Routing decision for research team supervisor"""
    next_node: Literal["web_researcher", "data_analyst", "FINISH"]

class ContentTeamDecision(RoutingDecision):
    """Routing decision for content team supervisor"""
    next_node: Literal["content_writer", "seo_specialist", "visual_designer", "FINISH"]

class SocialMediaTeamDecision(RoutingDecision):
    """Routing decision for social media team supervisor"""
    next_node: Literal["linkedin_manager", "twitter_manager", "analytics_tracker", "FINISH"]
```

### 2. Structured LLM Router Factory

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from typing import Type, TypeVar, List

T = TypeVar('T', bound=RoutingDecision)

class StructuredRouter:
    """Factory for creating LLM-based routers with structured output"""
    
    def __init__(self, llm, decision_model: Type[T], available_nodes: List[str]):
        self.llm = llm
        self.decision_model = decision_model
        self.available_nodes = available_nodes
        
        # Create output parser
        self.parser = PydanticOutputParser(pydantic_object=decision_model)
        
        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=self._create_system_prompt()),
            HumanMessage(content="{task_description}")
        ])
    
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
    
    async def route(self, state: dict) -> T:
        """Route based on current state"""
        # Extract task description from state
        messages = state.get("messages", [])
        if messages:
            task_description = messages[-1].content
        else:
            task_description = state.get("task", "")
        
        # Get LLM response
        chain = self.prompt | self.llm | self.parser
        try:
            decision = await chain.ainvoke({"task_description": task_description})
            return decision
        except Exception as e:
            # Fallback to keyword-based routing
            return self._fallback_routing(task_description)
    
    def _fallback_routing(self, task_description: str) -> T:
        """Fallback routing when LLM fails"""
        # Simple keyword-based fallback
        task_lower = task_description.lower()
        
        # Default to first available node
        next_node = self.available_nodes[0] if self.available_nodes else "FINISH"
        
        # Simple keyword matching
        for node in self.available_nodes:
            if node in task_lower:
                next_node = node
                break
        
        return self.decision_model(
            next_node=next_node,
            reasoning="Fallback routing: LLM routing failed, using keyword matching",
            confidence=0.5,
            should_terminate=False
        )
```

### 3. Enhanced Supervisor Nodes

```python
from langgraph.types import Command
from typing import Literal

def create_llm_supervisor_node(
    llm,
    available_nodes: List[str],
    decision_model: Type[RoutingDecision],
    max_iterations: int = 5
):
    """Create a supervisor node with LLM-based routing"""
    
    router = StructuredRouter(llm, decision_model, available_nodes)
    
    async def supervisor_node(state: dict) -> Command:
        """Enhanced supervisor with LLM routing"""
        
        # Check iteration limit
        iteration_count = state.get("iteration_count", 0)
        if iteration_count >= max_iterations:
            return Command(
                goto=END,
                update={
                    "termination_reason": "Max iterations reached",
                    "iteration_count": iteration_count + 1
                }
            )
        
        # Get routing decision
        decision = await router.route(state)
        
        # Update state with decision metadata
        update_data = {
            "iteration_count": iteration_count + 1,
            "last_routing_decision": decision.dict(),
            "routing_history": state.get("routing_history", []) + [decision.dict()]
        }
        
        # Handle termination
        if decision.should_terminate or decision.next_node == "FINISH":
            return Command(
                goto=END,
                update=update_data
            )
        
        # Route to next node
        return Command(
            goto=decision.next_node,
            update=update_data
        )
    
    return supervisor_node
```

### 4. Multi-Level Routing Configuration

```python
from agent_config import agent_config

def create_routing_configuration():
    """Create routing configuration for all levels"""
    
    config = {
        "main_supervisor": {
            "llm": agent_config.get_agent_config("main_supervisor").get_model(),
            "available_nodes": ["research_team", "content_team", "social_media_team", "strategy_agent"],
            "decision_model": MainSupervisorDecision,
            "max_iterations": 3
        },
        "research_team_supervisor": {
            "llm": agent_config.get_agent_config("research_team_supervisor").get_model(),
            "available_nodes": ["web_researcher", "data_analyst"],
            "decision_model": ResearchTeamDecision,
            "max_iterations": 2
        },
        "content_team_supervisor": {
            "llm": agent_config.get_agent_config("content_team_supervisor").get_model(),
            "available_nodes": ["content_writer", "seo_specialist", "visual_designer"],
            "decision_model": ContentTeamDecision,
            "max_iterations": 2
        },
        "social_media_team_supervisor": {
            "llm": agent_config.get_agent_config("social_media_team_supervisor").get_model(),
            "available_nodes": ["linkedin_manager", "twitter_manager", "analytics_tracker"],
            "decision_model": SocialMediaTeamDecision,
            "max_iterations": 2
        }
    }
    
    return config
```

### 5. Enhanced State with Routing Metadata

```python
from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import MessagesState

class EnhancedMarketingState(MessagesState):
    """Enhanced state with routing metadata"""
    current_team: Optional[str] = None
    task_status: str = "pending"
    iteration_count: int = 0
    routing_history: List[Dict[str, Any]] = []
    last_routing_decision: Optional[Dict[str, Any]] = None
    termination_reason: Optional[str] = None
    confidence_scores: List[float] = []
    
    @property
    def average_confidence(self) -> float:
        """Calculate average confidence of routing decisions"""
        if not self.confidence_scores:
            return 0.0
        return sum(self.confidence_scores) / len(self.confidence_scores)
```

### 6. Integration with Existing Graph

```python
def create_enhanced_main_supervisor() -> StateGraph:
    """Create main supervisor with enhanced LLM routing"""
    
    # Get routing configuration
    routing_config = create_routing_configuration()
    main_config = routing_config["main_supervisor"]
    
    # Create enhanced supervisor node
    main_supervisor_node = create_llm_supervisor_node(
        llm=main_config["llm"],
        available_nodes=main_config["available_nodes"],
        decision_model=main_config["decision_model"],
        max_iterations=main_config["max_iterations"]
    )
    
    # Create team graphs (with their own LLM routing)
    research_team_graph = create_enhanced_research_team()
    content_team_graph = create_enhanced_content_team()
    social_media_team_graph = create_enhanced_social_media_team()
    
    # Build main graph
    builder = StateGraph(EnhancedMarketingState)
    builder.add_node("supervisor", main_supervisor_node)
    builder.add_node("research_team", research_team_graph)
    builder.add_node("content_team", content_team_graph)
    builder.add_node("social_media_team", social_media_team_graph)
    builder.add_node("strategy_agent", strategy_agent_node)
    
    # Add edges
    builder.add_edge(START, "supervisor")
    builder.add_edge("research_team", "supervisor")
    builder.add_edge("content_team", "supervisor")
    builder.add_edge("social_media_team", "supervisor")
    builder.add_edge("strategy_agent", "supervisor")
    
    return builder.compile()
```

## Error Handling and Fallbacks

### 1. LLM Failure Fallback Chain

```python
class RoutingFallbackChain:
    """Chain of fallback strategies for routing failures"""
    
    def __init__(self):
        self.strategies = [
            self._retry_with_simpler_model,
            self._use_cached_decisions,
            self._keyword_based_routing,
            self._default_routing
        ]
    
    async def get_decision(self, router: StructuredRouter, state: dict) -> RoutingDecision:
        """Try multiple strategies to get a routing decision"""
        
        for strategy in self.strategies:
            try:
                decision = await strategy(router, state)
                if decision.confidence > 0.3:  # Minimum confidence threshold
                    return decision
            except Exception:
                continue
        
        # Ultimate fallback
        return router._fallback_routing(state.get("task", ""))
    
    async def _retry_with_simpler_model(self, router: StructuredRouter, state: dict):
        """Retry with a simpler/faster model"""
        # Implementation for model switching
        pass
    
    async def _use_cached_decisions(self, router: StructuredRouter, state: dict):
        """Use cached routing decisions for similar tasks"""
        # Implementation for decision caching
        pass
    
    async def _keyword_based_routing(self, router: StructuredRouter, state: dict):
        """Fallback to keyword-based routing"""
        return router._fallback_routing(state.get("task", ""))
    
    async def _default_routing(self, router: StructuredRouter, state: dict):
        """Default routing to first available node"""
        return router.decision_model(
            next_node=router.available_nodes[0] if router.available_nodes else "FINISH",
            reasoning="Default routing: All other strategies failed",
            confidence=0.1,
            should_terminate=False
        )
```

### 2. JSON Output Validation

```python
import json
from jsonschema import validate, ValidationError

class JSONOutputValidator:
    """Validate and sanitize JSON outputs from LLMs"""
    
    def __init__(self, schema: dict):
        self.schema = schema
    
    def validate_and_fix(self, json_str: str) -> dict:
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
                raise ValueError(f"Invalid JSON: {e}")
        
        # Validate against schema
        try:
            validate(instance=data, schema=self.schema)
        except ValidationError as e:
            # Attempt to fix validation issues
            data = self._fix_validation_issues(data, e)
        
        return data
    
    def _fix_json_issues(self, json_str: str) -> str:
        """Fix common JSON issues"""
        # Remove markdown code blocks
        json_str = json_str.replace("```json", "").replace("```", "")
        
        # Fix trailing commas
        json_str = json_str.replace(",}", "}").replace(",]", "]")
        
        # Fix missing quotes
        # Simple pattern matching for common issues
        import re
        json_str = re.sub(r'(\w+):', r'"\1":', json_str)
        
        return json_str.strip()
    
    def _fix_validation_issues(self, data: dict, error: ValidationError) -> dict:
        """Fix validation issues in JSON data"""
        # Implementation for fixing specific validation errors
        return data
```

## Monitoring and Metrics

### 1. Routing Performance Metrics

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class RoutingMetrics:
    """Metrics for routing performance"""
    timestamp: datetime
    decision_time_ms: float
    confidence: float
    success: bool
    fallback_used: bool
    llm_provider: str
    model_name: str
    
class RoutingMonitor:
    """Monitor routing performance"""
    
    def __init__(self):
        self.metrics: List[RoutingMetrics] = []
    
    def record_decision(self, metrics: RoutingMetrics):
        """Record routing decision metrics"""
        self.metrics.append(metrics)
    
    def get_summary(self) -> dict:
        """Get summary statistics"""
        if not self.metrics:
            return {}
        
        successful = [m for m in self.metrics if m.success]
        avg_confidence = sum(m.confidence for m in self.metrics) / len(self.metrics)
        avg_decision_time = sum(m.decision_time_ms for m in self.metrics) / len(self.metrics)
        fallback_rate = sum(1 for m in self.metrics if m.fallback_used) / len(self.metrics)
        
        return {
            "total_decisions": len(self.metrics),
            "success_rate": len(successful) / len(self.metrics),
            "average_confidence": avg_confidence,
            "average_decision_time_ms": avg_decision_time,
            "fallback_rate": fallback_rate,
            "unique_providers": set(m.llm_provider for m in self.metrics)
        }
```

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
1. Implement Pydantic models for routing decisions
2. Create `StructuredRouter` factory class
3. Implement JSON validation and fixing utilities
4. Create basic fallback mechanisms

### Phase 2: Integration (Week 2)
1. Integrate LLM routing into main supervisor
2. Update team supervisors with LLM routing
3. Implement enhanced state with routing metadata
4. Add routing performance monitoring

### Phase 3: Optimization (Week 3)
1. Implement decision caching
2. Add multi-model fallback chain
3. Optimize prompts for better JSON output
4. Add cost tracking and optimization

### Phase 4: Production Readiness (Week 4)
1. Comprehensive error handling
2. Performance testing and benchmarking
3. Documentation and examples
4. Deployment configuration

## Testing Strategy

### Unit Tests
1. **JSON parsing**: Test JSON validation and fixing
2. **Routing logic**: Test decision-making with mock LLMs
3. **Fallback chains**: Test all fallback strategies
4. **State management**: Test enhanced state updates

### Integration Tests
1. **End-to-end routing**: Test complete routing flow
2. **Multi-level coordination**: Test hierarchical routing decisions
3. **Error scenarios**: Test LLM failures and recovery
4. **Performance**: Test routing latency and throughput

### Acceptance Tests
1. **Business logic**: Test routing aligns with business requirements
2. **Confidence thresholds**: Test decision quality
3. **Cost efficiency**: Test routing doesn't exceed cost limits
4. **User experience**: Test overall workflow smoothness

## Success Criteria

### Technical Metrics
1. **Success rate**: >95% of routing decisions succeed
2. **Latency**: <2 seconds per routing decision
3. **JSON validity**: >99% of LLM outputs are valid JSON
4. **Fallback rate**: <10% of decisions use fallback

### Business Metrics
1. **Task completion**: