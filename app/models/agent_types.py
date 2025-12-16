from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import os
from langchain_openai import ChatOpenAI

@dataclass
class AgentConfig:
    """Configuration for a single agent"""
    name: str
    role: str = "worker"  # "supervisor" or "worker"
    model_name: str = "deepseek-chat"
    api_key_env_var: str = "DEEPSEEK_API_KEY"
    base_url: str = "https://api.deepseek.com"
    headers: Optional[Dict[str, str]] = None
    tools: Optional[List[Any]] = None  # List of actual tool objects or callables
    tool_names: Optional[List[str]] = None # List of tool names from config
    system_prompt: str = ""
    managed_agents: Optional[List[str]] = None
    depends_on: Optional[List[str]] = None  # List of agent names this agent depends on
    output_schema: Optional[str] = None
    require_approval: bool = False

    def get_model(self):
        """Create and return the configured LLM model"""
        headers = self.headers or {}
        
        # Add Authorization header if API key is available
        api_key = os.getenv(self.api_key_env_var)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        llm = ChatOpenAI(
            model=self.model_name,
            api_key=api_key,
            base_url=self.base_url,
            default_headers=headers
        )
        return llm

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
