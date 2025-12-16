# Agent Configuration Guide

This guide explains how to configure agents using the new dynamic, YAML-based configuration system.

## Configuration System Overview

The system now uses `config/agents.yaml` as the single source of truth for agent configuration. The `DynamicGraphBuilder` class dynamically creates agent graphs based on this configuration, allowing you to:

1. **Define agent hierarchies** - Create supervisor-worker relationships with `managed_agents`
2. **Configure inheritance** - Inherit configurations from parent YAML files
3. **Define tools per agent** - Specify which tools each agent can use
4. **Set approval requirements** - Mark agents that require human approval
5. **Use different providers per agent** - Mix DeepSeek, OpenAI, and other providers
6. **Configure custom headers** - Set referer URLs and titles for each agent

## Configuration Structure

Configuration is defined in YAML files with this structure:

```yaml
# Global defaults applied to all agents unless overridden
defaults:
  provider: "deepseek"
  model: "deepseek-chat"

# Provider definitions
providers:
  deepseek:
    base_url: "https://api.deepseek.com"
    api_key_env: "DEEPSEEK_API_KEY"
  openai:
    base_url: null  # Uses default OpenAI URL
    api_key_env: "OPENAI_API_KEY"

# Agent configurations
agents:
  - name: "main_supervisor"
    role: "supervisor"
    prompt_file: "supervisors/main.md"
    output_schema: "RouterResponse"
    headers:
      HTTP-Referer: "https://marketing-orchestrator.com"
      X-Title: "Marketing Main Supervisor"
    managed_agents:
      - "research_team_supervisor"
      - "content_team_supervisor"
      - "social_media_team_supervisor"

  - name: "web_researcher"
    role: "worker"
    prompt_file: "workers/web_researcher.md"
    headers:
      HTTP-Referer: "https://web-researcher.com"
      X-Title: "Web Researcher Agent"
    tools:
      - "tavily_search"
    require_approval: false

# Tool configurations
tools:
  tavily_search:
    type: "tavily"
    api_key_env: "TAVILY_API_KEY"
    max_results: 5
    search_depth: "advanced"
```

## Agent Properties

Each agent configuration supports these properties:

| Property | Required | Description | Example |
|----------|----------|-------------|---------|
| `name` | Yes | Unique identifier for the agent | `"web_researcher"` |
| `role` | Yes | `"supervisor"` or `"worker"` | `"worker"` |
| `prompt_file` | Yes | Path to markdown file with agent instructions | `"workers/web_researcher.md"` |
| `output_schema` | For supervisors | Schema for routing decisions | `"RouterResponse"` |
| `headers` | No | Custom HTTP headers for API calls | `{"HTTP-Referer": "..."}` |
| `managed_agents` | For supervisors | List of agent names this supervisor manages | `["agent1", "agent2"]` |
| `tools` | No | List of tool names this agent can use | `["tavily_search", "linkedin_post"]` |
| `require_approval` | No | Whether agent requires human approval | `true` |
| `provider` | No | Override default provider | `"openai"` |
| `model` | No | Override default model | `"gpt-4o"` |

## Configuration Inheritance

Configurations can inherit from other YAML files:

```yaml
# research_team.yaml
description: "Research-focused team"
inherit_from: "agents.yaml"  # Inherit base configuration

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
      - "strategy_agent"
```

Inheritance rules:
1. **Defaults merge** - Child defaults override parent defaults
2. **Agents merge** - Agents with same name are overridden, others are added
3. **Tools merge** - Tool configurations merge with child taking precedence
4. **Providers merge** - Provider definitions merge

## Dynamic Graph Building

The system automatically builds agent graphs based on configuration:

### Graph Types

1. **Full Hierarchy** - Starting from `main_supervisor`, builds complete agent tree
2. **Team Supervisor** - Starting from any supervisor, builds that team's hierarchy
3. **Single Agent** - Starting from any worker, builds just that agent

### Entry Point Targeting

You can start workflows from any agent:

