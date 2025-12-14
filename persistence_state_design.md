# Persistence and State Management Design

## Overview
This document outlines the design for implementing persistence and state management in the hierarchical marketing agents system, enabling workflow checkpointing, state recovery, and historical tracking.

## Current Limitations
1. **Ephemeral state**: Current state exists only in memory during execution
2. **No recovery**: Workflows cannot be resumed after failures
3. **No history**: No tracking of past executions or decisions
4. **No audit trail**: Cannot trace how decisions were made
5. **Scalability issues**: State cannot be shared across multiple instances

## Design Goals
1. **Workflow persistence**: Save and restore workflow state
2. **Checkpointing**: Create recovery points during execution
3. **Historical tracking**: Maintain complete execution history
4. **State sharing**: Enable distributed execution
5. **Audit compliance**: Full traceability of decisions
6. **Performance**: Minimal impact on execution speed

## Architecture

### 1. Database Schema Design

```sql
-- Core workflow tracking
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    initial_task TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'paused', 'completed', 'failed', 'cancelled')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'::jsonb,
    INDEX idx_workflows_user_status (user_id, status),
    INDEX idx_workflows_created (created_at)
);

-- Workflow state snapshots (checkpoints)
CREATE TABLE workflow_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    checkpoint_name TEXT NOT NULL,
    state_json JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb,
    INDEX idx_snapshots_workflow (workflow_id),
    INDEX idx_snapshots_checkpoint (workflow_id, checkpoint_name)
);

-- Agent execution history
CREATE TABLE agent_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,
    input_data JSONB,
    output_data JSONB,
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    INDEX idx_executions_workflow (workflow_id),
    INDEX idx_executions_agent (agent_name),
    INDEX idx_executions_time (start_time)
);

-- Routing decision history
CREATE TABLE routing_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    decision_point TEXT NOT NULL,  -- e.g., "main_supervisor", "research_team_supervisor"
    available_nodes TEXT[] NOT NULL,
    selected_node TEXT NOT NULL,
    reasoning TEXT,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb,
    INDEX idx_decisions_workflow (workflow_id),
    INDEX idx_decisions_point (decision_point)
);

-- Tool usage tracking
CREATE TABLE tool_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    parameters JSONB,
    result JSONB,
    cost_estimate FLOAT DEFAULT 0.0,
    duration_ms INTEGER,
    success BOOLEAN DEFAULT true,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tool_usage_workflow (workflow_id),
    INDEX idx_tool_usage_tool (tool_name)
);

-- Performance metrics
CREATE TABLE performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    metric_name TEXT NOT NULL,
    metric_value FLOAT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb,
    INDEX idx_metrics_workflow (workflow_id),
    INDEX idx_metrics_name (metric_name)
);
```

### 2. State Persistence Layer

