#!/usr/bin/env python3
"""
Basic monitoring setup for hierarchical marketing agents.
Tracks agent performance, errors, and provides metrics.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json


class AgentStatus(Enum):
    """Agent status enumeration"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"


class TaskType(Enum):
    """Task type enumeration"""
    RESEARCH = "research"
    CONTENT = "content"
    SOCIAL_MEDIA = "social_media"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass
class AgentEvent:
    """Agent event data"""
    timestamp: datetime
    agent_name: str
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "agent_name": self.agent_name,
            "event_type": self.event_type,
            "data": self.data,
            "duration_ms": self.duration_ms,
            "error": self.error
        }


@dataclass
class AgentMetrics:
    """Agent performance metrics"""
    agent_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    last_call_time: Optional[datetime] = None
    
    def record_call(self, duration_ms: float, success: bool = True):
        """Record a call"""
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        
        self.total_duration_ms += duration_ms
        self.avg_duration_ms = self.total_duration_ms / self.total_calls
        self.last_call_time = datetime.now()
    
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_name": self.agent_name,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": self.success_rate(),
            "total_duration_ms": self.total_duration_ms,
            "avg_duration_ms": self.avg_duration_ms,
            "last_call_time": self.last_call_time.isoformat() if self.last_call_time else None
        }


