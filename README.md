# Marketing Agents - Hierarchical Agent System

A production-ready hierarchical agent system for marketing automation, built with LangGraph and following best practices from the LangGraph hierarchical agent teams tutorial.

## Features

- **Hierarchical Supervision**: Multi-level agent teams (main supervisor → team supervisors → specialists)
- **LLM-Based Routing**: Intelligent task delegation with structured JSON validation
- **Real Tool Integration**: Tavily search API with caching and error handling
- **Comprehensive Monitoring**: Event tracking, performance metrics, and agent statistics
- **Production-Ready**: Error handling, fallback mechanisms, and graceful degradation

## Architecture

```
Main Supervisor
├── Research Team
│   ├── Web Researcher (Tavily search)
│   └── Data Analyst
├── Content Team
│   ├── Content Writer
│   └── SEO Specialist
└── Social Media Team
    ├── LinkedIn Manager
    └── Twitter Manager
```

## Quick Start

### 1. Installation

```bash
# Install dependencies
uv sync
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```bash
# API Keys
OPENROUTER_API_KEY=your_openrouter_key_here
TAVILY_API_KEY=your_tavily_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here
MISTRAL_API_KEY=your_mistral_key_here

# Optional: Enable debug mode
DEBUG=true
```

**Important**: The `.env` file is automatically loaded when any module from the `app` package is imported. You don't need to set environment variables manually in commands.

### 3. Running Tests

```bash
# No need to set TAVILY_API_KEY manually - it's loaded from .env
uv run python test_new_implementation.py
```

### 4. Running the System

```python
from app.agents.hierarchical_marketing import create_marketing_workflow

workflow = create_marketing_workflow()
result = await workflow.ainvoke({
    "messages": [HumanMessage(content="Research AI marketing trends")],
    "iteration_count": 0
})
```

## Environment Variables

The system automatically loads environment variables from `.env` file through:

1. `app/__init__.py` - Loads `.env` when any app module is imported
2. `agent_config.py` - Also loads `.env` for backward compatibility

### Available Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `OPENROUTER_API_KEY` | LLM API access | Yes |
| `TAVILY_API_KEY` | Web search API | Yes |
| `DEEPSEEK_API_KEY` | Alternative LLM | No |
| `MISTRAL_API_KEY` | Alternative LLM | No |
| `DEBUG` | Enable debug output | No |

## Testing

### Running All Tests

```bash
# All tests automatically use .env file
uv run python test_new_implementation.py
uv run python test_monitoring.py
uv run python debug_tavily_error.py
```

### Test Coverage

- ✅ Research tasks with real web search
- ✅ Content creation tasks
- ✅ Mixed research+content workflows
- ✅ Error handling and fallbacks
- ✅ Monitoring and metrics collection

## Project Structure

```
.
├── app/
│   ├── __init__.py           # Loads .env file automatically
│   ├── agents/
│   │   └── hierarchical_marketing.py  # Main agent implementation
│   ├── models/
│   │   └── state_models.py   # Pydantic state models
│   ├── routing/
│   │   └── structured_router.py  # LLM-based routing
│   ├── tools/
│   │   ├── tool_registry.py  # Tool management
│   │   └── tavily_search.py  # Tavily API integration
│   ├── monitoring/
│   │   └── basic_monitor.py  # Monitoring system
│   └── utils/
│       └── message_utils.py  # Message processing utilities
├── tests/                    # Test suite
├── .env                     # Environment variables (gitignored)
├── pyproject.toml          # Dependencies
├── uv.lock                 # Lock file
└── README.md               # This file
```

## Development

### Adding New Tools

1. Create tool in `app/tools/`
2. Register in `app/tools/tool_registry.py`
3. Add to appropriate agent in `app/agents/hierarchical_marketing.py`

### Adding New Agents

1. Define agent configuration in `agent_config.py`
2. Implement agent node in `app/agents/hierarchical_marketing.py`
3. Update routing logic in `app/routing/structured_router.py`

### Monitoring

The system includes a basic monitoring system that tracks:
- Agent start/complete events
- Tool calls and durations
- Routing decisions
- Errors and exceptions

View monitoring summary:
```python
from app.monitoring.basic_monitor import get_global_monitor
monitor = get_global_monitor()
monitor.print_summary()
```

## Production Deployment

### Requirements
- Python 3.12+
- UV package manager
- API keys for LLM and search services

### Steps
1. Set up `.env` file with production API keys
2. Run comprehensive test suite
3. Deploy with proper error monitoring
4. Set up alerting for critical errors

## Troubleshooting

### Common Issues

**"TAVILY_API_KEY not set"**
- Ensure `.env` file exists in project root
- Check that `TAVILY_API_KEY` is set in `.env`
- Verify the `.env` file is being loaded (set `DEBUG=true`)

**Import errors**
- Run `uv sync` to install dependencies
- Check Python version (requires 3.12+)

**API errors**
- Check API key validity
- Verify rate limits and quotas
- Enable debug mode for detailed error messages

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Based on LangGraph hierarchical agent teams tutorial
- Uses Tavily for web search
- Built with LangChain and LangGraph