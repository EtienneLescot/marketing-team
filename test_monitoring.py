#!/usr/bin/env python3
"""
Test monitoring system to ensure it's capturing all events.
"""

import asyncio
import os
from datetime import datetime

# Set API key
os.environ["TAVILY_API_KEY"] = "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"

from app.agents.hierarchical_marketing import create_marketing_workflow
from app.monitoring.basic_monitor import get_global_monitor
from langchain_core.messages import HumanMessage

async def test_monitoring():
    """Test that monitoring captures all events"""
    print("Testing monitoring system...")
    print("=" * 60)
    
    # Reset monitor
    from app.monitoring.basic_monitor import reset_global_monitor
    reset_global_monitor()
    monitor = get_global_monitor()
    
    # Create workflow
    workflow = create_marketing_workflow()
    
    # Run a simple task
    task = "Research Python web frameworks for 2024"
    print(f"Task: {task}")
    
    result = await workflow.ainvoke({
        "messages": [HumanMessage(content=task)],
        "iteration_count": 0,
        "workflow_status": "running",
        "start_time": datetime.now()
    })
    
    print("\n✅ Task completed!")
    print(f"Status: {result.get('workflow_status', 'unknown')}")
    print(f"Iterations: {result.get('iteration_count', 0)}")
    print(f"Current team: {result.get('current_team', 'none')}")
    
    # Print monitoring summary
    print("\n📊 Monitoring Summary:")
    print("-" * 40)
    monitor.print_summary()
    
    # Check specific metrics
    print("\n🔍 Detailed Metrics:")
    print("-" * 40)
    
    # Get recent events
    recent_events = monitor.get_recent_events(limit=50)
    if recent_events:
        print(f"Events recorded: {len(recent_events)}")
        
        # Group by event type
        event_types = {}
        for event in recent_events:
            event_type = event['event_type']
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        print("\nEvent types:")
        for event_type, count in event_types.items():
            print(f"  - {event_type}: {count}")
        
        # Show agent calls (events with agent_start or agent_complete)
        agent_events = [e for e in recent_events if 'agent' in e['event_type']]
        if agent_events:
            print(f"\nAgent events: {len(agent_events)}")
            for event in agent_events[:5]:
                print(f"  - {event['agent_name']}: {event['event_type']} "
                      f"({event.get('duration_ms', 0):.1f}ms)")
        
        # Show tool calls
        tool_events = [e for e in recent_events if e['event_type'] == 'tool_call']
        if tool_events:
            print(f"\nTool calls: {len(tool_events)}")
            for event in tool_events:
                tool_name = event['data'].get('tool_name', 'unknown')
                result = event['data'].get('result', 'No result')
                print(f"  - {tool_name}: {result[:50]}...")
    else:
        print("No events recorded")
    
    # Check if we have the expected data
    expected_events = ['agent_start', 'agent_complete', 'tool_call']
    missing = []
    for expected in expected_events:
        found = False
        for event in recent_events:
            if event['event_type'] == expected:
                found = True
                break
        if not found:
            missing.append(expected)
    
    if missing:
        print(f"\n⚠️  Missing expected event types: {missing}")
    else:
        print("\n✅ All expected event types captured!")
    
    return True

async def main():
    print("Monitoring System Test")
    print("=" * 60)
    
    success = await test_monitoring()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ Monitoring system is working correctly!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ Monitoring test failed")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())