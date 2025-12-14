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

    # Check if this is a response from an agent (starts with agent name)
    if last_message.startswith("research_agent:") or \
       last_message.startswith("content_agent:") or \
       last_message.startswith("social_media_agent:") or \
       last_message.startswith("analytics_agent:"):
        # This is a response from an agent, terminate the workflow
        return Command(
            update={"task": "completed"},
            goto=END
        )
    elif "recherche" in last_message.lower():
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

    # Create a simple agent function that performs the actual task using the AI model
    async def agent_function(state: MessagesState):
        last_message = state["messages"][-1].content

        # Use the configured AI model to generate a real response
        try:
            # Get the model response based on the agent's system prompt and task
            if name == "research_agent":
                system_prompt = "You are a research assistant. Conduct detailed research on the given topic about GitHub repository promotion."
                user_prompt = f"Research this topic: {last_message}"
            elif name == "content_agent":
                system_prompt = "You are a marketing content creator. Create engaging content to promote GitHub repositories."
                user_prompt = f"Create marketing content about: {last_message}"
            elif name == "social_media_agent":
                system_prompt = "You are a social media manager. Create posts to promote GitHub repositories on LinkedIn."
                user_prompt = f"Create a LinkedIn post about: {last_message}"
            elif name == "analytics_agent":
                system_prompt = "You are a performance analyst. Analyze marketing metrics for GitHub repository promotion."
                user_prompt = f"Analyze performance for: {last_message}"
            else:
                system_prompt = config.system_prompt
                user_prompt = last_message

            # Use the configured model to generate a real AI response
            from langchain_core.messages import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            # Get the AI response using async method
            response = await model.ainvoke(messages)
            ai_response = response.content
            tool_result = f"{name}: {ai_response}"

        except Exception as e:
            # Fallback to mock if AI fails
            print(f"AI Model failed for {name}: {e}")
            if name == "social_media_agent":
                tool_result = tools[0](last_message, "LinkedIn")
            elif name == "analytics_agent":
                tool_result = tools[0]({"metrics": "sample_data"})
            else:
                tool_result = tools[0](last_message)

        return {"messages": [{"role": "ai", "content": tool_result}]}

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
# Remove the edges from agents back to supervisor - supervisor will handle termination
workflow.add_edge("research_agent", END)
workflow.add_edge("content_agent", END)
workflow.add_edge("social_media_agent", END)
workflow.add_edge("analytics_agent", END)

# Compiler le graphe
app = workflow.compile()


# Interactive execution
async def interactive_main():
    """Exécute le workflow en mode interactif."""
    print("=" * 60)
    print("Système d'agents marketing - Mode interactif")
    print("=" * 60)
    print("Commandes disponibles:")
    print("  - 'quit' ou 'exit' : quitter le programme")
    print("  - 'help' : afficher cette aide")
    print("  - 'agents' : lister les agents disponibles")
    print("  - 'config' : afficher la configuration actuelle")
    print("\nExemples de tâches marketing:")
    print("  - 'Faire une recherche sur les tendances marketing open source'")
    print("  - 'Créer du contenu pour promouvoir un dépôt GitHub'")
    print("  - 'Publier un post LinkedIn sur un projet open source'")
    print("  - 'Analyser les performances de notre campagne marketing'")
    print("=" * 60)

    while True:
        try:
            user_input = input("\n> ").strip()
            
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Au revoir!")
                break
            elif user_input.lower() in ["help", "h"]:
                print("Commandes disponibles: quit, exit, help, agents, config")
                print("Tâches marketing: utilisez des mots-clés comme 'recherche', 'création', 'publication', 'analyse'")
            elif user_input.lower() in ["agents", "a"]:
                print("Agents disponibles:")
                print("  - research_agent : recherche marketing")
                print("  - content_agent : création de contenu")
                print("  - social_media_agent : publication sur réseaux sociaux")
                print("  - analytics_agent : analyse de performance")
                print("  - supervisor : superviseur qui route les tâches")
            elif user_input.lower() in ["config", "c"]:
                print("Configuration actuelle:")
                for agent_name in ["research_agent", "content_agent", "social_media_agent", "analytics_agent", "supervisor"]:
                    config = agent_config.get_agent_config(agent_name)
                    if config:
                        print(f"  - {agent_name}: {config.model_name}")
            elif user_input:
                print(f"Traitement de la tâche: '{user_input}'")
                print("-" * 40)
                
                # Execute the workflow
                result = await app.ainvoke({
                    "messages": [
                        {
                            "role": "user",
                            "content": user_input
                        }
                    ]
                })

                # Display results
                print("\nRésultat:")
                for message in result["messages"]:
                    if message.type == "ai":
                        print(f"  {message.content}")
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
    print("Exécution du workflow marketing...")
    result = await app.ainvoke({
        "messages": [
            {
                "role": "user",
                "content": "I need you to promote my open source GitHub repository. As a marketing expert, you will orchestrate the creation of a marketing plan for my repository. You may work with other agents to complete this task. here is the repo url:https://github.com/stimm-ai/stimm"
            }
        ]
    })

    print("Résultat de l'exécution :")
    for message in result["messages"]:
        print(f"{message.type}: {message.content}")


if __name__ == "__main__":
    import asyncio
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive_main())
    elif len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python marketing_agents.py [OPTION]")
        print("Options:")
        print("  --interactive    Run in interactive mode")
        print("  --help           Show this help message")
        print("  (no arguments)   Run a single example task")
    else:
        # Run the example task
        asyncio.run(main())