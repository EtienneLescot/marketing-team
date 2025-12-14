#!/usr/bin/env python3
"""
Implémentation d'une architecture d'agents marketing avec Langraph.
Ce script définit un agent superviseur et plusieurs agents spécialisés
pour promouvoir un dépôt GitHub open source.
"""

from typing import Literal, TypedDict
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Command
import os
from agent_config import agent_config


# Définir les outils pour les agents spécialisés
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


# Définir l'agent superviseur
def marketing_supervisor(state: MessagesState) -> Command:
    """
    L'agent superviseur décompose la tâche de haut niveau
    et assigne les sous-tâches aux agents spécialisés.
    """
    last_message = state["messages"][-1].content
    
    if "recherche" in last_message.lower():
        return Command(
            update={"task": "research"},
            goto="research_agent"
        )
    elif "création" in last_message.lower():
        return Command(
            update={"task": "content"},
            goto="content_agent"
        )
    elif "publication" in last_message.lower():
        return Command(
            update={"task": "publish"},
            goto="social_media_agent"
        )
    elif "analyse" in last_message.lower():
        return Command(
            update={"task": "analyze"},
            goto="analytics_agent"
        )
    else:
        return Command(
            update={"task": "unknown"},
            goto=END
        )


# Définir les agents spécialisés
def create_specialized_agent(name: str, tools: list, prompt: str):
    """Crée un agent spécialisé avec des outils et un prompt spécifiques."""
    # Get agent configuration
    config = agent_config.get_agent_config(name)
    if not config:
        raise ValueError(f"Configuration not found for agent: {name}")

    # Get the configured model
    model = config.get_model()

    # Create a simple agent function that performs the actual task
    def agent_function(state: MessagesState):
        last_message = state["messages"][-1].content

        # Perform the actual task using the tool
        tool_result = tools[0](last_message)

        return {"messages": [{"role": "ai", "content": f"{name}: {tool_result}"}]}

    return agent_function


# Créer les agents spécialisés
research_agent = create_specialized_agent(
    name="research_agent",
    tools=[research_task],
    prompt="Tu es un assistant de recherche. Effectue des recherches détaillées sur les sujets demandés."
)

content_agent = create_specialized_agent(
    name="content_agent",
    tools=[create_content],
    prompt="Tu es un assistant de création de contenu. Crée des posts et articles marketing."
)

social_media_agent = create_specialized_agent(
    name="social_media_agent",
    tools=[publish_post],
    prompt="Tu es un assistant de gestion des réseaux sociaux. Publie et gère les posts."
)

analytics_agent = create_specialized_agent(
    name="analytics_agent",
    tools=[analyze_performance],
    prompt="Tu es un assistant d'analyse de performance. Analyse les métriques marketing."
)


# Construire le graphe d'agents
workflow = StateGraph(MessagesState)

# Ajouter les agents au graphe
workflow.add_node("supervisor", marketing_supervisor)
workflow.add_node("research_agent", research_agent)
workflow.add_node("content_agent", content_agent)
workflow.add_node("social_media_agent", social_media_agent)
workflow.add_node("analytics_agent", analytics_agent)

# Définir les transitions
workflow.add_edge(START, "supervisor")
workflow.add_edge("supervisor", "research_agent")
workflow.add_edge("supervisor", "content_agent")
workflow.add_edge("supervisor", "social_media_agent")
workflow.add_edge("supervisor", "analytics_agent")
workflow.add_edge("research_agent", "supervisor")
workflow.add_edge("content_agent", "supervisor")
workflow.add_edge("social_media_agent", "supervisor")
workflow.add_edge("analytics_agent", "supervisor")

# Compiler le graphe
app = workflow.compile()


# Exemple d'exécution
async def main():
    """Exécute le workflow avec une tâche de marketing."""
    result = await app.ainvoke({
        "messages": [
            {
                "role": "user",
                "content": "Promouvoir un dépôt GitHub open source pour augmenter sa visibilité, ses étoiles, ses contributeurs et son adoption."
            }
        ]
    })

    print("Résultat de l'exécution :")
    for message in result["messages"]:
        print(f"{message['role']}: {message['content']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())