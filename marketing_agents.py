#!/usr/bin/env python3
"""
Implémentation d'une architecture hiérarchique d'agents marketing avec LangGraph.
Ce script définit un agent superviseur principal et plusieurs équipes hiérarchiques
pour promouvoir un dépôt GitHub open source.
"""

from typing import Literal, TypedDict, List, Optional
from langchain_openai import ChatOpenAI
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


def generate_strategy(topic: str) -> str:
    """Génère une stratégie marketing."""
    return f"Stratégie générée pour : {topic}"


def community_engagement(action: str) -> str:
    """Gère l'engagement communautaire."""
    return f"Engagement communautaire : {action}"


# ============================================================================
# Fonctions utilitaires pour les superviseurs
# ============================================================================

def make_supervisor_node(llm: ChatOpenAI, members: List[str], system_prompt: str = None):
    """
    Crée un nœud superviseur basé sur LLM pour router vers les membres.
    Pattern provenant du tutoriel LangGraph hierarchical agent teams.
    """
    options = ["FINISH"] + members
    
    if not system_prompt:
        system_prompt = (
            f"Vous êtes un superviseur chargé de gérer une conversation entre les "
            f"travailleurs suivants : {', '.join(members)}. "
            "Étant donné la demande de l'utilisateur, répondez avec le travailleur à agir ensuite. "
            "Chaque travailleur effectuera une tâche et répondra avec ses résultats et son statut. "
            "Lorsque vous avez terminé, répondez avec FINISH."
        )
    
    class Router(TypedDict):
        """Worker to route to next. If no workers needed, route to FINISH."""
        next: Literal[*options]
    
    def supervisor_node(state: MarketingState) -> Command[Literal[*members, "__end__"]]:
        """Un routeur basé sur LLM."""
        messages = [
            SystemMessage(content=system_prompt),
        ] + state["messages"]
        
        # Utiliser le LLM pour prendre une décision structurée
        response = llm.with_structured_output(Router).invoke(messages)
        goto = response["next"]
        
        if goto == "FINISH":
            goto = END
        
        return Command(
            goto=goto,
            update={"current_team": goto if goto != END else None}
        )
    
    return supervisor_node


# ============================================================================
# Équipe de Recherche (Sous-graphe)
# ============================================================================

def create_research_team() -> StateGraph:
    """Crée une équipe de recherche avec superviseur et agents spécialisés."""
    
    # Obtenir la configuration
    config = agent_config.get_agent_config("research_team_supervisor")
    llm = config.get_model() if config else ChatOpenAI()
    
    # Créer le superviseur de l'équipe de recherche
    research_supervisor = make_supervisor_node(
        llm=llm,
        members=["web_researcher", "data_analyst"],
        system_prompt=(
            "Vous êtes le superviseur de l'équipe de recherche marketing. "
            "Vous gérez deux spécialistes : "
            "1. web_researcher : effectue des recherches web sur les tendances et concurrents "
            "2. data_analyst : analyse les données et métriques "
            "Assignez les tâches appropriées à chaque spécialiste."
        )
    )
    
    # Définir les agents spécialisés de recherche
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
    research_builder.add_node("supervisor", research_supervisor)
    research_builder.add_node("web_researcher", web_researcher_node)
    research_builder.add_node("data_analyst", data_analyst_node)
    
    research_builder.add_edge(START, "supervisor")
    research_builder.add_edge("web_researcher", "supervisor")
    research_builder.add_edge("data_analyst", "supervisor")
    
    return research_builder.compile()


# ============================================================================
# Équipe de Création de Contenu (Sous-graphe)
# ============================================================================

def create_content_team() -> StateGraph:
    """Crée une équipe de création de contenu avec superviseur et agents spécialisés."""
    
    # Obtenir la configuration
    config = agent_config.get_agent_config("content_team_supervisor")
    llm = config.get_model() if config else ChatOpenAI()
    
    # Créer le superviseur de l'équipe de contenu
    content_supervisor = make_supervisor_node(
        llm=llm,
        members=["content_writer", "seo_specialist", "visual_designer"],
        system_prompt=(
            "Vous êtes le superviseur de l'équipe de création de contenu marketing. "
            "Vous gérez trois spécialistes : "
            "1. content_writer : rédige du contenu textuel "
            "2. seo_specialist : optimise le contenu pour le SEO "
            "3. visual_designer : crée des éléments visuels "
            "Assignez les tâches appropriées à chaque spécialiste."
        )
    )
    
    # Définir les agents spécialisés de contenu
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
    content_builder.add_node("supervisor", content_supervisor)
    content_builder.add_node("content_writer", content_writer_node)
    content_builder.add_node("seo_specialist", seo_specialist_node)
    content_builder.add_node("visual_designer", visual_designer_node)
    
    content_builder.add_edge(START, "supervisor")
    content_builder.add_edge("content_writer", "supervisor")
    content_builder.add_edge("seo_specialist", "supervisor")
    content_builder.add_edge("visual_designer", "supervisor")
    
    return content_builder.compile()


