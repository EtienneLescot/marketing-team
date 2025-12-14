# Monitoring and Logging System Design

## Overview
This document outlines the design for implementing comprehensive monitoring and logging in the hierarchical marketing agents system, enabling observability, performance tracking, and operational intelligence.

## Current Limitations
1. **Limited logging**: Basic print statements with no structured format
2. **No metrics**: No performance or business metrics collection
3. **No alerts**: No proactive notification of issues
4. **Poor traceability**: Difficult to trace requests through the system
5. **No dashboards**: No visualization of system health or performance

## Design Goals
1. **Structured logging**: Consistent, machine-readable log format
2. **Comprehensive metrics**: Business, technical, and cost metrics
3. **Distributed tracing**: End-to-end request tracing
4. **Real-time alerts**: Proactive notification of issues
5. **Interactive dashboards**: Visual monitoring of system health
6. **Cost tracking**: Real-time tracking of API and compute costs

## Architecture

### 1. Structured Logging System

```python
import structlog
import logging
import sys
from typing import Dict, Any, Optional
from datetime import datetime
import json
from contextvars import ContextVar
import uuid

# Context variables for distributed tracing
request_id: ContextVar[str] = ContextVar('request_id', default='')
workflow_id: ContextVar[str] = ContextVar('workflow_id', default='')
user_id: ContextVar[str] = ContextVar('user_id', default='')

class StructuredLogger:
    """Structured logging with context propagation"""
    
    def __init__(self, name: str = "marketing_agents"):
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.BoundLogger,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        
        self.logger = structlog.get_logger(name)
        self.metrics_collector = None
    
    def bind_context(
        self,
        request_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        **additional_context
    ):
        """Bind context variables to logger"""
        context = {}
        
        if request_id:
            context['request_id'] = request_id
        if workflow_id:
            context['workflow_id'] = workflow_id
        if user_id:
            context['user_id'] = user_id
        if agent_name:
            context['agent_name'] = agent_name
        
        context.update(additional_context)
        return self.logger.bind(**context)
    
    def log_agent_execution(
        self,
        agent_name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        duration_ms: float,
        success: bool,
        error_message: Optional[str] = None
    ):
        """Log agent execution with structured data"""
        log_data = {
            "event": "agent_execution",
            "agent_name": agent_name,
            "input_summary": self._summarize_input(input_data),
            "output_summary": self._summarize_output(output_data),
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": datetime.now().isoformat()
        }
        
        if error_message:
            log_data["error_message"] = error_message
        
        if success:
            self.logger.info("agent_execution_completed", **log_data)
        else:
            self.logger.error("agent_execution_failed", **log_data)
        
        # Collect metrics if available
        if self.metrics_collector:
            self.metrics_collector.record_agent_execution(
                agent_name=agent_name,
                duration_ms=duration_ms,
                success=success
            )
    
    def log_routing_decision(
        self,
        decision_point: str,
        available_nodes: list,
        selected_node: str,
        reasoning: str,
        confidence: float
    ):
        """Log routing decision"""
        self.logger.info(
            "routing_decision",
            event="routing_decision",
            decision_point=decision_point,
            available_nodes=available_nodes,
            selected_node=selected_node,
            reasoning=reasoning,
            confidence=confidence,
            timestamp=datetime.now().isoformat()
        )
    
    def log_tool_usage(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Dict[str, Any],
        duration_ms: float,
        success: bool,
        cost_estimate: float = 0.0
    ):
        """Log tool usage"""
        log_data = {
            "event": "tool_usage",
            "tool_name": tool_name,
            "parameters_summary": self._summarize_parameters(parameters),
            "result_summary": self._summarize_result(result),
            "duration_ms": duration_ms,
            "success": success,
            "cost_estimate": cost_estimate,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info("tool_executed", **log_data)
        
        # Collect metrics
        if self.metrics_collector:
            self.metrics_collector.record_tool_usage(
                tool_name=tool_name,
                duration_ms=duration_ms,
                success=success,
                cost_estimate=cost_estimate
            )
    
    def log_workflow_event(
        self,
        event_type: str,
        workflow_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log workflow-level events"""
        log_data = {
            "event": f"workflow_{event_type}",
            "workflow_id": workflow_id,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        
        if metadata:
            log_data.update(metadata)
        
        self.logger.info(f"workflow_{event_type}", **log_data)
    
    def _summarize_input(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create summary of input data for logging"""
        summary = {}
        for key, value in input_data.items():
            if isinstance(value, str):
                summary[key] = value[:100] + "..." if len(value) > 100 else value
            elif isinstance(value, (int, float, bool)):
                summary[key] = value
            elif isinstance(value, dict):
                summary[key] = {"type": "dict", "keys": list(value.keys())}
            elif isinstance(value, list):
                summary[key] = {"type": "list", "length": len(value)}
            else:
                summary[key] = str(type(value))
        return summary
    
    def _summarize_output(self, output_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create summary of output data for logging"""
        return self._summarize_input(output_data)
    
    def _summarize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create summary of tool parameters"""
        summary = {}
        for key, value in parameters.items():
            if key.lower() in ['api_key', 'password', 'secret', 'token']:
                summary[key] = "***REDACTED***"
            else:
                summary[key] = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
        return summary
    
    def _summarize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Create summary of tool result"""
        if isinstance(result, dict):
            summary = {"type": "dict", "keys": list(result.keys())}
            # Include size information for large results
            result_str = json.dumps(result)
            summary["size_bytes"] = len(result_str)
            return summary
        elif isinstance(result, str):
            return {"type": "str", "length": len(result), "preview": result[:100]}
        else:
            return {"type": str(type(result)), "value": str(result)}
```

