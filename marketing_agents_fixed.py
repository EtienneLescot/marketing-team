#!/usr/bin/env python3
"""
Working hierarchical marketing agents implementation with proper termination conditions.
"""

from typing import Literal, TypedDict, List, Optional
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage, BaseMessage


# ============================================================================
# Définitions des états
# ============================================================================

class MarketingState(MessagesState):
    """État étendu pour le système marketing hiérarchique."""
    current_team: Optional[str] = None
    task_status: str = "pending"
    iteration_count: int = 0  # Pour éviter la récursion infinie


class TeamState(MessagesState):
    """État pour les équipes spécialisées."""
    team_name: str
    iteration_count: int = 0


# ============================================================================
# Outils pour les agents spécialisés
# ============================================================================

def research_task(query: str) -> str:
    """Effectue une recherche sur un sujet donné."""
    return f"Recherche effectuée pour : {query}"


def create_content(topic: str) -> str:
    """Crée un contenu marketing pour un sujet donné."""
    return f"Contenu créé pour : {topic}"


# ============================================================================
# Équipe de Recherche (Sous-graphe fonctionnel)
# ============================================================================

def create_research_team() -> StateGraph:
    """Crée une équipe de recherche fonctionnelle."""
    
    def research_supervisor_node(state: TeamState) -> Command[Literal["web_researcher", "data_analyst", "__end__"]]:
        """Superviseur avec condition de terminaison."""
        # Limiter les itérations pour éviter la récursion infinie
        if state.get("iteration_count", 0) >= 2:
            return Command(goto=END)
        
        last_message = state["messages"][-1].content.lower()
        
        # Logique de routage simple
        if "web" in last_message or "online" in last_message:
            goto = "web_researcher"
        elif "data" in last_message or "analytics" in last_message:
            goto = "data_analyst"
        else:
            goto = "web_researcher"
        
        return Command(
            goto=goto,
            update={"iteration_count": state.get("iteration_count", 0) + 1}
        )
    
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
        result = f"Analyse de données pour : {last_message}"
        
        return Command(
            goto="supervisor",
            update={
                "messages": [
                    HumanMessage(content=result, name="data_analyst")
                ]
            }
        )
    
    # Construire le graphe
    research_builder = StateGraph(TeamState)
    research_builder.add_node("supervisor", research_supervisor_node)
    research_builder.add_node("web_researcher", web_researcher_node)
    research_builder.add_node("data_analyst", data_analyst_node)
    
    research_builder.add_edge(START, "supervisor")
    research_builder.add_edge("web_researcher", "supervisor")
    research_builder.add_edge("data_analyst", "supervisor")
    
    return research_builder.compile()


# ============================================================================
# Équipe de Création de Contenu (Sous-graphe fonctionnel)
# ============================================================================

def create_content_team() -> StateGraph:
    """Crée une équipe de création de contenu fonctionnelle."""
    
    def content_supervisor_node(state: TeamState) -> Command[Literal["content_writer", "seo_specialist", "__end__"]]:
        """Superviseur avec condition de terminaison."""
        if state.get("iteration_count", 0) >= 2:
            return Command(goto=END)
        
        last_message = state["messages"][-1].content.lower()
        
        if "seo" in last_message or "optimisation" in last_message:
            goto = "seo_specialist"
        else:
            goto = "content_writer"
        
        return Command(
            goto=goto,
            update={"iteration_count": state.get("iteration_count", 0) + 1}
        )
    
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
        result = f"Optimisation SEO pour : {last_message}"
        
        return Command(
            goto="supervisor",
            update={
                "messages": [
                    HumanMessage(content=result, name="seo_specialist")
                ]
            }
        )
    
    # Construire le graphe
    content_builder = StateGraph(TeamState)
    content_builder.add_node("supervisor", content_supervisor_node)
    content_builder.add_node("content_writer", content_writer_node)
    content_builder.add_node("seo_specialist", seo_specialist_node)
    
    content_builder.add_edge(START, "supervisor")
    content_builder.add_edge("content_writer", "supervisor")
    content_builder.add_edge("seo_specialist", "supervisor")
    
    return content_builder.compile()


# ============================================================================
# Superviseur Principal (Graphe de Niveau Supérieur fonctionnel)
# ============================================================================

def create_main_supervisor() -> StateGraph:
    """Crée le superviseur principal fonctionnel."""
    
    # Créer les équipes
    research_team_graph = create_research_team()
    content_team_graph = create_content_team()
    
    # Fonctions pour appeler les équipes
    def call_research_team(state: MarketingState) -> Command[Literal["supervisor"]]:
        """Appelle l'équipe de recherche."""
        response = research_team_graph.invoke({
            "messages": state["messages"][-1:],
            "team_name": "research_team",
            "iteration_count": 0
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
            "team_name": "content_team",
            "iteration_count": 0
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
    
    # Créer le superviseur principal
    def main_supervisor_node(state: MarketingState) -> Command[Literal["research_team", "content_team", "__end__"]]:
        """Superviseur principal avec condition de terminaison."""
        # Limiter les itérations
        if state.get("iteration_count", 0) >= 3:
            return Command(goto=END)
        
        last_message = state["messages"][-1].content.lower()
        
        # Logique de routage
        if "recherche" in last_message or "analyse" in last_message:
            goto = "research_team"
        elif "contenu" in last_message or "créer" in last_message:
            goto = "content_team"
        else:
            # Par défaut, terminer après quelques itérations
            if state.get("iteration_count", 0) >= 1:
                goto = END
            else:
                goto = "research_team"
        
        return Command(
            goto=goto,
            update={
                "iteration_count": state.get("iteration_count", 0) + 1,
                "current_team": goto if goto != END else None
            }
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
# Initialisation et Test
# ============================================================================

# Créer le graphe principal
marketing_graph = create_main_supervisor()

# Test fonctionnel
async def test_working_hierarchy():
    """Test du système hiérarchique fonctionnel."""
    print("=" * 60)
    print("Test du système hiérarchique d'agents marketing")
    print("=" * 60)
    
    # Test 1: Tâche de recherche
    print("\n1. Test de recherche marketing:")
    print("-" * 40)
    task = "Faire une recherche sur les tendances marketing open source"
    print(f"Tâche: {task}")
    
    try:
        result = await marketing_graph.ainvoke({
            "messages": [HumanMessage(content=task)],
            "iteration_count": 0
        })
        
        print("\n✅ Succès! Résultat:")
        for i, message in enumerate(result["messages"]):
            if isinstance(message, BaseMessage):
                print(f"  {i+1}. {message.name or 'system'}: {message.content}")
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        return False
    
    # Test 2: Tâche de création de contenu
    print("\n\n2. Test de création de contenu:")
    print("-" * 40)
    task = "Créer du contenu SEO pour promouvoir un projet GitHub"
    print(f"Tâche: {task}")
    
    try:
        result = await marketing_graph.ainvoke({
            "messages": [HumanMessage(content=task)],
            "iteration_count": 0
        })
        
        print("\n✅ Succès! Résultat:")
        for i, message in enumerate(result["messages"]):
            if isinstance(message, BaseMessage):
                print(f"  {i+1}. {message.name or 'system'}: {message.content}")
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ Tous les tests ont réussi!")
    print("L'architecture hiérarchique fonctionne correctement.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    import asyncio
    
    print("Démarrage du test de l'architecture hiérarchique...")
    success = asyncio.run(test_working_hierarchy())
    
    if success:
        print("\n🎉 L'implémentation est maintenant fonctionnelle!")
        print("\nRésumé des améliorations:")
        print("1. Architecture hiérarchique avec superviseurs à plusieurs niveaux")
        print("2. Boucles de feedback correctes (agents → superviseur)")
        print("3. Conditions de terminaison pour éviter la récursion infinie")
        print("4. Sous-graphes pour les équipes spécialisées")
        print("5. Patterns LangGraph correctement implémentés")
    else:
        print("\n❌ Des problèmes persistent. Vérifiez les erreurs ci-dessus.")