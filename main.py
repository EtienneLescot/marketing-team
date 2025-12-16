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
from app.agents.graph_builder import create_config_driven_workflow
from app.monitoring.streaming_monitor import get_global_streaming_monitor

# Rich imports
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.tree import Tree
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()


from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from langgraph.errors import GraphInterrupt

async def run_marketing_task(task_description: str):
    """Run a marketing task with the hierarchical agents and HITL support."""
    console.print(Panel(f"[bold blue]Task:[/bold blue] {task_description}", title="🚀 Marketing Agent System", border_style="blue"))
    
    # Get streaming monitor
    monitor = get_global_streaming_monitor()
    
    # CRITICAL FIX: Ensure basic monitor uses the same instance
    from app.monitoring import basic_monitor
    basic_monitor._global_monitor = monitor
    
    stream = monitor.get_stream()
    
    # Identify event type and create rich output
    def print_event(event):
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Identify event type and create rich output
            if event.get('type') == 'interaction':
                msg = f"[bold yellow]🔄 ROUTING:[/bold yellow] {event['from']} → {event['to']}"
                console.print(f"[{timestamp}] {msg}")
                
            elif event.get('type') == 'output':
                agent = event.get('agent', 'unknown')
                output = event.get('output', '')
                console.print(Panel(output, title=f"🗣️  Output from [bold cyan]{agent}[/bold cyan]", border_style="green"))

            elif event.get('type') == 'prompt':
                agent = event.get('agent', 'unknown')
                prompt = event.get('prompt', '')
                console.print(Panel(prompt, title=f"📝 Prompt for [bold yellow]{agent}[/bold yellow]", border_style="yellow", style="dim"))

            
            elif event.get('type') == 'routing':
                supervisor = event.get('supervisor', 'unknown')
                next_node = event.get('decision', {}).get('next_node', 'unknown')
                confidence = event.get('decision', {}).get('confidence', '?')
                reasoning = event.get('reasoning', '')
                
                msg = f"[bold magenta]🧭 COORDINATOR ({supervisor}):[/bold magenta] Routing to [bold cyan]{next_node}[/bold cyan] (Conf: {confidence})"
                console.print(f"[{timestamp}] {msg}")
                if reasoning:
                    console.print(f"   [dim]Reasoning: {reasoning}[/dim]")
                
                instructions = event.get('decision', {}).get('instructions', '')
                if instructions:
                    console.print(f"   [bold yellow]Instructions: {instructions}[/bold yellow]")
            
            elif 'agent_name' in event:
                agent = event['agent_name']
                etype = event['event_type']
                
                if "waiting_for_approval" in etype:
                     # Handled by the interrupt logic, but we can log it
                     pass
                elif "start" in etype:
                    color = "green"
                    icon = "▶️"
                    msg = f"{icon} [bold {color}]{agent}[/bold {color}]: started"
                    console.print(f"[{timestamp}] {msg}")
                elif "complete" in etype:
                    color = "blue"
                    icon = "✅"
                    msg = f"{icon} [bold {color}]{agent}[/bold {color}]: completed"
                    console.print(f"[{timestamp}] {msg}")
                elif "error" in etype:
                    color = "red"
                    icon = "❌"
                    msg = f"{icon} [bold {color}]{agent}[/bold {color}]: error"
                    console.print(f"[{timestamp}] {msg}")
                else:
                    color = "white"
                    icon = "🤖"
                    # msg = f"{icon} [bold {color}]{agent}[/bold {color}]: {etype}"
                    # console.print(f"[{timestamp}] {msg}")
                
                # Print specific data if available (e.g. tool usage)
                if event.get('data') and 'tool_name' in event['data']:
                     tool = event['data']['tool_name']
                     console.print(f"   🛠️  Using tool: [bold]{tool}[/bold]")

        except Exception as e:
            console.print(f"[red]Error displaying event: {e}[/red]")

    # Subscribe to stream
    sub = stream.subscribe(print_event)
    
    console.print("[dim]Starting monitor...[/dim]")
    
    # Initialize MemorySaver for persistence
    memory = MemorySaver()
    
    # Create workflow with checkpointer
    workflow = create_config_driven_workflow(checkpointer=memory)
    
    # Thread config for persistence
    thread_config = {"configurable": {"thread_id": "1"}}
    
    # Initial input
    initial_input = {
        "messages": [HumanMessage(content=task_description)],
        "iteration_count": 0,
        "workflow_status": "running",
        "start_time": datetime.now()
    }
    
    current_input = initial_input
    resume_mode = False
    
    while True:
        try:
            # Execute with streaming to catch interrupts
            # We look for the `__interrupt__` event or just interruption of the stream
            
            # Using basic invoke for simplicity as interrupt handling raises GraphInterrupt
            # But wait, with checkpointer, we need to inspect state after run
            
            # Streaming approach
            async for event in workflow.astream(current_input if not resume_mode else Command(resume=current_input), thread_config):
                pass
            
            # If we reach here without exception, check if finished
            snapshot = workflow.get_state(thread_config)
            if not snapshot.next:
                console.print(Panel("Task Completed Successfully", style="bold green"))
                break
            else:
                # If there are next steps but stream finished, we might be interrupted? 
                # Actually, stream() yields events. If it pauses for interrupt, it just stops yielding.
                # We need to check if there are tasks and if they have interrupts.
                if snapshot.tasks and snapshot.tasks[0].interrupts:
                    interrupt_value = snapshot.tasks[0].interrupts[0].value
                    console.print(Panel(f"[bold red]INTERRUPT:[/bold red] {interrupt_value}", border_style="red"))
                    
                    # Ask user for input
                    user_input = console.input("[bold yellow]Enter 'approved' to publish or providing feedback:[/bold yellow] ")
                    
                    # Prepare to resume
                    current_input = user_input
                    resume_mode = True
                    continue
            
            break

        except GraphInterrupt:
            # Handle interrupt specifically if raised
            snapshot = workflow.get_state(thread_config)
            if snapshot.tasks and snapshot.tasks[0].interrupts:
                interrupt_value = snapshot.tasks[0].interrupts[0].value
                console.print(Panel(f"[bold red]INTERRUPT:[/bold red] {interrupt_value}", border_style="red"))
                
                # Ask user for input
                user_input = console.input("[bold yellow]Enter 'approved' to publish or providing feedback:[/bold yellow] ")
                
                # Prepare to resume
                current_input = user_input
                resume_mode = True
                continue
            else:
                 console.print("[yellow]Graph interrupted but no interrupt value found.[/yellow]")
                 break

        except Exception as e:
            console.print(f"[red]Error during execution: {e}[/red]")
            import traceback
            traceback.print_exc()
            break
            
    # Final cleanup
    # stream.unsubscribe(sub) # if subscribe returns anything, standard doesn't return handle usually or depends on impl
    
    # Display final results
    snapshot = workflow.get_state(thread_config)
    messages = snapshot.values.get("messages", [])
    if messages:
        for msg in messages:
            if isinstance(msg, AIMessage) or (hasattr(msg, 'name') and msg.name not in ['user', 'system']):
                name = getattr(msg, 'name', 'Assistant')
                console.print(Panel(msg.content, title=f"📄 Final Output: {name}", border_style="blue"))

    return snapshot.values


def print_help():
    """Print help information."""
    console = Console()
    console.print(Panel("Marketing Agents System", style="bold blue"))
    console.print("Usage:")
    console.print("  uv run python main.py \"Your task\"")
    console.print("  uv run python main.py --interactive")

async def interactive_mode():
    """Run in interactive mode."""
    console.print(Panel("Interactive Mode", style="bold green"))
    while True:
        try:
            task = console.input("\n[bold]Enter task (or 'quit' to exit):[/bold] ")
            if task.lower() in ["quit", "exit", "q"]:
                break
            if task:
                await run_marketing_task(task)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

async def main():
    """Main entry point."""
    if len(sys.argv) == 1:
        print_help()
        return
    
    if sys.argv[1] == "--interactive":
        await interactive_mode()
    else:
        task = " ".join(sys.argv[1:])
        await run_marketing_task(task)

if __name__ == "__main__":
    asyncio.run(main())
