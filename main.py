#!/usr/bin/env python3
"""
Main entry point for the Marketing Agents System.
This script provides a unified interface to run marketing tasks using the
enhanced hierarchical agent implementation with real-time monitoring.
"""

import asyncio
import sys
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage
from app.agents.hierarchical_marketing import create_marketing_workflow
from app.monitoring.streaming_monitor import get_global_streaming_monitor


async def run_marketing_task(task_description: str):
    """Run a marketing task with the hierarchical agents."""
    print(f"Running task: {task_description}")
    print("-" * 40)
    
    # Get streaming monitor
    monitor = get_global_streaming_monitor()
    stream = monitor.get_stream()
    
    print("\n🎬 Starting real-time monitoring...")
    print("   Agents will report activities as they happen.")
    print("   Coordinator decisions will be shown in real-time.")
    print("-" * 40)
    
    # Create workflow
    workflow = create_marketing_workflow()
    
    # Execute task
    result = await workflow.ainvoke({
        "messages": [HumanMessage(content=task_description)],
        "iteration_count": 0,
        "workflow_status": "running",
        "start_time": datetime.now()
    })
    
    # Display final results
    print("\n" + "="*60)
    print("✅ TASK COMPLETED!")
    print("="*60)
    print(f"Status: {result.get('workflow_status', 'unknown')}")
    print(f"Iterations: {result.get('iteration_count', 0)}")
    print(f"Current team: {result.get('current_team', 'none')}")
    
    # Show routing decision if available
    routing_decision = result.get("routing_decision")
    if routing_decision:
        print(f"\n📊 Final Routing Decision:")
        print(f"  Next node: {routing_decision.get('next_node')}")
        print(f"  Confidence: {routing_decision.get('confidence', 0):.2f}")
        print(f"  Reasoning: {routing_decision.get('reasoning', '')[:200]}...")
    
    print("\n📋 Team Output Summary:")
    messages = result.get("messages", [])
    
    if not messages:
        print("  The team didn't generate any output.")
    else:
        # Filter to show only agent responses
        agent_messages = []
        for msg in messages:
            if isinstance(msg, AIMessage):
                agent_messages.append(msg)
            elif hasattr(msg, 'name') and msg.name and msg.name not in ['user', 'system']:
                agent_messages.append(msg)
        
        if not agent_messages:
            print("  No agent responses in the output.")
        else:
            print(f"  Team generated {len(agent_messages)} responses:")
            for msg in agent_messages:
                agent_name = getattr(msg, 'name', 'unknown_agent')
                print(f"\n{'='*60}")
                print(f"AGENT: {agent_name}")
                print(f"{'='*60}")
                print(msg.content[:500] + ("..." if len(msg.content) > 500 else ""))
                print(f"{'='*60}")
    
    # Show real-time activity summary
    print("\n" + "="*60)
    print("📈 REAL-TIME ACTIVITY SUMMARY")
    print("="*60)
    monitor.print_real_time_summary()
    
    # Show workflow diagram
    print("\n" + "="*60)
    print("📊 WORKFLOW DIAGRAM (Mermaid.js)")
    print("="*60)
    mermaid_diagram = stream.generate_mermaid_diagram()
    print(mermaid_diagram)
    print("\n💡 Copy this diagram to https://mermaid.live/ to visualize")
    
    # Show monitoring summary
    print("\n" + "="*60)
    print("📊 AGENT MONITORING SUMMARY")
    print("="*60)
    from app.monitoring.basic_monitor import get_global_monitor
    basic_monitor = get_global_monitor()
    basic_monitor.print_summary()
    
    return result


def print_help():
    """Print help information."""
    print("Marketing Agents System - Usage")
    print("=" * 60)
    print("Run a marketing task:")
    print("  uv run python main.py \"Your marketing task description\"")
    print()
    print("Interactive mode:")
    print("  uv run python main.py --interactive")
    print()
    print("Example tasks:")
    print("  1. \"Research the latest trends in AI-powered marketing automation\"")
    print("  2. \"Create a blog post about effective social media strategies for B2B companies\"")
    print("  3. \"Analyze competitor social media presence and create content recommendations\"")
    print("  4. \"Research Python web frameworks for 2024 and create a comparison article\"")
    print()
    print("For detailed instructions, see RUN_TASKS_GUIDE.md")


async def interactive_mode():
    """Run in interactive mode."""
    print("Marketing Agents System - Interactive Mode")
    print("=" * 60)
    print("Type your marketing tasks (or 'quit' to exit):")
    
    while True:
        try:
            task = input("\n> ").strip()
            
            if task.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            elif task.lower() in ["help", "h"]:
                print_help()
            elif task:
                await run_marketing_task(task)
            else:
                print("Please enter a task or 'quit' to exit.")
                
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            print("Please try again.")


async def main():
    """Main entry point."""
    if len(sys.argv) == 1:
        print_help()
        return
    
    if sys.argv[1] == "--interactive":
        await interactive_mode()
    elif sys.argv[1] in ["--help", "-h"]:
        print_help()
    else:
        # Join all arguments as the task
        task = " ".join(sys.argv[1:])
        await run_marketing_task(task)


if __name__ == "__main__":
    asyncio.run(main())