```bash
# Full workflow from main supervisor (default)
uv run python main.py "Research competitors and create social media posts"

# Content team only
uv run python main.py --config config/agents.yaml --entry-point content_team_supervisor "Write blog post about AI"

# Single agent
uv run python main.py --entry-point web_researcher "Find latest marketing trends"
```

## Example Configurations

### Research Team Configuration (`config/research_team.yaml`)

```yaml
description: "Research-focused team for competitive analysis"
inherit_from: "agents.yaml"

agents:
  - name: "research_supervisor"
    role: "supervisor"
    prompt_file: "supervisors/research.md"
    managed_agents:
      - "web_researcher"
      - "data_analyst"
      - "strategy_agent"

  - name: "web_researcher"
    role: "worker"
    tools:
      - "tavily_search"
      - "mock_search"
```

### Content Team Configuration (`config/content_team.yaml`)

```yaml
description: "Content creation team"
inherit_from: "agents.yaml"

defaults:
  provider: "openai"
  model: "gpt-4o-mini"

agents:
  - name: "content_supervisor"
    role: "supervisor"
    managed_agents:
      - "content_writer"
      - "seo_specialist"
      - "visual_designer"

  - name: "content_writer"
    role: "worker"
    require_approval: true
```

## Tool Configuration

Tools are configured separately and can be referenced by agents:

```yaml
tools:
  tavily_search:
    type: "tavily"
    api_key_env: "TAVILY_API_KEY"
    max_results: 5
    search_depth: "advanced"

  linkedin_post:
    type: "linkedin"
    api_key_env: "LINKEDIN_API_KEY"
    post_visibility: "public"

  mock_search:
    type: "mock"
    mock_data_file: "mock_search_results.json"
```

## CLI Interface

The main script provides a rich CLI interface:

```bash
# Show help
uv run python main.py --help

# List available configurations
uv run python main.py --list-configs

# List entry points for a configuration
uv run python main.py --list-entry-points --config research_team

# Validate configuration
uv run python main.py --validate --config config/agents.yaml

# Interactive mode
uv run python main.py --interactive

# Run with custom config and entry point
uv run python main.py --config research_team --entry-point web_researcher "Research AI trends"
```

## Validation and Error Checking

The system includes automatic validation:

1. **Cycle Detection** - Prevents infinite loops in agent hierarchies
2. **Missing Agent Detection** - Warns about referenced agents that don't exist
3. **Tool Validation** - Checks that referenced tools are configured
4. **Prompt File Validation** - Verifies prompt files exist

Run validation manually:
```bash
uv run python main.py --validate --config your_config.yaml
```

## Best Practices

1. **Start simple** - Use `config/simple_team.yaml` as a template
2. **Use inheritance** - Create base configurations and extend them
3. **Validate early** - Run validation before deploying new configurations
4. **Document your configs** - Add descriptions to each configuration file
5. **Test entry points** - Verify each agent can be used as an entry point
6. **Use meaningful names** - Agent names should reflect their function

## Migration from Old System

If you're migrating from the old `agent_config.py` system:

1. **Convert agent definitions** to YAML format
2. **Move prompts** to markdown files in `config/prompts/`
3. **Update tool references** to use the new tool configuration system
4. **Test with validation** to ensure everything works

## Troubleshooting

**Issue**: "Agent not found in configuration"
- **Solution**: Check agent name spelling and ensure it's defined in the YAML file

**Issue**: "Cycle detected in agent hierarchy"
- **Solution**: Review `managed_agents` references to ensure no circular dependencies

**Issue**: "Tool not configured"
- **Solution**: Add tool configuration to the `tools` section of your YAML

**Issue**: "Prompt file not found"
- **Solution**: Verify the `prompt_file` path exists relative to `config/prompts/`

**Issue**: "Configuration inheritance not working"
- **Solution**: Check that `inherit_from` path is correct and files are readable

## Example Configuration

Here's how the current agents are configured:

### Research Agent
- **Model**: `mistralai/mistral-7b-instruct` (specialized for research)
- **Provider**: OpenRouter
- **API Key**: `OPENROUTER_API_KEY`
- **Use Case**: Detailed research tasks

