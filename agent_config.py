#!/usr/bin/env python3

"""
Centralized configuration for marketing agents with hierarchical team structure.

This file defines the configuration for each agent including models, API keys, and settings.
It now loads configuration from config/agents.yaml and config/prompts/.
"""

import os
from dotenv import load_dotenv

# Import types and loader
from app.models.agent_types import AgentConfig, AgentConfigManager
from app.utils.config_loader import ConfigurationLoader, inject_managed_agents_into_prompts

# Load environment variables from .env file
load_dotenv()

# Function to create/load configuration
def create_default_config() -> AgentConfigManager:
    """Create default configuration for hierarchical marketing agents by loading from YAML"""
    loader = ConfigurationLoader()
    config_manager = loader.load_agents()
    
    # Inject dynamic content into prompts (like managed_agents lists)
    inject_managed_agents_into_prompts(config_manager)
    
    return config_manager

# Global configuration instance
agent_config = create_default_config()