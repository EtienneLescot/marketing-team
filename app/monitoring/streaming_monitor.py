#!/usr/bin/env python3
"""
Real-time streaming monitor for hierarchical marketing agents.
Provides live visualization of agent activities, conversations, and outputs.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json

from app.monitoring.basic_monitor import BasicMonitor, AgentEvent, TimerContext


class EventStream:
    """Real-time event stream for monitoring agent activities"""
    
    def __init__(self, max_buffer: int = 1000):
        self.events: List[Dict[str, Any]] = []
        self.max_buffer = max_buffer
        self.subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self.workflow_graph: List[Dict[str, Any]] = []  # Tracks agent interactions
    
    def add_event(self, event: Dict[str, Any]):
        """Add event to stream and notify subscribers"""
        self.events.append(event)
        
        # Trim buffer if needed
        if len(self.events) > self.max_buffer:
            self.events = self.events[-self.max_buffer:]
        
        # Notify subscribers
        for subscriber in self.subscribers:
            try:
                subscriber(event)
            except Exception as e:
                print(f"Error in event subscriber: {e}")
    
    def subscribe(self, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to event stream"""
        self.subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[Dict[str, Any]], None]):
        """Unsubscribe from event stream"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    def record_agent_interaction(self, from_agent: str, to_agent: str, action: str, data: Dict[str, Any]):
        """Record interaction between agents"""
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "from": from_agent,
            "to": to_agent,
            "action": action,
            "data": data,
            "type": "interaction"
        }
        
        self.workflow_graph.append(interaction)
        self.add_event(interaction)
        
        # Print to console for real-time viewing
        print(f"[{interaction['timestamp'].split('T')[1][:12]}] {from_agent} → {to_agent}: {action}")
        if data.get('summary'):
            print(f"   Summary: {data['summary'][:100]}...")
    
    def record_agent_output(self, agent_name: str, output: str, output_type: str = "response"):
        """Record agent output"""
        output_event = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "output": output[:500],  # Truncate long outputs
            "output_type": output_type,
            "type": "output"
        }
        
        self.add_event(output_event)
        
        # Print to console
        print(f"\n{'='*60}")
        print(f"AGENT OUTPUT: {agent_name}")
        print(f"{'='*60}")
        print(f"{output[:300]}..." if len(output) > 300 else output)
        print(f"{'='*60}\n")
    
    def record_routing_decision(self, supervisor: str, decision: Dict[str, Any], reasoning: str):
        """Record routing decision"""
        routing_event = {
            "timestamp": datetime.now().isoformat(),
            "supervisor": supervisor,
            "decision": decision,
            "reasoning": reasoning,
            "type": "routing"
        }
        
        self.add_event(routing_event)
        
        # Print to console
        print(f"\n{'='*60}")
        print(f"ROUTING DECISION: {supervisor}")
        print(f"{'='*60}")
        print(f"Next: {decision.get('next_node', 'unknown')}")
        print(f"Confidence: {decision.get('confidence', 0):.2f}")
        print(f"Reasoning: {reasoning[:200]}...")
        print(f"{'='*60}\n")
    
    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent events"""
        return self.events[-limit:] if self.events else []
    
    def get_workflow_graph(self) -> List[Dict[str, Any]]:
        """Get workflow graph (agent interactions)"""
        return self.workflow_graph
    
    def generate_mermaid_diagram(self) -> str:
        """Generate Mermaid.js diagram from workflow graph"""
        if not self.workflow_graph:
            return "graph TD\n  A[No interactions recorded]"
        
        mermaid_lines = ["graph TD"]
        node_ids = {}
        next_id = 1
        
        for interaction in self.workflow_graph:
            from_agent = interaction["from"]
            to_agent = interaction["to"]
            action = interaction["action"]
            
            # Assign IDs to nodes
            if from_agent not in node_ids:
                node_ids[from_agent] = f"N{next_id}"
                next_id += 1
            if to_agent not in node_ids:
                node_ids[to_agent] = f"N{next_id}"
                next_id += 1
            
            from_id = node_ids[from_agent]
            to_id = node_ids[to_agent]
            
            # Add node definitions
            mermaid_lines.append(f"  {from_id}[{from_agent}]")
            mermaid_lines.append(f"  {to_id}[{to_agent}]")
            
            # Add edge
            mermaid_lines.append(f"  {from_id} -->|{action}| {to_id}")
        
        # Remove duplicates while preserving order
        unique_lines = []
        seen = set()
        for line in mermaid_lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)
        
        return "\n".join(unique_lines)