class BasicMonitor:
    """Basic monitoring system for agents"""
    
    def __init__(self, max_events: int = 1000):
        self.events: List[AgentEvent] = []
        self.metrics: Dict[str, AgentMetrics] = {}
        self.max_events = max_events
        self.start_time = datetime.now()
    
    def record_event(self, 
                    agent_name: str, 
                    event_type: str, 
                    data: Optional[Dict[str, Any]] = None,
                    duration_ms: Optional[float] = None,
                    error: Optional[str] = None):
        """Record an agent event"""
        event = AgentEvent(
            timestamp=datetime.now(),
            agent_name=agent_name,
            event_type=event_type,
            data=data or {},
            duration_ms=duration_ms,
            error=error
        )
        
        self.events.append(event)
        
        # Trim events if exceeding max
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        
        # Update metrics
        if agent_name not in self.metrics:
            self.metrics[agent_name] = AgentMetrics(agent_name=agent_name)
        
        if duration_ms is not None:
            success = error is None
            self.metrics[agent_name].record_call(duration_ms, success)
        
        return event
    
    def record_agent_start(self, agent_name: str, task: str) -> AgentEvent:
        """Record agent start"""
        return self.record_event(
            agent_name=agent_name,
            event_type="agent_start",
            data={"task": task}
        )
    
    def record_agent_complete(self, agent_name: str, result: Any, duration_ms: float) -> AgentEvent:
        """Record agent completion"""
        return self.record_event(
            agent_name=agent_name,
            event_type="agent_complete",
            data={"result": str(result)[:200]},  # Truncate long results
            duration_ms=duration_ms
        )
    
    def record_agent_error(self, agent_name: str, error: str, duration_ms: Optional[float] = None) -> AgentEvent:
        """Record agent error"""
        return self.record_event(
            agent_name=agent_name,
            event_type="agent_error",
            data={"error": error},
            duration_ms=duration_ms,
            error=error
        )
    
    def record_routing_decision(self, 
                               supervisor_name: str, 
                               decision: Dict[str, Any],
                               duration_ms: float) -> AgentEvent:
        """Record routing decision"""
        return self.record_event(
            agent_name=supervisor_name,
            event_type="routing_decision",
            data={"decision": decision},
            duration_ms=duration_ms
        )
    
    def record_tool_call(self, 
                        agent_name: str, 
                        tool_name: str, 
                        params: Dict[str, Any],
                        result: Any,
                        duration_ms: float) -> AgentEvent:
        """Record tool call"""
        return self.record_event(
            agent_name=agent_name,
            event_type="tool_call",
            data={
                "tool_name": tool_name,
                "params": params,
                "result": str(result)[:200]  # Truncate long results
            },
            duration_ms=duration_ms
        )
    
    def get_agent_metrics(self, agent_name: str) -> Optional[AgentMetrics]:
        """Get metrics for a specific agent"""
        return self.metrics.get(agent_name)
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get all metrics"""
        return {name: metrics.to_dict() for name, metrics in self.metrics.items()}
    
    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent events"""
        recent = self.events[-limit:] if self.events else []
        return [event.to_dict() for event in recent]
    
    def get_events_by_agent(self, agent_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get events for a specific agent"""
        agent_events = [e for e in self.events if e.agent_name == agent_name]
        recent = agent_events[-limit:] if agent_events else []
        return [event.to_dict() for event in recent]
    
    def get_system_uptime(self) -> float:
        """Get system uptime in seconds"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get monitoring summary"""
        total_calls = sum(m.total_calls for m in self.metrics.values())
        successful_calls = sum(m.successful_calls for m in self.metrics.values())
        failed_calls = sum(m.failed_calls for m in self.metrics.values())
        
        if total_calls > 0:
            overall_success_rate = successful_calls / total_calls
        else:
            overall_success_rate = 0.0
        
        # Get top performing agents
        agents_by_success = sorted(
            self.metrics.values(),
            key=lambda m: m.success_rate(),
            reverse=True
        )[:5]
        
        # Get most active agents
        agents_by_activity = sorted(
            self.metrics.values(),
            key=lambda m: m.total_calls,
            reverse=True
        )[:5]
        
        return {
            "uptime_seconds": self.get_system_uptime(),
            "total_events": len(self.events),
            "total_agents": len(self.metrics),
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "overall_success_rate": overall_success_rate,
            "top_performing_agents": [m.to_dict() for m in agents_by_success],
            "most_active_agents": [m.to_dict() for m in agents_by_activity],
            "recent_events": self.get_recent_events(10)
        }
    
    def print_summary(self):
        """Print monitoring summary to console"""
        summary = self.get_summary()
        
        print("\n" + "=" * 60)
        print("AGENT MONITORING SUMMARY")
        print("=" * 60)
        
        print(f"\n📊 System Overview:")
        print(f"   Uptime: {summary['uptime_seconds']:.1f} seconds")
        print(f"   Total agents: {summary['total_agents']}")
        print(f"   Total calls: {summary['total_calls']}")
        print(f"   Success rate: {summary['overall_success_rate']*100:.1f}%")
        
        print(f"\n🏆 Top Performing Agents:")
        for i, agent in enumerate(summary['top_performing_agents'][:3], 1):
            print(f"   {i}. {agent['agent_name']}: {agent['success_rate']*100:.1f}% "
                  f"({agent['successful_calls']}/{agent['total_calls']} calls)")
        
        print(f"\n⚡ Most Active Agents:")
        for i, agent in enumerate(summary['most_active_agents'][:3], 1):
            print(f"   {i}. {agent['agent_name']}: {agent['total_calls']} calls, "
                  f"avg {agent['avg_duration_ms']:.1f}ms")
        
        print(f"\n📈 Recent Events:")
        for event in summary['recent_events'][:5]:
            timestamp = event['timestamp'].split('T')[1][:12]  # Just time part
            print(f"   [{timestamp}] {event['agent_name']}: {event['event_type']}")
        
        print("\n" + "=" * 60)


# ============================================================================
# Context Manager for Timing
# ============================================================================

class TimerContext:
    """Context manager for timing operations"""
    
    def __init__(self, monitor: BasicMonitor, agent_name: str, operation: str):
        self.monitor = monitor
        self.agent_name = agent_name
        self.operation = operation
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.monitor.record_event(
            agent_name=self.agent_name,
            event_type=f"{self.operation}_start",
            data={}
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type is not None:
            self.monitor.record_event(
                agent_name=self.agent_name,
                event_type=f"{self.operation}_error",
                data={"error": str(exc_val)},
                duration_ms=self.duration_ms,
                error=str(exc_val)
            )
        else:
            self.monitor.record_event(
                agent_name=self.agent_name,
                event_type=f"{self.operation}_complete",
                data={"duration_ms": self.duration_ms},
                duration_ms=self.duration_ms
            )
        
        return False  # Don't suppress exceptions


# ============================================================================
# Global Monitor Instance
# ============================================================================

# Global monitor instance
_global_monitor: Optional[BasicMonitor] = None

def get_global_monitor() -> BasicMonitor:
    """Get or create global monitor instance"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = BasicMonitor()
    return _global_monitor


def reset_global_monitor():
    """Reset global monitor (for testing)"""
    global _global_monitor
    _global_monitor = None


# ============================================================================
# Decorators for Monitoring
# ============================================================================

def monitor_agent_call(agent_name: str):
    """Decorator to monitor agent function calls"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            monitor = get_global_monitor()
            start_time = time.time()
            
            # Record start
            monitor.record_agent_start(agent_name, str(func.__name__))
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Record completion
                monitor.record_agent_complete(agent_name, result, duration_ms)
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                # Record error
                monitor.record_agent_error(agent_name, str(e), duration_ms)
                
                raise
        
        def sync_wrapper(*args, **kwargs):
            monitor = get_global_monitor()
            start_time = time.time()
            
            # Record start
            monitor.record_agent_start(agent_name, str(func.__name__))
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Record completion
                monitor.record_agent_complete(agent_name, result, duration_ms)
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                # Record error
                monitor.record_agent_error(agent_name, str(e), duration_ms)
                
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ============================================================================
# Test Function
# ============================================================================

def test_monitoring():
    """Test the monitoring system"""
    print("Testing monitoring system...")
    
    monitor = BasicMonitor(max_events=50)
    
    # Record some events
    monitor.record_agent_start("web_researcher", "Research AI trends")
    monitor.record_agent_complete("web_researcher", "Found 10 results", 1500.5)
    
    monitor.record_agent_start("content_writer", "Write blog post")
    monitor.record_agent_error("content_writer", "Timeout error", 3000.0)
    
    monitor.record_routing_decision(
        "main_supervisor",
        {"next_node": "research_team", "confidence": 0.85},
        250.3
    )
    
    monitor.record_tool_call(
        "web_researcher",
        "tavily_search",
        {"query": "AI marketing trends"},
        "Search results...",
        1200.7
    )
    
    # Print summary
    monitor.print_summary()
    
    # Test metrics
    metrics = monitor.get_agent_metrics("web_researcher")
    if metrics:
        print(f"\nWeb researcher metrics:")
        print(f"  Total calls: {metrics.total_calls}")
        print(f"  Success rate: {metrics.success_rate()*100:.1f}%")
        print(f"  Avg duration: {metrics.avg_duration_ms:.1f}ms")
    
    print("\n✅ Monitoring test completed!")


if __name__ == "__main__":
    test_monitoring()