```python
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import uuid
from abc import ABC, abstractmethod
import asyncpg
from contextlib import asynccontextmanager

@dataclass
class WorkflowRecord:
    """Workflow record for persistence"""
    id: str
    user_id: str
    initial_task: str
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime to ISO format
        for field in ['created_at', 'updated_at', 'completed_at']:
            if data[field]:
                data[field] = data[field].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowRecord':
        """Create from dictionary"""
        # Convert ISO strings back to datetime
        for field in ['created_at', 'updated_at', 'completed_at']:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])
        return cls(**data)

@dataclass
class StateSnapshot:
    """State snapshot for checkpointing"""
    id: str
    workflow_id: str
    checkpoint_name: str
    state_json: Dict[str, Any]
    created_at: datetime
    metadata: Dict[str, Any] = None

class StatePersistence(ABC):
    """Abstract base class for state persistence"""
    
    @abstractmethod
    async def save_workflow(self, workflow: WorkflowRecord) -> str:
        """Save workflow record"""
        pass
    
    @abstractmethod
    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowRecord]:
        """Get workflow by ID"""
        pass
    
    @abstractmethod
    async def update_workflow_status(self, workflow_id: str, status: str) -> bool:
        """Update workflow status"""
        pass
    
    @abstractmethod
    async def save_snapshot(self, snapshot: StateSnapshot) -> str:
        """Save state snapshot"""
        pass
    
    @abstractmethod
    async def get_latest_snapshot(self, workflow_id: str) -> Optional[StateSnapshot]:
        """Get latest snapshot for workflow"""
        pass
    
    @abstractmethod
    async def save_agent_execution(self, execution: Dict[str, Any]) -> str:
        """Save agent execution record"""
        pass
    
    @abstractmethod
    async def save_routing_decision(self, decision: Dict[str, Any]) -> str:
        """Save routing decision"""
        pass

class PostgreSQLStatePersistence(StatePersistence):
    """PostgreSQL implementation of state persistence"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Initialize connection pool"""
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=1,
            max_size=10,
            command_timeout=60
        )
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool"""
        if not self.pool:
            await self.initialize()
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def save_workflow(self, workflow: WorkflowRecord) -> str:
        """Save workflow to database"""
        async with self.get_connection() as conn:
            workflow_id = await conn.fetchval("""
                INSERT INTO workflows (
                    id, user_id, initial_task, status, 
                    created_at, updated_at, completed_at, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """,
                uuid.UUID(workflow.id) if workflow.id else uuid.uuid4(),
                workflow.user_id,
                workflow.initial_task,
                workflow.status,
                workflow.created_at,
                workflow.updated_at,
                workflow.completed_at,
                json.dumps(workflow.metadata) if workflow.metadata else '{}'
            )
            return str(workflow_id)
    
    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowRecord]:
        """Get workflow from database"""
        async with self.get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM workflows WHERE id = $1
            """, uuid.UUID(workflow_id))
            
            if not row:
                return None
            
            return WorkflowRecord(
                id=str(row['id']),
                user_id=row['user_id'],
                initial_task=row['initial_task'],
                status=row['status'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                completed_at=row['completed_at'],
                metadata=row['metadata']
            )
    
    async def update_workflow_status(self, workflow_id: str, status: str) -> bool:
        """Update workflow status"""
        async with self.get_connection() as conn:
            updated = await conn.execute("""
                UPDATE workflows 
                SET status = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """, status, uuid.UUID(workflow_id))
            
            return "UPDATE" in updated
    
    async def save_snapshot(self, snapshot: StateSnapshot) -> str:
        """Save state snapshot"""
        async with self.get_connection() as conn:
            snapshot_id = await conn.fetchval("""
                INSERT INTO workflow_snapshots (
                    id, workflow_id, checkpoint_name, 
                    state_json, created_at, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
            """,
                uuid.UUID(snapshot.id) if snapshot.id else uuid.uuid4(),
                uuid.UUID(snapshot.workflow_id),
                snapshot.checkpoint_name,
                json.dumps(snapshot.state_json),
                snapshot.created_at,
                json.dumps(snapshot.metadata) if snapshot.metadata else '{}'
            )
            return str(snapshot_id)
    
    async def get_latest_snapshot(self, workflow_id: str) -> Optional[StateSnapshot]:
        """Get latest snapshot for workflow"""
        async with self.get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM workflow_snapshots 
                WHERE workflow_id = $1 
                ORDER BY created_at DESC 
                LIMIT 1
            """, uuid.UUID(workflow_id))
            
            if not row:
                return None
            
            return StateSnapshot(
                id=str(row['id']),
                workflow_id=str(row['workflow_id']),
                checkpoint_name=row['checkpoint_name'],
                state_json=row['state_json'],
                created_at=row['created_at'],
                metadata=row['metadata']
            )
    
    async def save_agent_execution(self, execution: Dict[str, Any]) -> str:
        """Save agent execution record"""
        async with self.get_connection() as conn:
            execution_id = await conn.fetchval("""
                INSERT INTO agent_executions (
                    id, workflow_id, agent_name, input_data, output_data,
                    start_time, end_time, duration_ms, success, 
                    error_message, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id
            """,
                uuid.uuid4(),
                uuid.UUID(execution['workflow_id']),
                execution['agent_name'],
                json.dumps(execution.get('input_data')),
                json.dumps(execution.get('output_data')),
                execution.get('start_time'),
                execution.get('end_time'),
                execution.get('duration_ms'),
                execution.get('success', True),
                execution.get('error_message'),
                json.dumps(execution.get('metadata', {}))
            )
            return str(execution_id)
    
    async def save_routing_decision(self, decision: Dict[str, Any]) -> str:
        """Save routing decision"""
        async with self.get_connection() as conn:
            decision_id = await conn.fetchval("""
                INSERT INTO routing_decisions (
                    id, workflow_id, decision_point, available_nodes,
                    selected_node, reasoning, confidence, timestamp, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """,
                uuid.uuid4(),
                uuid.UUID(decision['workflow_id']),
                decision['decision_point'],
                decision['available_nodes'],
                decision['selected_node'],
                decision.get('reasoning'),
                decision.get('confidence'),
                decision.get('timestamp', datetime.now()),
                json.dumps(decision.get('metadata', {}))
            )
            return str(decision_id)
```

