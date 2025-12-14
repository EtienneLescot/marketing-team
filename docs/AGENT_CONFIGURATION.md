# Agent Configuration Guide

This guide explains how to configure different agents with their own models, API keys, and settings.

## Configuration System Overview

The `agent_config.py` file provides a centralized configuration system that allows you to:

1. **Set different models for each agent** - Each agent can use a different LLM model
2. **Use different API providers** - Mix OpenRouter, OpenAI, and other providers
3. **Configure custom headers** - Set referer URLs and titles for each agent
4. **Manage API keys securely** - Use environment variables for sensitive data

## Configuration Structure

Each agent is configured using the `AgentConfig` class with these parameters:

```python
AgentConfig(
    name="agent_name",              # Unique identifier for the agent
    model_name="model-name",        # LLM model to use (default: "gpt-4o")
    api_key_env_var="API_KEY_VAR",  # Environment variable for API key (default: "OPENROUTER_API_KEY")
    base_url="https://...",         # API base URL (default: OpenRouter)
    headers={...},                  # Custom HTTP headers
    system_prompt="..."             # System prompt for the agent
)
```

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