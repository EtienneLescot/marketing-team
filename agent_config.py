#!/usr/bin/env python3
"""
Centralized configuration for marketing agents.
This file defines the configuration for each agent including models, API keys, and settings.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI

@dataclass
class AgentConfig:
    """Configuration for a single agent"""
    name: str
    model_name: str = "gpt-4o"  # Default model
    api_key_env_var: str = "OPENROUTER_API_KEY"  # Default API key environment variable
    base_url: str = "https://openrouter.ai/api/v1"  # Default base URL
    headers: Optional[Dict[str, str]] = None
    tools: Optional[List] = None
    system_prompt: str = ""

    def get_model(self):
        """Create and return the configured LLM model"""
        headers = self.headers or {
            "HTTP-Referer": "https://your-app-name.com",
            "X-Title": "Your App Name"
        }

        # Add Authorization header if API key is available
        api_key = os.getenv(self.api_key_env_var)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        return ChatOpenAI(
            model=self.model_name,
            api_key=api_key,
            base_url=self.base_url,
            default_headers=headers
        )

class AgentConfigManager:
    """Manages configuration for all agents"""

    def __init__(self):
        self.agents = {}

    def add_agent(self, config: AgentConfig):
        """Add an agent configuration"""
        self.agents[config.name] = config

    def get_agent_config(self, name: str) -> AgentConfig:
        """Get configuration for a specific agent"""
        return self.agents.get(name)

    def get_all_agents(self) -> Dict[str, AgentConfig]:
        """Get all agent configurations"""
        return self.agents

# Default configuration for marketing agents
def create_default_config() -> AgentConfigManager:
    """Create default configuration for marketing agents"""
    config_manager = AgentConfigManager()

    # Research Agent - Using OpenRouter with specific model
    research_config = AgentConfig(
        name="research_agent",
        model_name="openai/gpt-oss-120b:free",  # Different model for research
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://marketing-research-app.com",
            "X-Title": "Marketing Research Agent"
        },
        system_prompt="Tu es un assistant de recherche. Effectue des recherches détaillées sur les sujets demandés."
    )

    # Content Agent - Using a different provider (example: OpenAI)
    content_config = AgentConfig(
        name="content_agent",
        model_name="openai/gpt-oss-120b:free",  # Different model for content creation
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://content-creator-app.com",
            "X-Title": "Content Creation Agent"
        },
        system_prompt="Tu es un assistant de création de contenu. Crée des posts et articles marketing."
    )

    # Social Media Agent - Using OpenRouter with another model
    social_media_config = AgentConfig(
        name="social_media_agent",
        model_name="openai/gpt-oss-120b:free",  # Different model for social media
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://social-media-manager.com",
            "X-Title": "Social Media Agent"
        },
        system_prompt="Tu es un assistant de gestion des réseaux sociaux. Publie et gère les posts."
    )

    # Analytics Agent - Using a local/fast model for analytics
    analytics_config = AgentConfig(
        name="analytics_agent",
        model_name="openai/gpt-oss-120b:free",  # Faster model for analytics
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://analytics-dashboard.com",
            "X-Title": "Analytics Agent"
        },
        system_prompt="Tu es un assistant d'analyse de performance. Analyse les métriques marketing."
    )

    config_manager.add_agent(research_config)
    config_manager.add_agent(content_config)
    config_manager.add_agent(social_media_config)
    config_manager.add_agent(analytics_config)

    # Supervisor Agent - The "chef" that orchestrates everything
    supervisor_config = AgentConfig(
        name="supervisor",
        model_name="openai/gpt-oss-120b:free",  # Faster model for analytics
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://marketing-orchestrator.com",
            "X-Title": "Marketing Supervisor Agent"
        },
        system_prompt="Tu es le superviseur principal. Analyse les demandes marketing de haut niveau, décompose-les en sous-tâches et assigne-les aux agents spécialisés appropriés."
    )

    config_manager.add_agent(supervisor_config)

    return config_manager

# Global configuration instance
agent_config = create_default_config()