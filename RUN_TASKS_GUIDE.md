# How to Run Tasks with Marketing Agents

## Consolidated Implementation

The project has been cleaned up to use a single, production-ready implementation:

### **Enhanced Hierarchical Implementation** (`app/agents/hierarchical_marketing.py`)
- Hierarchical supervisor pattern (LangGraph best practice)
- LLM-based routing with structured JSON validation
- Real Tavily search API integration
- Comprehensive monitoring and error handling
- **Recommended for production use**

**Note**: The original `marketing_agents.py` implementation has been removed as it was a duplicate with mock tools.

## Running Tasks

### Main Entry Point: `main.py`

The system provides a unified command-line interface through `main.py`:

#### Interactive Mode
```bash
uv run python main.py --interactive
```
Start an interactive session where you can type marketing tasks and see results in real-time.

#### Single Task
```bash
uv run python main.py "Research AI marketing trends"
```

#### Help
```bash
uv run python main.py --help
```

### Example Tasks to Try

#### Research Tasks
- "Research AI marketing trends for 2024"
- "Analyze competitor social media strategies"
- "Find the latest digital marketing tools"

#### Content Tasks
- "Create a blog post about GitHub project promotion"
- "Write social media content for a tech startup"
- "Create an email marketing campaign for a SaaS product"

#### Mixed Tasks
- "Research and create content about web3 marketing"
- "Analyze social media performance and suggest improvements"
- "Create a comprehensive marketing strategy for an open source project"

## Programmatic Usage

You can also use the system programmatically:

```python
import asyncio
from app.agents.hierarchical_marketing import create_marketing_workflow
from langchain_core.messages import HumanMessage

async def run_custom_task():
    workflow = create_marketing_workflow()
    
    result = await workflow.ainvoke({
        "messages": [HumanMessage(content="Your marketing task here")],
        "iteration_count": 0,
        "workflow_status": "running"
    })
    
    # Process results
    for message in result["messages"]:
        if hasattr(message, 'name'):
            print(f"{message.name}: {message.content[:200]}...")
    
    return result

# Run the task
asyncio.run(run_custom_task())
```

## Environment Setup

Make sure your `.env` file is configured:
```bash
# API Keys (required)
OPENROUTER_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here

# Optional API keys
DEEPSEEK_API_KEY=your_key_here
MISTRAL_API_KEY=your_key_here
```

The `.env` file is automatically loaded when you run any script that imports from the `app` package.

## Testing the System

### Run Test Suite
```bash
uv run python test_new_implementation.py
```

### Test Tavily API Directly
```bash
uv run python test_tavily_api.py
```

### Test Monitoring System
```bash
uv run python test_monitoring.py
```

## Monitoring and Debugging

### View Monitoring Data
```python
from app.monitoring.basic_monitor import get_global_monitor
monitor = get_global_monitor()
monitor.print_summary()
```

The monitoring system tracks:
- Agent start/complete events
- Tool calls and durations
- Routing decisions
- Errors and exceptions

## Project Structure After Cleanup

```
.
├── app/                           # Main application code
│   ├── __init__.py               # Loads .env file automatically
│   ├── agents/
│   │   └── hierarchical_marketing.py  # Main agent implementation
│   ├── models/
│   │   └── state_models.py       # Pydantic state models
│   ├── routing/
│   │   └── structured_router.py  # LLM-based routing
│   ├── tools/
│   │   ├── tool_registry.py      # Tool management
│   │   └── tavily_search.py      # Tavily API integration
│   ├── monitoring/
│   │   └── basic_monitor.py      # Monitoring system
│   └── utils/
│       └── message_utils.py      # Message processing utilities
├── tests/                        # Test suite
├── main.py                       # Main entry point (CLI)
├── agent_config.py               # Agent configuration
├── .env                          # Environment variables (gitignored)
├── pyproject.toml                # Dependencies
├── uv.lock                       # Lock file
├── README.md                     # Project documentation
└── RUN_TASKS_GUIDE.md            # This guide
```

## Troubleshooting

### Common Issues

**"API key not found"**
- Ensure `.env` file exists in project root
- Check that API keys are correctly set
- Verify the `.env` file is being loaded (set `DEBUG=true` in `.env`)

**Import errors**
- Run `uv sync` to install dependencies
- Check Python version (requires 3.12+)

**Slow responses**
- The system uses real LLM calls and web search
- Complex tasks may take 30-60 seconds
- Check your internet connection and API rate limits

**"No such file or directory" errors**
- The project has been cleaned up
- Use `main.py` as the entry point instead of removed files

## Next Steps

1. **Start with test suite**: `uv run python test_new_implementation.py`
2. **Run example task**: `uv run python main.py "Research AI marketing trends"`
3. **Try interactive mode**: `uv run python main.py --interactive`
4. **Explore monitoring**: Check agent performance and tool usage statistics

The hierarchical implementation is production-ready and follows LangGraph best practices for agent teams.