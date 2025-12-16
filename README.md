# Marketing Agents - Dynamic Configuration-Driven Agent System

A production-ready hierarchical agent system for marketing automation with dynamic, configuration-driven graph building. Built with LangGraph and featuring a flexible YAML-based configuration system.

## Features

- **Dynamic Configuration**: YAML-based agent configuration as single source of truth
- **Configuration Inheritance**: Hierarchical configuration with inheritance and overrides
- **Flexible Entry Points**: Start workflows from any agent (supervisor or worker)
- **Automatic Graph Building**: Recursive graph construction based on agent hierarchies
- **Cycle Detection**: Automatic validation to prevent infinite loops
- **Tool Integration**: Configurable tools per agent with environment variable support
- **Comprehensive Monitoring**: Real-time event tracking and performance metrics
- **Production-Ready**: Error handling, validation, and graceful degradation

## Architecture

The system dynamically builds agent graphs based on YAML configuration:

```
Main Supervisor (config/agents.yaml)
├── Research Team Supervisor
│   ├── Web Researcher (Tavily search)
│   └── Data Analyst
├── Content Team Supervisor
│   ├── Content Writer
│   ├── SEO Specialist
│   └── Visual Designer
└── Social Media Team Supervisor
    ├── LinkedIn Manager
    ├── Twitter Manager
    └── Analytics Tracker
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
# LLM API Keys
DEEPSEEK_API_KEY=your_deepseek_key_here
OPENAI_API_KEY=your_openai_key_here  # Optional

# Tool API Keys
TAVILY_API_KEY=your_tavily_key_here
LINKEDIN_API_KEY=your_linkedin_key_here  # Optional

# Optional: Enable debug mode
DEBUG=true
```

**Important**: The `.env` file is automatically loaded when any module from the `app` package is imported.

### 3. Running the System

#### Basic Usage

```bash
# Run with default configuration (main_supervisor entry point)
uv run python main.py "Research AI marketing trends"

# Run with specific configuration
uv run python main.py --config research_team "Research competitors"

# Run with specific entry point
uv run python main.py --entry-point content_team_supervisor "Write blog post about AI"

# Run single agent
uv run python main.py --entry-point web_researcher "Find latest trends"
```

#### Interactive Mode

```bash
# Interactive mode with default config
uv run python main.py --interactive

# Interactive mode with custom config
uv run python main.py --interactive --config research_team
```

#### Configuration Management

```bash
# List available configurations
uv run python main.py --list-configs

# List entry points for a configuration
uv run python main.py --list-entry-points --config research_team

# Validate configuration
uv run python main.py --validate --config config/agents.yaml

# Show help
uv run python main.py --help
```

#### Programmatic Usage

```python
from app.agents.dynamic_graph_builder import DynamicGraphBuilder
from langchain_core.messages import HumanMessage

# Create builder with configuration
builder = DynamicGraphBuilder("config/agents.yaml")

# Build graph with entry point
workflow = builder.build_graph(entry_point="main_supervisor")

# Execute workflow
result = await workflow.ainvoke({
    "messages": [HumanMessage(content="Research AI marketing trends")],
    "iteration_count": 0,
    "workflow_status": "running"
})
```

## Configuration System

### Configuration Files

The system uses YAML configuration files in the `config/` directory:

- `config/agents.yaml` - Main configuration with full agent hierarchy
- `config/research_team.yaml` - Research-focused team configuration
- `config/content_team.yaml` - Content creation team configuration
- `config/simple_team.yaml` - Minimal configuration for testing
- `config/inheritance_test.yaml` - Example of configuration inheritance
- `config/cycle_test.yaml` - Example with cycles for testing validation

### Configuration Structure

```yaml
# config/agents.yaml example
defaults:
  provider: "deepseek"
  model: "deepseek-chat"

providers:
  deepseek:
    base_url: "https://api.deepseek.com"
    api_key_env: "DEEPSEEK_API_KEY"

agents:
  - name: "main_supervisor"
    role: "supervisor"
    prompt_file: "supervisors/main.md"
    output_schema: "RouterResponse"
    managed_agents:
      - "research_team_supervisor"
      - "content_team_supervisor"

  - name: "web_researcher"
    role: "worker"
    prompt_file: "workers/web_researcher.md"
    tools:
      - "tavily_search"

tools:
  tavily_search:
    type: "tavily"
    api_key_env: "TAVILY_API_KEY"
    max_results: 5
```

### Configuration Inheritance

Configurations can inherit from other YAML files:

```yaml
# config/research_team.yaml
description: "Research-focused team"
inherit_from: "agents.yaml"

# Override defaults
defaults:
  provider: "deepseek"
  model: "deepseek-chat"

# Add or override agents
agents:
  - name: "research_supervisor"
    role: "supervisor"
    managed_agents:
      - "web_researcher"
      - "data_analyst"
```

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `DEEPSEEK_API_KEY` | DeepSeek LLM API access | Yes |
| `OPENAI_API_KEY` | OpenAI LLM API access | No |
| `TAVILY_API_KEY` | Tavily web search API | Yes |
| `LINKEDIN_API_KEY` | LinkedIn posting API | No |
| `DEBUG` | Enable debug output | No |

## Project Structure

