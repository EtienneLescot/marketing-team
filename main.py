#!/usr/bin/env python3
"""
Main entry point for the Agent Orchestration System.
This script provides a unified interface to run agent workflows using the
dynamic, configuration-driven graph builder with real-time monitoring.
"""

import asyncio
import sys
import argparse
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage
from app.agents.dynamic_graph_builder import DynamicGraphBuilder, create_dynamic_workflow
from app.monitoring.streaming_monitor import get_global_streaming_monitor

# Rich imports
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()


from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from langgraph.errors import GraphInterrupt

async def run_task(task_description: str, config_path: str = "config/agents.yaml", entry_point: str = "main_supervisor"):
    """Run a task with configurable agents and entry points."""
    console.print(Panel(
        f"[bold blue]Task:[/bold blue] {task_description}\n"
        f"[dim]Config: {config_path}[/dim]\n"
        f"[dim]Entry point: {entry_point}[/dim]",
        title="🚀 Agent Orchestration System",
        border_style="blue"
    ))
    
    # Initialize DynamicGraphBuilder
    try:
        builder = DynamicGraphBuilder(config_path)
    except FileNotFoundError as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        console.print("[yellow]Available configs:[/yellow]")
        await _list_available_configs(console)
        return
    
    # Validate entry point
    if not builder.validate_entry_point(entry_point):
        console.print(f"[red]Error: Entry point '{entry_point}' not found in config[/red]")
        console.print("[yellow]Available entry points:[/yellow]")
        await _list_available_entry_points(config_path, console)
        return
    
    # Validate configuration
    validation_errors = builder.validate_config_for_graph()
    if validation_errors:
        console.print("[red]Configuration errors found:[/red]")
        for error in validation_errors:
            console.print(f"  - {error}")
        
        if any("Cycle detected" in e for e in validation_errors):
            console.print("[bold red]Fatal: Cycle detected in agent hierarchy. Fix config before proceeding.[/bold red]")
            return
        
        # Ask for confirmation if there are warnings
        confirm = console.input("[yellow]Continue despite warnings? (y/N): [/yellow]")
        if confirm.lower() != 'y':
            return
    
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
    workflow = builder.build_graph(entry_point=entry_point, checkpointer=memory)
    
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


