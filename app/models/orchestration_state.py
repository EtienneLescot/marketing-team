#!/usr/bin/env python3
"""
Orchestration state models for dynamic graph building with dependency resolution.
"""

from typing import TypedDict, Optional, Dict, Any, List, Annotated
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from datetime import datetime
import operator


class ExecutionPlan(BaseModel):
    """Execution plan for task orchestration"""
    task_id: str = Field(description="Unique task identifier")
    original_task: str = Field(description="Original user task")
    subtasks: List[Dict[str, Any]] = Field(description="List of subtasks with dependencies")
    execution_order: List[str] = Field(description="Topological order of agent execution")
    current_step: int = Field(description="Current step in execution order", default=0)
    completed_steps: List[str] = Field(description="Completed steps", default_factory=list)
    agent_results: Dict[str, str] = Field(description="Results from each agent", default_factory=dict)
    
    def get_current_agent(self) -> Optional[str]:
        """Get the current agent to execute"""
        if self.current_step < len(self.execution_order):
            return self.execution_order[self.current_step]
        return None
    
    def mark_agent_complete(self, agent_name: str, result: str):
        """Mark an agent as completed with result"""
        self.agent_results[agent_name] = result
        if agent_name not in self.completed_steps:
            self.completed_steps.append(agent_name)
        
        # Advance to next step if this was the current agent
        if (self.current_step < len(self.execution_order) and 
            self.execution_order[self.current_step] == agent_name):
            self.current_step += 1
    
    def is_complete(self) -> bool:
        """Check if all steps are complete"""
        return self.current_step >= len(self.execution_order)
    
    def get_pending_dependencies(self, agent_name: str) -> List[str]:
        """Get pending dependencies for an agent"""
        pending = []
        for subtask in self.subtasks:
            if subtask.get("assigned_to") == agent_name:
                for dep in subtask.get("dependencies", []):
                    if dep not in self.completed_steps:
                        pending.append(dep)
        return pending
    
    def can_execute(self, agent_name: str) -> bool:
        """Check if an agent can execute (all dependencies satisfied)"""
        return len(self.get_pending_dependencies(agent_name)) == 0


