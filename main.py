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

async def run_marketing_task(task_description: str):
    """Run a marketing task with the hierarchical agents."""
    console.print(Panel(f"[bold blue]Task:[/bold blue] {task_description}", title="🚀 Marketing Agent System", border_style="blue"))
    
    # Get streaming monitor
    monitor = get_global_streaming_monitor()
    
    # CRITICAL FIX: Ensure basic monitor uses the same instance
    from app.monitoring import basic_monitor
    basic_monitor._global_monitor = monitor
    
    stream = monitor.get_stream()
    
    # Create a layout for live monitoring
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3)
    )
    
    # Store history for display
    event_history = []
    active_agents = set()
    
    def create_status_table():
        table = Table(title="Active Agents", box=box.ROUNDED)
        table.add_column("Agent", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Last Activity", style="dim")
        
        if not active_agents:
            table.add_row("System", "Idle", datetime.now().strftime("%H:%M:%S"))
        else:
            for agent in active_agents:
                table.add_row(agent, "Working...", datetime.now().strftime("%H:%M:%S"))
        return table

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
                if agent in active_agents:
                    active_agents.discard(agent)
            
            elif event.get('type') == 'routing':
                supervisor = event.get('supervisor', 'unknown')
                next_node = event.get('decision', {}).get('next_node', 'unknown')
                confidence = event.get('decision', {}).get('confidence', '?')
                reasoning = event.get('reasoning', '')
                
                msg = f"[bold magenta]🧭 COORDINATOR ({supervisor}):[/bold magenta] Routing to [bold cyan]{next_node}[/bold cyan] (Conf: {confidence})"
                console.print(f"[{timestamp}] {msg}")
                if reasoning:
                    console.print(f"   [dim]Reasoning: {reasoning}[/dim]")
            
            elif 'agent_name' in event:
                agent = event['agent_name']
                etype = event['event_type']
                
                if "start" in etype:
                    active_agents.add(agent)
                    color = "green"
                    icon = "▶️"
                elif "complete" in etype:
                    active_agents.discard(agent)
                    color = "blue"
                    icon = "✅"
                elif "error" in etype:
                    active_agents.discard(agent)
                    color = "red"
                    icon = "❌"
                else:
                    color = "white"
                    icon = "🤖"
                
                msg = f"{icon} [bold {color}]{agent}[/bold {color}]: {etype}"
                console.print(f"[{timestamp}] {msg}")
                
                # Print specific data if available (e.g. tool usage)
                if event.get('data') and 'tool_name' in event['data']:
                     tool = event['data']['tool_name']
                     console.print(f"   🛠️  Using tool: [bold]{tool}[/bold]")

        except Exception as e:
            console.print(f"[red]Error displaying event: {e}[/red]")

    # Subscribe to stream
    stream.subscribe(print_event)
    
    console.print("[dim]Starting monitor...[/dim]")
    
    # Create workflow
    workflow = create_marketing_workflow()
    
    # Execute task with progress spinner
    with console.status("[bold green]Executing Marketing Workflow...[/bold green]", spinner="dots"):
        result = await workflow.ainvoke({
            "messages": [HumanMessage(content=task_description)],
            "iteration_count": 0,
            "workflow_status": "running",
            "start_time": datetime.now()
        })
    
    # Display final results
    console.print(Panel("Task Completed Successfully", style="bold green"))
    
    # Show output messages
    messages = result.get("messages", [])
    if messages:
        for msg in messages:
            if isinstance(msg, AIMessage) or (hasattr(msg, 'name') and msg.name not in ['user', 'system']):
                name = getattr(msg, 'name', 'Assistant')
                console.print(Panel(msg.content, title=f"📄 Final Output: {name}", border_style="blue"))

    return result

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
