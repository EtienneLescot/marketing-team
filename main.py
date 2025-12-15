#!/usr/bin/env python3
"""
Main entry point for the Marketing Agents System.
This script provides a unified interface to run marketing tasks using the
enhanced hierarchical agent implementation.
"""

import asyncio
import sys
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage
from app.agents.hierarchical_marketing import create_marketing_workflow


async def run_marketing_task(task_description: str):
    """Run a marketing task with the hierarchical agents."""
    print(f"Running task: {task_description}")
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
    
    # Display results
    print("\n✅ Task completed!")
    print(f"Status: {result.get('workflow_status', 'unknown')}")
    print(f"Iterations: {result.get('iteration_count', 0)}")
    print(f"Current team: {result.get('current_team', 'none')}")
    
    print("\n📋 Team Output:")
    messages = result.get("messages", [])
    
    if not messages:
        print("  The team didn't generate any output.")
        print("  This could be because:")
        print("  1. The workflow terminated early (iteration limit reached)")
        print("  2. There was an error in agent execution")
        print("  3. Messages weren't propagated back to the main workflow")
    else:
        # Filter to show only agent responses (not the original user message)
        agent_messages = []
        for msg in messages:
            # Show AIMessages (agent responses)
            if isinstance(msg, AIMessage):
                agent_messages.append(msg)
            # Also show any message with a name (agent identifier)
            elif hasattr(msg, 'name') and msg.name and msg.name not in ['user', 'system']:
                agent_messages.append(msg)
        
        if not agent_messages:
            print("  No agent responses in the output.")
            print("  Raw messages found:")
            for i, msg in enumerate(messages):
                msg_type = type(msg).__name__
                msg_name = getattr(msg, 'name', 'no name')
                preview = msg.content[:100].replace('\n', ' ') + ('...' if len(msg.content) > 100 else '')
                print(f"    [{i}] {msg_type} (name: {msg_name}): {preview}")
        else:
            print(f"  Team generated {len(agent_messages)} responses:")
            for msg in agent_messages:
                agent_name = getattr(msg, 'name', 'unknown_agent')
                print(f"\n{'='*60}")
                print(f"AGENT: {agent_name}")
                print(f"{'='*60}")
                print(msg.content)
                print(f"{'='*60}")
    
    # Show monitoring summary
    from app.monitoring.basic_monitor import get_global_monitor
    monitor = get_global_monitor()
    monitor.print_summary()
    
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