class OrchestrationState(MessagesState):
    """State for orchestration with dependency resolution"""
    
    # Core orchestration
    execution_plan: Optional[ExecutionPlan] = Field(description="Execution plan for current task", default=None)
    target_agent: str = Field(description="Target agent to start execution from", default="main_supervisor")
    
    # Task tracking
    original_task: str = Field(description="Original user task")
    current_task: str = Field(description="Current task being worked on")
    task_status: str = Field(description="Status of current task", default="pending")
    
    # Agent tracking
    current_agent: Optional[str] = Field(description="Current agent working on the task", default=None)
    agent_history: Annotated[List[Dict[str, Any]], operator.add] = Field(
        description="History of agent executions", default_factory=list
    )
    
    # Results tracking
    agent_results: Dict[str, str] = Field(description="Results from each agent", default_factory=dict)
    final_result: Optional[str] = Field(description="Final synthesized result", default=None)
    
    # Workflow metadata
    workflow_id: Optional[str] = Field(description="Unique workflow ID", default=None)
    iteration_count: Annotated[int, operator.add] = Field(description="Number of iterations", default=0)
    max_iterations: int = Field(description="Maximum iterations allowed", default=20)
    
    # Performance metrics
    start_time: Optional[datetime] = Field(description="Workflow start time", default=None)
    total_agent_calls: Annotated[int, operator.add] = Field(description="Total agent calls", default=0)
    total_tool_calls: Annotated[int, operator.add] = Field(description="Total tool calls", default=0)
    
    # Error tracking
    error_count: Annotated[int, operator.add] = Field(description="Number of errors", default=0)
    last_error: Optional[str] = Field(description="Last error message", default=None)
    
    def initialize_execution_plan(self, plan: ExecutionPlan):
        """Initialize execution plan"""
        self.execution_plan = plan
        self.task_status = "planning_complete"
        
    def get_next_agent(self) -> Optional[str]:
        """Get the next agent to execute based on execution plan"""
        if not self.execution_plan:
            return None
        
        # Get current agent from plan
        current_agent = self.execution_plan.get_current_agent()
        if current_agent:
            # Check if dependencies are satisfied
            if self.execution_plan.can_execute(current_agent):
                return current_agent
        
        return None
    
    def mark_agent_complete(self, agent_name: str, result: str):
        """Mark an agent as completed with result"""
        self.agent_results[agent_name] = result
        self.agent_history.append({
            "agent": agent_name,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
        if self.execution_plan:
            self.execution_plan.mark_agent_complete(agent_name, result)
            
            # Check if plan is complete
            if self.execution_plan.is_complete():
                self.task_status = "execution_complete"
    
    def is_complete(self) -> bool:
        """Check if orchestration is complete"""
        if self.execution_plan:
            return self.execution_plan.is_complete()
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = dict(self)
        
        # Handle datetime serialization
        if data.get("start_time"):
            data["start_time"] = data["start_time"].isoformat()
        
        # Handle execution plan serialization
        if data.get("execution_plan"):
            data["execution_plan"] = self.execution_plan.dict()
        
        return data


class DependencyGraph:
    """Utility class for building and analyzing dependency graphs"""
    
    def __init__(self, agents_config: Dict[str, Any]):
        """
        Initialize with agent configurations.
        
        Args:
            agents_config: Dict mapping agent names to their configs
        """
        self.agents = agents_config
        self.graph = self._build_dependency_graph()
    
    def _build_dependency_graph(self) -> Dict[str, List[str]]:
        """Build adjacency list of dependencies"""
        graph = {}
        for agent_name, config in self.agents.items():
            depends_on = getattr(config, 'depends_on', []) or []
            graph[agent_name] = depends_on
        return graph
    
    def get_topological_order(self) -> List[str]:
        """Get topological order of agents based on dependencies"""
        from collections import deque
        
        # Build reverse adjacency list: who depends on me?
        reverse_graph = {agent: [] for agent in self.graph}
        for agent, deps in self.graph.items():
            for dep in deps:
                if dep in reverse_graph:
                    reverse_graph[dep].append(agent)
                else:
                    reverse_graph[dep] = [agent]
        
        # Calculate in-degrees (number of dependencies for each agent)
        in_degree = {agent: 0 for agent in self.graph}
        for agent, deps in self.graph.items():
            in_degree[agent] = len(deps)
        
        # Initialize queue with agents having no dependencies
        queue = deque([agent for agent, deg in in_degree.items() if deg == 0])
        result = []
        
        while queue:
            agent = queue.popleft()
            result.append(agent)
            
            # Reduce in-degree of neighbors that depend on this agent
            for neighbor in reverse_graph.get(agent, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Check for cycles
        if len(result) != len(self.graph):
            # There's a cycle - we should not fallback, but raise an error
            # or provide a deterministic order
            raise ValueError(f"Cycle detected in dependency graph. Could only order {len(result)} of {len(self.graph)} agents.")
        
        return result
    
    def _get_hierarchy_order(self) -> List[str]:
        """Fallback order based on agent hierarchy (supervisors first)"""
        supervisors = []
        workers = []
        
        for agent_name, config in self.agents.items():
            if getattr(config, 'role', 'worker') == 'supervisor':
                supervisors.append(agent_name)
            else:
                workers.append(agent_name)
        
        return supervisors + workers
    
    def validate_dependencies(self) -> List[str]:
        """Validate that all dependencies exist"""
        errors = []
        for agent_name, deps in self.graph.items():
            for dep in deps:
                if dep not in self.agents:
                    errors.append(f"Agent '{agent_name}' depends on non-existent agent '{dep}'")
        return errors
    
    def get_agent_subgraph(self, start_agent: str) -> Dict[str, List[str]]:
        """Get subgraph starting from a specific agent (including managed agents)"""
        visited = set()
        subgraph = {}
        
        def dfs(agent: str):
            if agent in visited:
                return
            visited.add(agent)
            
            # Get dependencies
            deps = self.graph.get(agent, [])
            subgraph[agent] = deps
            
            # Get managed agents (if any)
            config = self.agents.get(agent)
            if config and hasattr(config, 'managed_agents') and config.managed_agents:
                for managed in config.managed_agents:
                    dfs(managed)
        
        dfs(start_agent)
        return subgraph