### 2. Metrics Collection System

```python
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
import statistics

@dataclass
class MetricPoint:
    """Single metric data point"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags
        }

class MetricsCollector:
    """Collects and aggregates metrics"""
    
    def __init__(self, retention_period: timedelta = timedelta(hours=24)):
        self.retention_period = retention_period
        self.metrics: List[MetricPoint] = []
        self.aggregated_metrics: Dict[str, List[float]] = defaultdict(list)
        self.lock = asyncio.Lock()
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_task())
    
    async def record_metric(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """Record a metric"""
        async with self.lock:
            metric_point = MetricPoint(
                name=name,
                value=value,
                timestamp=datetime.now(),
                tags=tags or {}
            )
            
            self.metrics.append(metric_point)
            self.aggregated_metrics[name].append(value)
    
    async def record_agent_execution(
        self,
        agent_name: str,
        duration_ms: float,
        success: bool
    ):
        """Record agent execution metrics"""
        tags = {"agent_name": agent_name}
        
        # Record duration
        await self.record_metric(
            name="agent_execution_duration_ms",
            value=duration_ms,
            tags=tags
        )
        
        # Record success/failure
        await self.record_metric(
            name="agent_execution_success",
            value=1.0 if success else 0.0,
            tags=tags
        )
    
    async def record_tool_usage(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool,
        cost_estimate: float
    ):
        """Record tool usage metrics"""
        tags = {"tool_name": tool_name}
        
        # Record duration
        await self.record_metric(
            name="tool_execution_duration_ms",
            value=duration_ms,
            tags=tags
        )
        
        # Record success
        await self.record_metric(
            name="tool_execution_success",
            value=1.0 if success else 0.0,
            tags=tags
        )
        
        # Record cost
        await self.record_metric(
            name="tool_execution_cost",
            value=cost_estimate,
            tags=tags
        )
    
    async def record_workflow_metrics(
        self,
        workflow_id: str,
        total_agents: int,
        total_tools: int,
        total_duration_ms: float,
        success: bool
    ):
        """Record workflow-level metrics"""
        tags = {"workflow_id": workflow_id}
        
        await self.record_metric(
            name="workflow_total_agents",
            value=total_agents,
            tags=tags
        )
        
        await self.record_metric(
            name="workflow_total_tools",
            value=total_tools,
            tags=tags
        )
        
        await self.record_metric(
            name="workflow_total_duration_ms",
            value=total_duration_ms,
            tags=tags
        )
        
        await self.record_metric(
            name="workflow_success",
            value=1.0 if success else 0.0,
            tags=tags
        )
    
    def get_metrics_summary(
        self,
        name: Optional[str] = None,
        time_range: Optional[timedelta] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Get summary statistics for metrics"""
        async with self.lock:
            # Filter metrics
            filtered = self.metrics
            
            if name:
                filtered = [m for m in filtered if m.name == name]
            
            if time_range:
                cutoff = datetime.now() - time_range
                filtered = [m for m in filtered if m.timestamp >= cutoff]
            
            if tags:
                filtered = [
                    m for m in filtered
                    if all(m.tags.get(k) == v for k, v in tags.items())
                ]
            
            if not filtered:
                return {"count": 0, "message": "No metrics found"}
            
            values = [m.value for m in filtered]
            
            return {
                "count": len(values),
                "sum": sum(values),
                "mean": statistics.mean(values) if values else 0,
                "median": statistics.median(values) if values else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "stddev": statistics.stdev(values) if len(values) > 1 else 0,
                "latest_timestamp": max(m.timestamp for m in filtered).isoformat(),
                "oldest_timestamp": min(m.timestamp for m in filtered).isoformat()
            }
    
    async def _cleanup_task(self):
        """Background task to clean up old metrics"""
        while True:
            await asyncio.sleep(3600)  # Run every hour
            
            async with self.lock:
                cutoff = datetime.now() - self.retention_period
                self.metrics = [m for m in self.metrics if m.timestamp >= cutoff]
                
                # Also clean aggregated metrics
                for name in list(self.aggregated_metrics.keys()):
                    # Keep only recent aggregated values (last 1000)
                    if len(self.aggregated_metrics[name]) > 1000:
                        self.aggregated_metrics[name] = self.aggregated_metrics[name][-1000:]
```