```
.
├── app/
│   ├── agents/
│   │   ├── dynamic_graph_builder.py  # Dynamic graph construction
│   │   └── graph_builder.py          # Legacy graph builder
│   ├── models/
│   │   ├── agent_types.py            # Agent type definitions
│   │   ├── schemas.py                # Pydantic schemas
│   │   └── state_models.py           # State models
│   ├── routing/
│   │   └── structured_router.py      # LLM-based routing
│   ├── tools/
│   │   ├── tool_registry.py          # Tool management
│   │   ├── tavily_search.py          # Tavily API integration
│   │   ├── linkedin.py               # LinkedIn integration
│   │   └── mock_search.py            # Mock search for testing
│   ├── monitoring/
│   │   ├── basic_monitor.py          # Basic monitoring
│   │   └── streaming_monitor.py      # Real-time streaming monitor
│   └── utils/
│       ├── config_loader.py          # Configuration loading with inheritance
│       └── message_utils.py          # Message processing utilities
├── config/
│   ├── agents.yaml                   # Main configuration
│   ├── research_team.yaml            # Research team configuration
│   ├── content_team.yaml             # Content team configuration
│   ├── simple_team.yaml              # Simple test configuration
│   ├── inheritance_test.yaml         # Inheritance example
│   ├── cycle_test.yaml               # Cycle test configuration
│   └── prompts/                      # Agent prompt files
│       ├── supervisors/              # Supervisor prompts
│       └── workers/                  # Worker prompts
├── tests/                            # Test suite
├── .env                              # Environment variables
├── pyproject.toml                    # Dependencies
├── uv.lock                           # Lock file
└── README.md                         # This file
```

## Development

### Adding New Agents

1. **Create agent configuration** in YAML:
   ```yaml
   - name: "new_agent"
     role: "worker"
     prompt_file: "workers/new_agent.md"
     tools: ["tool_name"]
   ```

2. **Create prompt file** in `config/prompts/workers/new_agent.md`

3. **Add to supervisor's** `managed_agents` list

4. **Validate configuration**:
   ```bash
   uv run python main.py --validate --config your_config.yaml
   ```

### Adding New Tools

1. **Create tool implementation** in `app/tools/`

2. **Register tool** in `app/tools/tool_registry.py`

3. **Configure tool** in YAML:
   ```yaml
   tools:
     new_tool:
       type: "custom"
       api_key_env: "NEW_TOOL_API_KEY"
       param: "value"
   ```

4. **Assign tool to agents** in their configuration

### Creating Custom Configurations

1. **Start from a template**:
   ```bash
   cp config/simple_team.yaml config/my_team.yaml
   ```

2. **Edit the configuration** to define your agent hierarchy

3. **Test the configuration**:
   ```bash
   uv run python main.py --validate --config config/my_team.yaml
   uv run python main.py --config config/my_team.yaml "Test task"
   ```

## Testing

### Running Tests

```bash
# Run unit tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_dynamic_graph_builder.py -v

# Run with coverage
uv run pytest tests/ --cov=app --cov-report=html
```

### Test Coverage

- ✅ Dynamic graph building from configuration
- ✅ Configuration inheritance and merging
- ✅ Cycle detection and validation
- ✅ Entry point targeting
- ✅ Tool configuration integration
- ✅ Error handling and validation

## Production Deployment

### Requirements
- Python 3.12+
- UV package manager
- API keys for LLM and tool services

### Steps
1. Set up `.env` file with production API keys
2. Create production configuration in `config/production.yaml`
3. Run comprehensive test suite
4. Validate configuration: `uv run python main.py --validate --config config/production.yaml`
5. Deploy with proper error monitoring
6. Set up alerting for critical errors

## Troubleshooting

### Common Issues

**"Configuration file not found"**
- Ensure configuration file exists in `config/` directory
- Check file path spelling
- Verify file has `.yaml` extension

**"Cycle detected in agent hierarchy"**
- Review `managed_agents` references in your YAML
- Check for circular dependencies between agents
- Use validation to identify specific cycles

**"Agent not found in configuration"**
- Verify agent name spelling in entry point parameter
- Check that agent is defined in the configuration file
- Ensure configuration file is being loaded correctly

**"Tool not configured"**
- Add tool configuration to `tools` section of YAML
- Verify tool name matches exactly
- Check that tool is registered in `tool_registry.py`

**API errors**
- Check API key validity in `.env` file
- Verify rate limits and quotas
- Enable debug mode for detailed error messages

### LinkedIn-Specific Issues

**"LinkedIn API Error: 403 - ACCESS_DENIED"**
- **Personal profile posting**: Works with `w_member_social` scope
- **Company page posting**: Requires `w_organization_social` scope and admin access
- **Common causes**:
  1. Access token doesn't have required scopes (`w_member_social` for personal, `w_organization_social` for company)
  2. User is not an admin of the company page
  3. Company URN format is incorrect
  4. Access token is expired or invalid
- **Solution**: Run `python scripts/get_linkedin_token.py` to regenerate credentials with correct scopes

**Testing LinkedIn without API credentials**
- The system includes a mock LinkedIn tool for testing
- If `LINKEDIN_ACCESS_TOKEN` is not set, the system automatically uses the mock tool
- Mock tool simulates posting with 95% success rate for testing

**Successful personal posting example**
```
DEBUG LinkedInPostTool: Response status: 201
DEBUG LinkedInPostTool: Response text: {"id":"urn:li:share:7406722782149083136"}
✅ Successfully published to LinkedIn personal profile! View post: https://www.linkedin.com/feed/update/urn:li:share:7406722782149083136
```

**Environment variables for LinkedIn**
```
LINKEDIN_ACCESS_TOKEN='your_access_token_here'
LINKEDIN_USER_URN='urn:li:person:your_user_id'  # For personal posting
LINKEDIN_COMPANY_URN='urn:li:organization:company_id'  # For company posting (optional)
```

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Based on LangGraph hierarchical agent teams tutorial
- Uses Tavily for web search
- Built with LangChain and LangGraph
- Inspired by modern configuration-driven architectures