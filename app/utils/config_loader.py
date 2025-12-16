import yaml
import os
from pathlib import Path
from typing import Dict, Any, List
from app.models.agent_types import AgentConfig, AgentConfigManager
from app.models.schemas import RouterResponse
from app.tools.tool_registry import ToolRegistry
from app.tools.tavily_search import create_tavily_search_tool
from app.tools.linkedin import create_linkedin_tool

# Initialize global tool registry
GLOBAL_TOOL_REGISTRY = ToolRegistry()
# Register known tools
tavily_tool = create_tavily_search_tool()
GLOBAL_TOOL_REGISTRY.register_tool(tavily_tool)
linkedin_tool = create_linkedin_tool()
GLOBAL_TOOL_REGISTRY.register_tool(linkedin_tool)

# Define output schemas registry
SCHEMAS = {
    "RouterResponse": RouterResponse
}

class ConfigurationLoader:
    def __init__(self, config_path: str = "config/agents.yaml"):
        # Resolve absolute path relative to project root if needed, 
        # or assume running from root.
        # Here we assume standard structure relative to where this script is imported usually, 
        # or we use an absolute path strategy if possible.
        # Let's try to be smart about finding the project root.
        
        # If config_path is relative, assume it's relative to project root.
        project_root = Path(os.getcwd())
        if "app" in project_root.parts: # if we are inside app/
             while project_root.name != "marketingTeam": # naive fallback
                 project_root = project_root.parent
        
        self.config_path = project_root / config_path
        self.prompts_dir = self.config_path.parent / "prompts"
        self.raw_config = self._load_yaml()

    def _load_yaml(self) -> Dict[str, Any]:
        """Load YAML configuration with inheritance support"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Check for inheritance
        if config and 'inherit_from' in config and config['inherit_from'] is not None:
            inherit_from = config['inherit_from']
            parent_path = Path(inherit_from)
            if not parent_path.is_absolute():
                # Resolve relative to current config file
                parent_path = self.config_path.parent / parent_path
            
            # Load parent config
            parent_loader = ConfigurationLoader(str(parent_path))
            parent_config = parent_loader.raw_config
            
            # Merge: parent config as base, child config overrides
            config = self._merge_configs(parent_config, config)
        
        return config
    
    def _merge_configs(self, parent: Dict[str, Any], child: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two configurations with child overriding parent"""
        merged = parent.copy()
        
        # Merge defaults
        if 'defaults' in child:
            merged['defaults'] = {**merged.get('defaults', {}), **child['defaults']}
        
        # Merge providers
        if 'providers' in child:
            merged['providers'] = {**merged.get('providers', {}), **child['providers']}
        
        # Merge agents (more complex - by name)
        if 'agents' in child:
            parent_agents = {a['name']: a for a in merged.get('agents', [])}
            child_agents = {a['name']: a for a in child['agents']}
            
            # Update or add agents
            for name, agent_config in child_agents.items():
                if name in parent_agents:
                    # Merge agent configurations (child overrides parent)
                    parent_agents[name] = {**parent_agents[name], **agent_config}
                else:
                    # Add new agent
                    parent_agents[name] = agent_config
            
            merged['agents'] = list(parent_agents.values())
        
        # Remove inherit_from from merged config
        if 'inherit_from' in merged:
            del merged['inherit_from']
        
        return merged

    def _load_prompt(self, filename: str) -> str:
        """Lit un fichier markdown et retourne le texte"""
        file_path = self.prompts_dir / filename
        if not file_path.exists():
             return "" # Or raise error
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def load_agents(self) -> AgentConfigManager:
        manager = AgentConfigManager()
        defaults = self.raw_config.get('defaults', {})
        providers = self.raw_config.get('providers', {})
        
        agents_list = self.raw_config.get('agents', [])
        
        for agent_def in agents_list:
            name = agent_def['name']
            prompt_file = agent_def.get('prompt_file')
            system_prompt = self._load_prompt(prompt_file) if prompt_file else ""
            
            # Determine Provider
            # Check agent specific provider, then default provider
            provider_name = agent_def.get('provider', defaults.get('provider'))
            provider_config = providers.get(provider_name, {}) if provider_name else {}

            # Helper to resolve values: Agent > Provider > Default > Hardcoded Fallback
            def resolve_val(yaml_key, fallback):
                # 1. Agent Config
                if yaml_key in agent_def:
                    return agent_def[yaml_key]
                # 2. Provider Config
                if yaml_key in provider_config:
                    return provider_config[yaml_key]
                # 3. Global Defaults
                if yaml_key in defaults:
                    return defaults[yaml_key]
                # 4. Fallback
                return fallback

            # Helper specifically for model (conceptually tied to agent, but defaults exist)
            # Model usually doesn't come from provider config directly as a fixed value, 
            # but we can allow it if someone wants a "default model for this provider".
            def resolve_model(fallback):
                if 'model' in agent_def:
                    return agent_def['model']
                if 'model' in defaults: # Global default model
                    return defaults['model']
                return fallback

            config = AgentConfig(
                name=name,
                role=agent_def.get('role', 'worker'),
                model_name=resolve_model('deepseek-chat'),
                api_key_env_var=resolve_val('api_key_env', 'DEEPSEEK_API_KEY'),
                base_url=resolve_val('base_url', 'https://api.deepseek.com'),
                headers=agent_def.get('headers', None),
                system_prompt=system_prompt,
                managed_agents=agent_def.get('managed_agents', None),
                output_schema=agent_def.get('output_schema', None),
                require_approval=agent_def.get('require_approval', False),
                tool_names=agent_def.get('tools', None)
            )
            
            # Handle Tools Mapping
            if config.tool_names:
                real_tools = []
                for t_name in config.tool_names:
                    tool = GLOBAL_TOOL_REGISTRY.get_tool(t_name)
                    if tool:
                        real_tools.append(tool)
                    else:
                        print(f"Warning: Tool '{t_name}' not found in registry.")
                config.tools = real_tools

            manager.add_agent(config)
            
        return manager

# Helper to inject managed agents list into prompts
def inject_managed_agents_into_prompts(manager: AgentConfigManager):
    for agent_config in manager.agents.values():
        if agent_config.managed_agents:
            formatted_list = "\n".join([f"- {name}" for name in agent_config.managed_agents])
            # Inject into prompt
            if "{managed_agents_list}" in agent_config.system_prompt:
                agent_config.system_prompt = agent_config.system_prompt.format(
                    managed_agents_list=formatted_list
                )