### 3. Alerting System

```python
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertCondition(Enum):
    """Alert conditions"""
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    THRESHOLD_BELOW = "threshold_below"
    ERROR_RATE_HIGH = "error_rate_high"
    LATENCY_HIGH = "latency_high"
    NO_DATA = "no_data"
    PATTERN_DETECTED = "pattern_detected"

@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    condition: AlertCondition
    metric_name: str
    threshold: float
    severity: AlertSeverity
    duration: timedelta  # Time window to evaluate
    cooldown: timedelta  # Minimum time between alerts
    tags: Optional[Dict[str, str]] = None
    message_template: str = "{metric_name} {condition} threshold: {value} > {threshold}"
    
    def check_condition(self, value: float) -> bool:
        """Check if condition is met"""
        if self.condition == AlertCondition.THRESHOLD_EXCEEDED:
            return value > self.threshold
        elif self.condition == AlertCondition.THRESHOLD_BELOW:
            return value < self.threshold
        elif self.condition == AlertCondition.ERROR_RATE_HIGH:
            return value > self.threshold
        elif self.condition == AlertCondition.LATENCY_HIGH:
            return value > self.threshold
        else:
            return False

@dataclass
class Alert:
    """Alert instance"""
    rule: AlertRule
    value: float
    timestamp: datetime
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary"""
        return {
            "rule_name": self.rule.name,
            "severity": self.rule.severity.value,
            "condition": self.rule.condition.value,
            "metric_name": self.rule.metric_name,
            "threshold": self.rule.threshold,
            "actual_value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "message": self.rule.message_template.format(
                metric_name=self.rule.metric_name,
                condition=self.rule.condition.value,
                value=self.value,
                threshold=self.rule.threshold
            ),
            "metadata": self.metadata
        }

class AlertManager:
    """Manages alert rules and notifications"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.rules: List[AlertRule] = []
        self.triggered_alerts: Dict[str, datetime] = {}  # rule_name -> last_triggered
        self.notification_handlers: List[Callable] = []
        
        # Start monitoring task
        asyncio.create_task(self._monitoring_task())
    
    def add_rule(self, rule: AlertRule):
        """Add an alert rule"""
        self.rules.append(rule)
    
    def add_notification_handler(self, handler: Callable):
        """Add a notification handler"""
        self.notification_handlers.append(handler)
    
    async def check_rules(self):
        """Check all alert rules"""
        for rule in self.rules:
            # Check cooldown
            last_triggered = self.triggered_alerts.get(rule.name)
            if last_triggered and datetime.now() - last_triggered < rule.cooldown:
                continue
            
            # Get metric summary
            summary = self.metrics_collector.get_metrics_summary(
                name=rule.metric_name,
                time_range=rule.duration,
                tags=rule