# ============================================================================
# Équipe des Médias Sociaux (Sous-graphe)
# ============================================================================

def create_social_media_team() -> StateGraph:
    """Crée une équipe de médias sociaux avec superviseur et agents spécialisés."""
    
    # Obtenir la configuration
    config = agent_config.get_agent_config("social_media_team_supervisor")
    llm = config.get_model() if config else ChatOpenAI()
    
    # Créer le superviseur de l'équipe des médias sociaux
    social_supervisor = make_supervisor_node(
        llm=llm,
        members=["linkedin_manager", "twitter_manager", "analytics_tracker"],
        system_prompt=(
            "Vous êtes le superviseur de l'équipe des médias sociaux. "
            "Vous gérez trois spécialistes : "
            "1. linkedin_manager : gère les publications LinkedIn "
            "2. twitter_manager : gère les publications Twitter "
            "3. analytics_tracker : suit les performances des publications "
            "Assignez les tâches appropriées à chaque spécialiste."
        )
    )
    
    # Définir les agents spécialisés des médias sociaux
    def linkedin_manager_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Agent de gestion LinkedIn."""
        last_message = state["messages"][-1].content
        result = publish_post(last_message, "LinkedIn")
        
        return Command(
            goto="supervisor",
            update={
                "messages": [
                    HumanMessage(content=result, name="linkedin_manager")
                ]
            }
        )
    
    def twitter_manager_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Agent de gestion Twitter."""
        last_message = state["messages"][-1].content
        result = publish_post(last_message, "Twitter")
        
        return Command(
            goto="supervisor",
            update={
                "messages": [
                    HumanMessage(content=result, name="twitter_manager")
                ]
            }
        )
    
    def analytics_tracker_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Agent de suivi analytique."""
        last_message = state["messages"][-1].content
        result = analyze_performance({"platform": "social_media", "content": last_message})
        
        return Command(
            goto="supervisor",
            update={
                "messages": [
                    HumanMessage(content=result, name="analytics_tracker")
                ]
            }
        )
    
    # Construire le graphe de l'équipe des médias sociaux
    social_builder = StateGraph(TeamState)
    social_builder.add_node("supervisor", social_supervisor)
    social_builder.add_node("linkedin_manager", linkedin_manager_node)
    social_builder.add_node("twitter_manager", twitter_manager_node)
    social_builder.add_node("analytics_tracker", analytics_tracker_node)
    
    social_builder.add_edge(START, "supervisor")
    social_builder.add_edge("linkedin_manager", "supervisor")
    social_builder.add_edge("twitter_manager", "supervisor")
    social_builder.add_edge("analytics_tracker", "supervisor")
    
    return social_builder.compile()


# ============================================================================
# Superviseur Principal (Graphe de Niveau Supérieur)
# ============================================================================

def create_main_supervisor() -> StateGraph:
    """Crée le superviseur principal qui orchestre les équipes."""
    
    # Obtenir la configuration du superviseur principal
    config = agent_config.get_agent_config("main_supervisor")
    llm = config.get_model() if config else ChatOpenAI()
    
    # Créer les équipes (sous-graphes)
    research_team_graph = create_research_team()
    content_team_graph = create_content_team()
    social_media_team_graph = create_social_media_team()
    
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
    
    def call_social_media_team(state: MarketingState) -> Command[Literal["supervisor"]]:
        """Appelle l'équipe des médias sociaux."""
        response = social_media_team_graph.invoke({
            "messages": state["messages"][-1:],
            "team_name": "social_media_team"
        })
        
        return Command(
            goto="supervisor",
            update={
                "messages": [
                    HumanMessage(
                        content=response["messages"][-1].content,
                        name="social_media_team"
                    )
                ],
                "current_team": "social_media_team"
            }
        )
    
    # Créer le superviseur principal
    main_supervisor = make_supervisor_node(
        llm=llm,
        members=["research_team", "content_team", "social_media_team"],
        system_prompt=(
            "Vous êtes le superviseur principal du système marketing. "
            "Vous gérez trois équipes spécialisées : "
            "1. research_team : effectue des recherches et analyses "
            "2. content_team : crée du contenu marketing "
            "3. social_media_team : gère les publications sur les médias sociaux "
            "Analysez la demande de l'utilisateur et assignez-la à l'équipe appropriée. "
            "Vous pouvez également orchestrer des workflows complexes impliquant plusieurs équipes."
        )
    )
    
    # Construire le graphe principal
    main_builder = StateGraph(MarketingState)
    main_builder.add_node("supervisor", main_supervisor)
    main_builder.add_node("research_team", call_research_team)
    main_builder.add_node("content_team", call_content_team)
    main_builder.add_node("social_media_team", call_social_media_team)
    
    main_builder.add_edge(START, "supervisor")
    main_builder.add_edge("research_team", "supervisor")
    main_builder.add_edge("content_team", "supervisor")
    main_builder.add_edge("social_media_team", "supervisor")
    
    return main_builder.compile()


# ============================================================================
# Initialisation et Exécution
# ============================================================================

# Créer le graphe principal
marketing_graph = create_main_supervisor()


# Exécution interactive
async def interactive_main():
    """Exécute le workflow en mode interactif."""
    print("=" * 60)
    print("Système d'agents marketing hiérarchique - Mode interactif")
    print("=" * 60)
    print("Commandes disponibles:")
    print("  - 'quit' ou 'exit' : quitter le programme")
    print("  - 'help' : afficher cette aide")
    print("  - 'teams' : lister les équipes disponibles")
    print("  - 'config' : afficher la configuration actuelle")
    print("\nExemples de tâches marketing:")
    print("  - 'Faire une recherche sur les tendances marketing open source'")
    print("  - 'Créer du contenu pour promouvoir un dépôt GitHub'")
    print("  - 'Publier sur les médias sociaux un projet open source'")
    print("  - 'Analyser les performances de notre campagne marketing'")
    print("=" * 60)
    
            user_input = input("\n> ").strip()
            
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Au revoir!")
                break
            elif user_input.lower() in ["help", "h"]:
                print("Commandes disponibles: quit, exit, help, teams, config")
                print("Tâches marketing: utilisez des descriptions détaillées pour une meilleure orchestration")
            elif user_input.lower() in ["teams", "t"]:
                print("Équipes disponibles:")
                print("  - research_team : recherche et analyse marketing")
                print("    • web_researcher : recherches web")
                print("    • data_analyst : analyse de données")
                print("  - content_team : création de contenu")
                print("    • content_writer : rédaction")
                print("    • seo_specialist : optimisation SEO")
                print("    • visual_designer : design visuel")
                print("  - social_media_team : médias sociaux")
                print("    • linkedin_manager : publications LinkedIn")
                print("    • twitter_manager : publications Twitter")
                print("    • analytics_tracker : suivi des performances")
            elif user_input.lower() in ["config", "c"]:
                print("Configuration actuelle:")
                for agent_name in ["main_supervisor", "research_team_supervisor",
                                  "content_team_supervisor", "social_media_team_supervisor"]:
                    config = agent_config.get_agent_config(agent_name)
                    if config:
                        print(f"  - {agent_name}: {config.model_name}")
            elif user_input:
                print(f"Traitement de la tâche: '{user_input}'")
                print("-" * 40)
                
                # Exécuter le workflow
                result = await marketing_graph.ainvoke({
                    "messages": [
                        HumanMessage(content=user_input)
                    ]
                })

                # Afficher les résultats
                print("\nRésultat:")
                for message in result["messages"]:
                    if isinstance(message, BaseMessage):
                        print(f"  {message.name or 'system'}: {message.content}")
                print("-" * 40)
            else:
                print("Veuillez entrer une commande ou une tâche marketing.")
                
        except KeyboardInterrupt:
            print("\n\nInterruption détectée. Au revoir!")
            break
        except Exception as e:
            print(f"Erreur: {e}")
            print("Veuillez réessayer.")


# Exemple d'exécution
async def main():
    """Exécute le workflow avec une tâche de marketing."""
    print("Exécution du workflow marketing hiérarchique...")
    
    # Exemple de tâche complexe
    task = "I need you to promote my open source GitHub repository. As a marketing expert, you will orchestrate the creation of a marketing plan for my repository. You may work with other agents to complete this task. here is the repo url:https://github.com/stimm-ai/stimm"
    
    print(f"Tâche: {task}")
    print("-" * 40)
    
    result = await marketing_graph.ainvoke({
        "messages": [HumanMessage(content=task)]
    })
    
    print("Résultat de l'exécution :")
    for message in result["messages"]:
        if isinstance(message, BaseMessage):
            print(f"{message.name or 'system'}: {message.content}")
    print("-" * 40)


if __name__ == "__main__":
    import asyncio
    import sys
    
    # Vérifier les arguments de ligne de commande
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive_main())
    elif len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python marketing_agents.py [OPTION]")
        print("Options:")
        print("  --interactive    Run in interactive mode")
        print("  --help           Show this help message")
        print("  (no arguments)   Run a single example task")
    else:
        # Exécuter la tâche d'exemple
        asyncio.run(main())
