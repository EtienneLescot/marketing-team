#!/usr/bin/env python3
"""
Centralized configuration for marketing agents with hierarchical team structure.
This file defines the configuration for each agent including models, API keys, and settings.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

@dataclass
class AgentConfig:
    """Configuration for a single agent"""
    name: str
    model_name: str = "meta-llama/llama-3.3-70b-instruct:free"  # Default model
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

# Default configuration for hierarchical marketing agents
def create_default_config() -> AgentConfigManager:
    """Create default configuration for hierarchical marketing agents"""
    config_manager = AgentConfigManager()

    # ============================================================================
    # Superviseur Principal (Niveau le plus élevé)
    # ============================================================================
    
    main_supervisor_config = AgentConfig(
        name="main_supervisor",
        model_name="meta-llama/llama-3.3-70b-instruct:free",  # Powerful model for orchestration
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://marketing-orchestrator.com",
            "X-Title": "Marketing Main Supervisor"
        },
        system_prompt=(
            "You are the main supervisor of the hierarchical marketing system. "
            "You manage specialized teams: "
            "1. research_team: performs marketing research and analysis "
            "2. content_team: creates marketing content "
            "3. social_media_team: manages social media publications "
            "Analyze the user's request and assign it to the appropriate team. "
            "You can also orchestrate complex workflows involving multiple teams. "
            "\n\nIMPORTANT: You must output your routing decision in valid JSON format with the following structure: "
            "{\"next_node\": \"team_name\", \"reasoning\": \"explanation\", \"confidence\": 0.95, \"should_terminate\": false} "
            "Where next_node must be one of: research_team, content_team, social_media_team, or FINISH. "
            "confidence is a number between 0 and 1 indicating your confidence in the decision. "
            "should_terminate is true only if the task is complete and no further processing is needed."
        )
    )
    config_manager.add_agent(main_supervisor_config)

    # ============================================================================
    # Équipe de Recherche (Superviseur et Agents)
    # ============================================================================
    
    research_team_supervisor_config = AgentConfig(
        name="research_team_supervisor",
        model_name="amazon/nova-2-lite-v1:free",  # Model for research
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://research-team.com",
            "X-Title": "Research Team Supervisor"
        },
        system_prompt=(
            "You are the supervisor of the marketing research team. "
            "You manage two specialists: "
            "1. web_researcher: performs web research on trends and competitors "
            "2. data_analyst: analyzes data and metrics "
            "Assign appropriate tasks to each specialist. "
            "\n\nIMPORTANT: You must output your routing decision in valid JSON format with the following structure: "
            "{\"next_node\": \"agent_name\", \"reasoning\": \"explanation\", \"confidence\": 0.95, \"should_terminate\": false} "
            "Where next_node must be one of: web_researcher, data_analyst, or FINISH. "
            "confidence is a number between 0 and 1 indicating your confidence in the decision. "
            "should_terminate is true only if the task is complete and no further processing is needed."
        )
    )
    config_manager.add_agent(research_team_supervisor_config)

    # Agents de l'équipe de recherche
    web_researcher_config = AgentConfig(
        name="web_researcher",
        model_name="amazon/nova-2-lite-v1:free",
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://web-researcher.com",
            "X-Title": "Web Researcher Agent"
        },
        system_prompt="Vous êtes un chercheur web spécialisé en marketing. Effectuez des recherches approfondies sur les tendances, concurrents et opportunités."
    )
    config_manager.add_agent(web_researcher_config)

    data_analyst_config = AgentConfig(
        name="data_analyst",
        model_name="amazon/nova-2-lite-v1:free",
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://data-analyst.com",
            "X-Title": "Data Analyst Agent"
        },
        system_prompt="Vous êtes un analyste de données marketing. Analysez les métriques, performances et données pour fournir des insights."
    )
    config_manager.add_agent(data_analyst_config)

    # ============================================================================
    # Équipe de Création de Contenu (Superviseur et Agents)
    # ============================================================================
    
    content_team_supervisor_config = AgentConfig(
        name="content_team_supervisor",
        model_name="amazon/nova-2-lite-v1:free",  # Model for content creation
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://content-team.com",
            "X-Title": "Content Team Supervisor"
        },
        system_prompt=(
            "You are the supervisor of the marketing content creation team. "
            "You manage three specialists: "
            "1. content_writer: writes textual content "
            "2. seo_specialist: optimizes content for SEO "
            "3. visual_designer: creates visual elements "
            "Assign appropriate tasks to each specialist. "
            "\n\nIMPORTANT: You must output your routing decision in valid JSON format with the following structure: "
            "{\"next_node\": \"agent_name\", \"reasoning\": \"explanation\", \"confidence\": 0.95, \"should_terminate\": false} "
            "Where next_node must be one of: content_writer, seo_specialist, visual_designer, or FINISH. "
            "confidence is a number between 0 and 1 indicating your confidence in the decision. "
            "should_terminate is true only if the task is complete and no further processing is needed."
        )
    )
    config_manager.add_agent(content_team_supervisor_config)

    # Agents de l'équipe de contenu
    content_writer_config = AgentConfig(
        name="content_writer",
        model_name="amazon/nova-2-lite-v1:free",
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://content-writer.com",
            "X-Title": "Content Writer Agent"
        },
        system_prompt="Vous êtes un rédacteur de contenu marketing. Créez des posts, articles et communications engageants pour promouvoir des projets."
    )
    config_manager.add_agent(content_writer_config)

    seo_specialist_config = AgentConfig(
        name="seo_specialist",
        model_name="amazon/nova-2-lite-v1:free",
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://seo-specialist.com",
            "X-Title": "SEO Specialist Agent"
        },
        system_prompt="Vous êtes un spécialiste SEO. Optimisez le contenu pour les moteurs de recherche et améliorez la visibilité."
    )
    config_manager.add_agent(seo_specialist_config)

    visual_designer_config = AgentConfig(
        name="visual_designer",
        model_name="amazon/nova-2-lite-v1:free",
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://visual-designer.com",
            "X-Title": "Visual Designer Agent"
        },
        system_prompt="Vous êtes un designer visuel. Créez des éléments visuels attrayants pour le marketing (graphiques, images, présentations)."
    )
    config_manager.add_agent(visual_designer_config)

    # ============================================================================
    # Équipe des Médias Sociaux (Superviseur et Agents)
    # ============================================================================
    
    social_media_team_supervisor_config = AgentConfig(
        name="social_media_team_supervisor",
        model_name="amazon/nova-2-lite-v1:free",  # Model for social media
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://social-media-team.com",
            "X-Title": "Social Media Team Supervisor"
        },
        system_prompt=(
            "You are the supervisor of the social media team. "
            "You manage three specialists: "
            "1. linkedin_manager: manages LinkedIn publications "
            "2. twitter_manager: manages Twitter publications "
            "3. analytics_tracker: tracks publication performance "
            "Assign appropriate tasks to each specialist. "
            "\n\nIMPORTANT: You must output your routing decision in valid JSON format with the following structure: "
            "{\"next_node\": \"agent_name\", \"reasoning\": \"explanation\", \"confidence\": 0.95, \"should_terminate\": false} "
            "Where next_node must be one of: linkedin_manager, twitter_manager, analytics_tracker, or FINISH. "
            "confidence is a number between 0 and 1 indicating your confidence in the decision. "
            "should_terminate is true only if the task is complete and no further processing is needed."
        )
    )
    config_manager.add_agent(social_media_team_supervisor_config)

    # Agents de l'équipe des médias sociaux
    linkedin_manager_config = AgentConfig(
        name="linkedin_manager",
        model_name="amazon/nova-2-lite-v1:free",
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://linkedin-manager.com",
            "X-Title": "LinkedIn Manager Agent"
        },
        system_prompt="Vous êtes un gestionnaire LinkedIn. Créez et gérez des publications professionnelles sur LinkedIn pour promouvoir des projets."
    )
    config_manager.add_agent(linkedin_manager_config)

    twitter_manager_config = AgentConfig(
        name="twitter_manager",
        model_name="amazon/nova-2-lite-v1:free",
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://twitter-manager.com",
            "X-Title": "Twitter Manager Agent"
        },
        system_prompt="Vous êtes un gestionnaire Twitter. Créez et gérez des publications sur Twitter pour engager la communauté."
    )
    config_manager.add_agent(twitter_manager_config)

    analytics_tracker_config = AgentConfig(
        name="analytics_tracker",
        model_name="amazon/nova-2-lite-v1:free",
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://analytics-tracker.com",
            "X-Title": "Analytics Tracker Agent"
        },
        system_prompt="Vous êtes un tracker analytique. Suivez et analysez les performances des publications sur les médias sociaux."
    )
    config_manager.add_agent(analytics_tracker_config)

    # ============================================================================
    # Agents de Support (Optionnels)
    # ============================================================================
    
    strategy_agent_config = AgentConfig(
        name="strategy_agent",
        model_name="meta-llama/llama-3.3-70b-instruct:free",
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://strategy-agent.com",
            "X-Title": "Strategy Agent"
        },
        system_prompt="Vous êtes un agent de stratégie marketing. Développez des stratégies complètes pour la promotion de projets."
    )
    config_manager.add_agent(strategy_agent_config)

    community_manager_config = AgentConfig(
        name="community_manager",
        model_name="amazon/nova-2-lite-v1:free",
        api_key_env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        headers={
            "HTTP-Referer": "https://community-manager.com",
            "X-Title": "Community Manager Agent"
        },
        system_prompt="Vous êtes un gestionnaire de communauté. Engagez et interagissez avec la communauté pour promouvoir l'adoption de projets."
    )
    config_manager.add_agent(community_manager_config)

    return config_manager

# Global configuration instance
agent_config = create_default_config()