class StreamingMonitor(BasicMonitor):
    """Enhanced monitor with real-time streaming capabilities"""
    
    def __init__(self, max_events: int = 1000):
        super().__init__(max_events)
        self.stream = EventStream(max_buffer=500)
        self.agent_outputs: Dict[str, List[str]] = {}
    
    def record_event(self, 
                    agent_name: str, 
                    event_type: str, 
                    data: Optional[Dict[str, Any]] = None,
                    duration_ms: Optional[float] = None,
                    error: Optional[str] = None):
        """Record event with streaming"""
        event = super().record_event(agent_name, event_type, data, duration_ms, error)
        
        # Stream the event
        event_dict = event.to_dict()
        event_dict["stream_type"] = "agent_event"
        self.stream.add_event(event_dict)
        
        return event
    
    def record_agent_output(self, agent_name: str, output: str):
        """Record agent output with streaming"""
        if agent_name not in self.agent_outputs:
            self.agent_outputs[agent_name] = []
        
        self.agent_outputs[agent_name].append(output)
        self.stream.record_agent_output(agent_name, output)
    
    def record_routing_decision(self, 
                               supervisor_name: str, 
                               decision: Dict[str, Any],
                               duration_ms: float) -> AgentEvent:
        """Record routing decision with streaming"""
        event = super().record_routing_decision(supervisor_name, decision, duration_ms)
        
        # Stream the routing decision
        reasoning = decision.get("reasoning", "No reasoning provided")
        self.stream.record_routing_decision(supervisor_name, decision, reasoning)
        
        return event
    
    def record_agent_interaction(self, from_agent: str, to_agent: str, action: str, data: Dict[str, Any]):
        """Record interaction between agents"""
        self.stream.record_agent_interaction(from_agent, to_agent, action, data)
    
    def get_stream(self) -> EventStream:
        """Get event stream"""
        return self.stream
    
    def print_real_time_summary(self):
        """Print real-time summary of current activities"""
        recent_events = self.stream.get_recent_events(10)
        
        if not recent_events:
            print("\n📭 No recent events")
            return
        
        print("\n" + "="*60)
        print("REAL-TIME ACTIVITY STREAM")
        print("="*60)
        
        for event in recent_events[-5:]:  # Last 5 events
            timestamp = event.get('timestamp', '').split('T')[1][:12] if 'timestamp' in event else '--:--:--.--'
            
            if event.get('type') == 'interaction':
                print(f"[{timestamp}] {event['from']} → {event['to']}: {event['action']}")
            elif event.get('type') == 'output':
                print(f"[{timestamp}] {event['agent']} produced {event['output_type']}")
            elif event.get('type') == 'routing':
                print(f"[{timestamp}] {event['supervisor']} routed to {event['decision'].get('next_node', 'unknown')}")
            elif 'agent_name' in event:
                print(f"[{timestamp}] {event['agent_name']}: {event['event_type']}")
        
        print("="*60)


# Global streaming monitor instance
_global_streaming_monitor: Optional[StreamingMonitor] = None

def get_global_streaming_monitor() -> StreamingMonitor:
    """Get or create global streaming monitor instance"""
    global _global_streaming_monitor
    if _global_streaming_monitor is None:
        _global_streaming_monitor = StreamingMonitor()
    return _global_streaming_monitor


def monitor_agent_call_with_streaming(agent_name: str):
    """Decorator to monitor agent function calls with streaming"""
    from app.monitoring.basic_monitor import monitor_agent_call
    
    def decorator(func):
        # Use the existing monitor_agent_call decorator
        monitored_func = monitor_agent_call(agent_name)(func)
        
        async def async_wrapper(*args, **kwargs):
            monitor = get_global_streaming_monitor()
            
            # Record interaction if this is being called by another agent
            # (This would need context about caller, which is complex)
            
            result = await monitored_func(*args, **kwargs)
            
            # Try to extract output from result
            try:
                if hasattr(result, 'update') and isinstance(result.update, dict):
                    if 'messages' in result.update:
                        messages = result.update['messages']
                        if messages and hasattr(messages[-1], 'content'):
                            monitor.record_agent_output(agent_name, messages[-1].content)
            except Exception:
                pass
            
            return result
        
        def sync_wrapper(*args, **kwargs):
            monitor = get_global_streaming_monitor()
            
            result = monitored_func(*args, **kwargs)
            
            # Try to extract output from result
            try:
                if hasattr(result, 'update') and isinstance(result.update, dict):
                    if 'messages' in result.update:
                        messages = result.update['messages']
                        if messages and hasattr(messages[-1], 'content'):
                            monitor.record_agent_output(agent_name, messages[-1].content)
            except Exception:
                pass
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def test_streaming_monitor():
    """Test the streaming monitor"""
    print("Testing streaming monitor...")
    
    monitor = StreamingMonitor()
    stream = monitor.get_stream()
    
    # Record some events
    monitor.record_agent_interaction("main_supervisor", "research_team", "delegate", {"task": "Research AI trends"})
    monitor.record_agent_output("web_researcher", "Found 10 articles about AI trends in 2024")
    monitor.record_routing_decision(
        "research_supervisor",
        {"next_node": "data_analyst", "confidence": 0.85, "reasoning": "Need data analysis"},
        250.3
    )
    monitor.record_agent_interaction("research_supervisor", "data_analyst", "assign", {"analysis_type": "trend"})
    monitor.record_agent_output("data_analyst", "Analysis complete: AI adoption growing 30% YoY")
    
    # Print real-time summary
    monitor.print_real_time_summary()
    
    # Generate Mermaid diagram
    print("\n📊 Workflow Diagram (Mermaid):")
    print(stream.generate_mermaid_diagram())
    
    print("\n✅ Streaming monitor test completed!")


if __name__ == "__main__":
    test_streaming_monitor()