### 3. Enhanced State with Persistence Integration

```python
from typing import TypedDict, Optional, Dict, Any, List
from langgraph.graph import MessagesState
from datetime import datetime

class PersistentMarketingState(MessagesState):
    """Enhanced state with persistence support"""
    
    # Core workflow metadata
    workflow_id: Optional[str] = None
    user_id: Optional[str] = None
    workflow_status: str = "running"
    
    # Persistence tracking
    last_checkpoint: Optional[str] = None
    checkpoint_count: int = 0
    persistence_enabled: bool = True
    
    # Execution metadata
    start_time: Optional[datetime] = None
    agent_execution_history: List[Dict[str, Any]] = []
    routing_decision_history: List[Dict[str, Any]] = []
    
    # Performance metrics
    total_agent_calls: int = 0
    total_tool_calls: int = 0
    estimated_cost: float = 0.0
    
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
            data['messages'] = [
                {
                    'type': msg.__class__.__name__,
                    'content': msg.content,
                    'name': getattr(msg, 'name', None),
                    'additional_kwargs': getattr(msg, 'additional_kwargs', {})
                }
                for msg in self['messages']
            ]
        
        return data
    
    @classmethod
    def from_persistable_dict(cls, data: Dict[str, Any]) -> 'PersistentMarketingState':
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
                messages.append(msg_class(
                    content=msg_data['content'],
                    name=msg_data.get('name'),
                    additional_kwargs=msg_data.get('additional_kwargs', {})
                ))
            
            data['messages'] = messages
        
        # Handle datetime deserialization
        datetime_fields = ['start_time']
        for field in datetime_fields:
            if field in data and data[field]:
                data[field] = datetime.fromisoformat(data[field])
        
        return cls(**data)
```

### 4. Checkpoint Manager

```python
from typing import Optional, Dict, Any
import asyncio
from datetime import datetime

class CheckpointManager:
    """Manages workflow checkpoints"""
    
    def __init__(self, persistence: StatePersistence):
        self.persistence = persistence
        self.checkpoint_config = {
            'frequency': 'after_each_agent',  # 'after_each_agent', 'after_each_decision', 'manual'
            'max_checkpoints': 10,
            'auto_cleanup': True
        }
    
    async def create_checkpoint(
        self, 
        workflow_id: str,
        state: PersistentMarketingState,
        checkpoint_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a checkpoint"""
        # Update checkpoint count in state
        state['checkpoint_count'] = state.get('checkpoint_count', 0) + 1
        state['last_checkpoint'] = checkpoint_name
        
        # Create snapshot
        snapshot = StateSnapshot(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            checkpoint_name=checkpoint_name,
            state_json=state.to_persistable_dict(),
            created_at=datetime.now(),
            metadata=metadata or {}
        )
        
        # Save to persistence
        snapshot_id = await self.persistence.save_snapshot(snapshot)
        
        # Auto-cleanup if configured
        if self.checkpoint_config['auto_cleanup']:
            await self._cleanup_old_checkpoints(workflow_id)
        
        return snapshot_id
    
    async def restore_checkpoint(
        self, 
        workflow_id: str, 
        checkpoint_name: Optional[str] = None
    ) -> Optional[PersistentMarketingState]:
        """Restore state from checkpoint"""
        if checkpoint_name:
