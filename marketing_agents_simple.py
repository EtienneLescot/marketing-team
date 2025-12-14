#!/usr/bin/env python3
"""
Simplified hierarchical marketing agents implementation.
This version uses keyword-based routing instead of LLM-based routing
to demonstrate the hierarchical architecture pattern without API dependencies.
"""

from typing import Literal, TypedDict, List, Optional
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
import os
from agent_config import agent_config


# ============================================================================
# Définitions des états
# ============================================================================

class MarketingState(MessagesState):
    """État étendu pour le système marketing hiérarchique."""
    current_team: Optional[str] = None
    task_status: str = "pending"


class TeamState(MessagesState):
    """État pour les équipes spécialisées."""
    team_name: str


# ============================================================================
# Outils pour les agents spécialisés
# ============================================================================

def research_task(query: str) -> str:
    """Effectue une recherche sur un sujet donné."""
    return f"Recherche effectuée pour : {query}"


def create_content(topic: str) -> str:
    """Crée un contenu marketing pour un sujet donné."""
    return f"Contenu créé pour : {topic}"


def publish_post(content: str, platform: str) -> str:
    """Publie un post sur une plateforme donnée."""
    return f"Post publié sur {platform} : {content}"


def analyze_performance(metrics: dict) -> str:
    """Analyse les performances des actions marketing."""
    return f"Analyse des performances : {metrics}"


# ============================================================================
# Fonctions utilitaires pour les superviseurs (version simplifiée)
# ============================================================================

def make_simple_supervisor_node(members: List[str], system_prompt: str = None):
    """
    Crée un nœud superviseur simplifié qui route basé sur des mots-clés.
    """
    def supervisor_node(state: MarketingState) -> Command[Literal[*members, "__end__"]]:
        """Un routeur basé sur des mots-clés."""
        last_message = state["messages"][-1].content.lower()
        
        # Logique de routage simple basée sur des mots-clés
        if "recherche" in last_message or "analyse" in last_message or "data" in last_message:
            goto = "research_team"
        elif "contenu" in last_message or "créer" in last_message or "écrire" in last_message:
            goto = "content_team"
        elif "social" in last_message or "linkedin" in last_message or "twitter" in last_message:
            goto = "social_media_team"
        elif "finish" in last_message or "terminé" in last_message or "done" in last_message:
            goto = END
        else:
            # Par défaut, aller à l'équipe de recherche
            goto = "research_team"
        
        return Command(
            goto=goto,
            update={"current_team": goto if goto != END else None}
        )
    
    return supervisor_node


# ============================================================================
# Équipe de Recherche (Sous-graphe simplifié)
# ============================================================================

def create_simple_research_team() -> StateGraph:
    """Crée une équipe de recherche simplifiée."""
    
    def research_supervisor_node(state: TeamState) -> Command[Literal["web_researcher", "data_analyst", "__end__"]]:
        """Superviseur simplifié pour l'équipe de recherche."""
        last_message = state["messages"][-1].content.lower()
        
        if "web" in last_message or "internet" in last_message or "online" in last_message:
            goto = "web_researcher"
        elif "data" in last_message or "analytics" in last_message or "métrique" in last_message:
            goto = "data_analyst"
        else:
            goto = "web_researcher"  # Par défaut
        
        return Command(goto=goto)
    
    def web_researcher_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Agent de recherche web."""
        last_message = state["messages"][-1].content
        result = research_task(last_message)
        
        return Command(
            goto="supervisor",
            update={
                "messages": [
                    HumanMessage(content=result, name="web_researcher")
                ]
            }
        )
    
    def data_analyst_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Agent d'analyse de données."""
        last_message = state["messages"][-1].content
        result = analyze_performance({"query": last_message})
        
        return Command(
            goto="supervisor",
            update={
                "messages": [
                    HumanMessage(content=result, name="data_analyst")
                ]
            }
        )
    
    # Construire le graphe de l'équipe de recherche
    research_builder = StateGraph(TeamState)
    research_builder.add_node("supervisor", research_supervisor_node)
    research_builder.add_node("web_researcher", web_researcher_node)
    research_builder.add_node("data_analyst", data_analyst_node)
    
    research_builder.add_edge(START, "supervisor")
    research_builder.add_edge("web_researcher", "supervisor")
    research_builder.add_edge("data_analyst", "supervisor")
    
    return research_builder.compile()


# ============================================================================
# Équipe de Création de Contenu (Sous-graphe simplifié)
# ============================================================================

def create_simple_content_team() -> StateGraph:
    """Crée une équipe de création de contenu simplifiée."""
    
    def content_supervisor_node(state: TeamState) -> Command[Literal["content_writer", "seo_specialist", "visual_designer", "__end__"]]:
        """Superviseur simplifié pour l'équipe de contenu."""
        last_message = state["messages"][-1].content.lower()
        
        if "texte" in last_message or "écrire" in last_message or "rédiger" in last_message:
            goto = "content_writer"
        elif "seo" in last_message or "optimisation" in last_message:
            goto = "seo_specialist"
        elif "visuel" in last_message or "design" in last_message or "image" in last_message:
            goto = "visual_designer"
        else:
            goto = "content_writer"  # Par défaut
        
        return Command(goto=goto)
    
    def content_writer_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Agent de rédaction de contenu."""
        last_message = state["messages"][-1].content
        result = create_content(last_message)
        
        return Command(
            goto="supervisor",
            update={
                "messages": [
                    HumanMessage(content=result, name="content_writer")
                ]
            }
        )
    
    def seo_specialist_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Agent spécialiste SEO."""
        last_message = state["messages"][-1].content
        result = f"Contenu optimisé SEO pour : {last_message}"
        
        return Command(
            goto="supervisor",
            update={
                "messages": [
                    HumanMessage(content=result, name="seo_specialist")
                ]
            }
        )
    
    def visual_designer_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Agent de design visuel."""
        last_message = state["messages"][-1].content
        result = f"Éléments visuels créés pour : {last_message}"
        
        return Command(
            goto="supervisor",
            update={
                "messages": [
                    HumanMessage(content=result, name="visual_designer")
                ]
            }
        )
    
    # Construire le graphe de l'équipe de contenu
    content_builder = StateGraph(TeamState)
    content_builder.add_node("supervisor", content_supervisor_node)
    content_builder.add_node("content_writer", content_writer_node)
    content_builder.add_node("seo_specialist", seo_specialist_node)
    content_builder.add_node("visual_designer", visual_designer_node)
    
    content_builder.add_edge(START, "supervisor")
    content_builder.add_edge("content_writer", "supervisor")
    content_builder.add_edge("seo_specialist", "supervisor")
    content_builder.add_edge("visual_designer", "supervisor")
    
    return content_builder.compile()


# ============================================================================
# Superviseur Principal (Graphe de Niveau Supérieur simplifié)
# ============================================================================

def create_simple_main_supervisor() -> StateGraph:
    """Crée le superviseur principal simplifié."""
    
    # Créer les équipes (sous-graphes)
    research_team_graph = create_simple_research_team()
    content_team_graph = create_simple_content_team()
    
    # Fonctions pour appeler les équipes
    def call_research_team(state: MarketingState) -> Command[Literal["supervisor"]]:
        """Appelle l'équipe de recherche."""
        response = research_team_graph.invoke({
            "messages": state["messages"][-1:],
            "team_name": "research_team"
        })
        
        return Command(
            goto="supervisor",
            update={
                "messages": [
                    HumanMessage(
                        content=response["messages"][-1].content,
                        name="research_team"
                    )
                ],
                "current_team": "research_team"
            }
        )
    
    def call_content_team(state: MarketingState) -> Command[Literal["supervisor"]]:
        """Appelle l'équipe de création de contenu."""
        response = content_team_graph.invoke({
            "messages": state["messages"][-1:],
            "team_name": "content_team"
        })
        
        return Command(
            goto="supervisor",
            update={
                "messages": [
                    HumanMessage(
                        content=response["messages"][-1].content,
                        name="content_team"
                    )
                ],
                "current_team": "content_team"
            }
        )
    
    # Créer le superviseur principal simplifié
    def main_supervisor_node(state: MarketingState) -> Command[Literal["research_team", "content_team", "__end__"]]:
        """Superviseur principal basé sur des mots-clés."""
        last_message = state["messages"][-1].content.lower()
        
        if "recherche" in last_message or "analyse" in last_message:
            goto = "research_team"
        elif "contenu" in last_message or "créer" in last_message:
            goto = "content_team"
        elif "finish" in last_message or "terminé" in last_message:
            goto = END
        else:
            goto = "research_team"  # Par défaut
        
        return Command(
            goto=goto,
            update={"current_team": goto if goto != END else None}
        )
    
    # Construire le graphe principal
    main_builder = StateGraph(MarketingState)
    main_builder.add_node("supervisor", main_supervisor_node)
    main_builder.add_node("research_team", call_research_team)
    main_builder.add_node("content_team", call_content_team)
    
    main_builder.add_edge(START, "supervisor")
    main_builder.add_edge("research_team", "supervisor")
    main_builder.add_edge("content_team", "supervisor")
    
    return main_builder.compile()


# ============================================================================
# Initialisation et Exécution
# ============================================================================

# Créer le graphe principal simplifié
simple_marketing_graph = create_simple_main_supervisor()


# Test de démonstration
async def demo():
    """Démonstration du système hiérarchique simplifié."""
    print("=" * 60)
    print("Démonstration de l'architecture hiérarchique simplifiée")
    print("=" * 60)
    
    # Test 1: Tâche de recherche
    print("\nTest 1: Tâche de recherche")
    print("-" * 40)
    task = "Faire une recherche sur les tendances marketing"
    print(f"Tâche: {task}")
    
    result = await simple_marketing_graph.ainvoke({
        "messages": [HumanMessage(content=task)]
    })
    
    print("\nRésultat:")
    for message in result["messages"]:
        if isinstance(message, BaseMessage):
            print(f"  {message.name or 'system'}: {message.content}")
    
    # Test 2: Tâche de création de contenu
    print("\n\nTest 2: Tâche de création de contenu")
    print("-" * 40)
    task = "Créer du contenu pour promouvoir un projet"
    print(f"Tâche: {task}")
    
    result = await simple_marketing_graph.ainvoke({
        "messages": [HumanMessage(content=task)]
    })
    
    print("\nRésultat:")
    for message in result["messages"]:
        if isinstance(message, BaseMessage):
            print(f"  {message.name or 'system'}: {message.content}")
    
    print("\n" + "=" * 60)
    print("Démonstration terminée avec succès!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())