async def _list_available_configs(console: Console):
    """List all available configuration files"""
    console.print(Panel("Available Configurations", style="bold green"))
    
    config_dir = Path("config")
    if not config_dir.exists():
        console.print("[yellow]No config directory found[/yellow]")
        return
    
    configs = []
    for file in config_dir.glob("*.yaml"):
        try:
            with open(file, 'r') as f:
                config = yaml.safe_load(f)
            
            configs.append({
                "name": file.stem,
                "path": str(file),
                "description": config.get("description", ""),
                "agent_count": len(config.get("agents", [])),
                "inherits": config.get("inherit_from")
            })
        except Exception as e:
            configs.append({
                "name": file.stem,
                "path": str(file),
                "error": f"Failed to parse: {e}"
            })
    
    if not configs:
        console.print("[dim]No YAML config files found in config/ directory[/dim]")
        return
    
    # Create table
    table = Table(title="Configuration Files", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Agents", style="green")
    table.add_column("Description", style="white")
    table.add_column("Inherits", style="dim")
    table.add_column("Path", style="dim")
    
    for config in configs:
        if "error" in config:
            table.add_row(
                config["name"],
                "ERROR",
                config["error"],
                "",
                config["path"]
            )
        else:
            table.add_row(
                config["name"],
                str(config["agent_count"]),
                config["description"][:50] + "..." if len(config["description"]) > 50 else config["description"],
                config["inherits"] or "",
                config["path"]
            )
    
    console.print(table)
    
    # Show usage examples
    console.print("\n[bold]Usage Examples:[/bold]")
    console.print("  uv run python main.py --config research_team \"Research competitors\"")
    console.print("  uv run python main.py --config config/custom.yaml \"Custom task\"")


async def _list_available_entry_points(config_path: str, console: Console):
    """List available entry points for a configuration"""
    try:
        builder = DynamicGraphBuilder(config_path)
    except FileNotFoundError as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        return
    
    entry_points = builder.list_available_entry_points()
    
    console.print(Panel(f"Entry Points for: {config_path}", style="bold green"))
    
    if not entry_points:
        console.print("[yellow]No agents found in configuration[/yellow]")
        return
    
    # Create table
    table = Table(title="Available Entry Points", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Managed Agents", style="white")
    table.add_column("Tools", style="dim")
    table.add_column("Approval", style="dim")
    
    for ep in entry_points:
        managed_str = ", ".join(ep["managed_agents"][:3])
        if len(ep["managed_agents"]) > 3:
            managed_str += f" (+{len(ep['managed_agents']) - 3} more)"
        
        tools_str = "Yes" if ep["has_tools"] else "No"
        approval_str = "Yes" if ep["require_approval"] else "No"
        
        table.add_row(
            ep["name"],
            ep["type"],
            managed_str or "None",
            tools_str,
            approval_str
        )
    
    console.print(table)
    
    # Show usage examples
    console.print("\n[bold]Usage Examples:[/bold]")
    console.print(f"  uv run python main.py --config {config_path} --entry-point main_supervisor \"Full workflow\"")
    console.print(f"  uv run python main.py --config {config_path} --entry-point content_team_supervisor \"Content task\"")
    console.print(f"  uv run python main.py --config {config_path} --entry-point web_researcher \"Research task\"")


async def _validate_configuration(config_path: str, console: Console):
    """Validate configuration file"""
    console.print(Panel(f"Validating: {config_path}", style="bold yellow"))
    
    try:
        builder = DynamicGraphBuilder(config_path)
    except FileNotFoundError as e:
        console.print(f"[red]❌ Config file not found: {e}[/red]")
        return
    except Exception as e:
        console.print(f"[red]❌ Failed to load config: {e}[/red]")
        return
    
    # Validate configuration
    errors = builder.validate_config_for_graph()
    
    if not errors:
        console.print("[green]✅ Configuration is valid[/green]")
        
        # Show summary
        entry_points = builder.list_available_entry_points()
        supervisors = [ep for ep in entry_points if ep["type"] == "supervisor"]
        workers = [ep for ep in entry_points if ep["type"] == "worker"]
        
        console.print(f"\n[dim]Summary:[/dim]")
        console.print(f"  Total agents: {len(entry_points)}")
        console.print(f"  Supervisors: {len(supervisors)}")
        console.print(f"  Workers: {len(workers)}")
        
        # Show hierarchy
        console.print(f"\n[dim]Hierarchy:[/dim]")
        for ep in entry_points:
            if ep["managed_agents"]:
                console.print(f"  {ep['name']} → {', '.join(ep['managed_agents'])}")
    else:
        console.print("[red]❌ Configuration has errors:[/red]")
        for error in errors:
            console.print(f"  - {error}")


async def interactive_mode(config_path: str = "config/agents.yaml"):
    """Run in interactive mode with configurable options."""
    console = Console()
    console.print(Panel("Interactive Mode", style="bold green"))
    
    # Load builder for validation
    try:
        builder = DynamicGraphBuilder(config_path)
        console.print(f"[dim]Using config: {config_path}[/dim]")
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        console.print("[yellow]Falling back to default config[/yellow]")
        config_path = "config/agents.yaml"
        builder = DynamicGraphBuilder(config_path)
    
    while True:
        try:
            # Show available entry points
            entry_points = builder.list_available_entry_points()
            console.print("\n[bold]Available entry points:[/bold]")
            for ep in entry_points[:5]:  # Show first 5
                console.print(f"  [cyan]{ep['name']}[/cyan] ({ep['type']})")
            if len(entry_points) > 5:
                console.print(f"  ... and {len(entry_points) - 5} more")
            
            # Get task
            task = console.input("\n[bold]Enter task (or 'quit'/'config'/'validate'/'list'):[/bold] ")
            
            if task.lower() in ["quit", "exit", "q"]:
                break
            elif task.lower() == "config":
                new_config = console.input("[bold]Enter config path:[/bold] ")
                try:
                    builder = DynamicGraphBuilder(new_config)
                    config_path = new_config
                    console.print(f"[green]Switched to config: {config_path}[/green]")
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
                continue
            elif task.lower() == "validate":
                await _validate_configuration(config_path, console)
                continue
            elif task.lower() == "list":
                await _list_available_entry_points(config_path, console)
                continue
            
            # Get entry point
            entry_point = console.input("[bold]Enter entry point (default: main_supervisor):[/bold] ")
            if not entry_point:
                entry_point = "main_supervisor"
            
            # Validate entry point
            if not builder.validate_entry_point(entry_point):
                console.print(f"[red]Invalid entry point: {entry_point}[/red]")
                continue
            
            # Run task
            await run_task(
                task_description=task,
                config_path=config_path,
                entry_point=entry_point
            )
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def print_help():
    """Print enhanced help information."""
    console = Console()
    
    console.print(Panel("""
    🚀 Agent Orchestration System
    Dynamic, configuration-driven agent workflows
    """, style="bold blue"))
    
    console.print("\n[bold]Usage:[/bold]")
    console.print("  uv run python main.py \"Your task\"")
    console.print("  uv run python main.py --interactive")
    console.print("  uv run python main.py --config research_team \"Research task\"")
    console.print("  uv run python main.py --entry-point content_team_supervisor \"Content task\"")
    
    console.print("\n[bold]Options:[/bold]")
    console.print("  -i, --interactive        Run in interactive mode")
    console.print("  -c, --config PATH        Configuration file (default: config/agents.yaml)")
    console.print("  -e, --entry-point NAME   Entry point agent (default: main_supervisor)")
    console.print("  -l, --list-entry-points  List available entry points for config")
    console.print("  -L, --list-configs       List available configuration files")
    console.print("  -V, --validate           Validate configuration only")
    console.print("  -h, --help               Show this help message")
    
    console.print("\n[bold]Examples:[/bold]")
    console.print("  # Full workflow with default config")
    console.print("  uv run python main.py \"Research competitors and create social media posts\"")
    
    console.print("\n  # Content team only")
    console.print("  uv run python main.py --config config/agents.yaml --entry-point content_team_supervisor \"Write blog post about AI\"")
    
    console.print("\n  # Single agent")
    console.print("  uv run python main.py --entry-point web_researcher \"Find latest marketing trends\"")
    
    console.print("\n  # Custom configuration")
    console.print("  uv run python main.py --config config/custom_team.yaml \"Execute custom workflow\"")
    
    console.print("\n  # Interactive mode with custom config")
    console.print("  uv run python main.py --interactive --config research_team")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Agent Orchestration System")
    parser.add_argument("task", nargs="?", help="Task description to execute")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument("--config", "-c", default="config/agents.yaml", help="Configuration file path")
    parser.add_argument("--entry-point", "-e", default="main_supervisor", help="Entry point agent name")
    parser.add_argument("--list-entry-points", "-l", action="store_true", help="List available entry points")
    parser.add_argument("--list-configs", "-L", action="store_true", help="List available configurations")
    parser.add_argument("--validate", "-V", action="store_true", help="Validate configuration only")
    
    args = parser.parse_args()
    
    # Handle listing modes
    if args.list_configs:
        await _list_available_configs(Console())
        return
    
    if args.list_entry_points:
        await _list_available_entry_points(args.config, Console())
        return
    
    # Handle validation mode
    if args.validate:
        await _validate_configuration(args.config, Console())
        return
    
    # Handle interactive mode
    if args.interactive:
        await interactive_mode(args.config)
        return
    
    # Handle regular task execution
    if args.task:
        await run_task(
            task_description=args.task,
            config_path=args.config,
            entry_point=args.entry_point
        )
    else:
        print_help()


if __name__ == "__main__":
    asyncio.run(main())