### Content Agent
- **Model**: `gpt-4` (high-quality content generation)
- **Provider**: OpenAI (different provider example)
- **API Key**: `OPENAI_API_KEY`
- **Use Case**: Marketing content creation

### Social Media Agent
- **Model**: `anthropic/claude-3-sonnet` (great for social media tone)
- **Provider**: OpenRouter
- **API Key**: `OPENROUTER_API_KEY`
- **Use Case**: Social media management

### Analytics Agent
- **Model**: `gpt-3.5-turbo` (fast and cost-effective)
- **Provider**: OpenRouter
- **API Key**: `OPENROUTER_API_KEY`
- **Use Case**: Performance analysis

### Supervisor Agent (Orchestrator)
- **Model**: `gpt-4o` (powerful for decision making)
- **Provider**: OpenRouter
- **API Key**: `OPENROUTER_API_KEY`
- **Use Case**: High-level task decomposition and agent orchestration
- **Role**: The "chef" agent that receives macro prompts and assigns tasks to specialized agents

## How to Add a New Agent

1. **Add the agent to the configuration** in `agent_config.py`:

```python
# Add to the create_default_config() function
new_agent_config = AgentConfig(
    name="new_agent",
    model_name="your-preferred-model",
    api_key_env_var="YOUR_API_KEY_VAR",
    base_url="https://your-provider.com/api/v1",
    system_prompt="Description of what this agent does..."
)
config_manager.add_agent(new_agent_config)
```

2. **Set the environment variable** in your `.env` file:

```env
YOUR_API_KEY_VAR=your_actual_api_key_here
```

3. **Use the agent** in your workflow:

```python
from agent_config import agent_config

# Get the configured agent
new_agent = create_specialized_agent(
    name="new_agent",
    tools=[your_tools_here],
    prompt="Agent instructions..."
)
```

## Environment Variables

Create a `.env` file in your project root with your API keys:

```env
# OpenRouter API Key
OPENROUTER_API_KEY=your_openrouter_key

# OpenAI API Key (if using OpenAI models)
OPENAI_API_KEY=your_openai_key

# Other provider keys as needed
OTHER_PROVIDER_KEY=your_other_key
```

## Architecture Overview

The agent system follows a hierarchical architecture:

1. **Supervisor Agent (Orchestrator)** - The "chef" agent that:
   - Receives high-level marketing requests (macro prompts)
   - Analyzes the request and determines what needs to be done
   - Decomposes the task into sub-tasks
   - Assigns sub-tasks to specialized agents
   - Coordinates the workflow between agents

2. **Specialized Agents** - Each focused on a specific domain:
   - Research Agent: Handles research tasks
   - Content Agent: Creates marketing content
   - Social Media Agent: Manages social media operations
   - Analytics Agent: Analyzes performance metrics

3. **Workflow**:
   ```
   User → Supervisor → Specialized Agents → Supervisor → User
                    (Task Assignment)       (Result Aggregation)
   ```

## Supervisor Agent Configuration

The supervisor agent is configured like any other agent but has a special role:

```python
supervisor_config = AgentConfig(
    name="supervisor",
    model_name="gpt-4o",  # Use a powerful model for complex decision making
    system_prompt="Tu es le superviseur principal. Analyse les demandes marketing de haut niveau...",
    # ... other configuration parameters
)
```

The supervisor uses keyword-based routing to assign tasks:

- "recherche" → Research Agent
- "création" → Content Agent
- "publication" → Social Media Agent
- "analyse" → Analytics Agent

## Best Practices

1. **Match models to tasks** - Use specialized models for specific tasks
2. **Consider cost vs performance** - Faster models for simple tasks, powerful models for complex ones
3. **Use meaningful referer URLs** - Helps with API provider analytics
4. **Keep API keys secure** - Never hardcode keys, always use environment variables
5. **Document your configuration** - Explain why you chose each model/provider

## Troubleshooting

**Issue**: Authentication errors
- **Solution**: Check that the environment variable name matches exactly and the API key is valid

**Issue**: Model not found
- **Solution**: Verify the model name is correct for the provider you're using

**Issue**: Rate limiting
- **Solution**: Consider using different providers for different agents to distribute load