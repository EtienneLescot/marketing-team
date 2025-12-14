#!/usr/bin/env python3
"""
Debug script to compare authentication between test and main script.
"""

import os
import asyncio
from dotenv import load_dotenv
from agent_config import create_default_config
from langchain_openai import ChatOpenAI

# Load environment variables from .env file
load_dotenv()

async def debug_agent_config():
    """Debug agent configuration and model creation."""
    print("Debugging agent configuration...")
    
    # Load configuration
    config_manager = create_default_config()
    
    # Check research_agent
    config = config_manager.get_agent_config("research_agent")
    if not config:
        print("ERROR: No configuration found for research_agent")
        return
    
    print(f"Config for research_agent:")
    print(f"  model_name: {config.model_name}")
    print(f"  api_key_env_var: {config.api_key_env_var}")
    print(f"  base_url: {config.base_url}")
    
    # Check API key
    api_key = os.getenv(config.api_key_env_var)
    print(f"  API key from env: {'Present' if api_key else 'Missing'}")
    if api_key:
        print(f"  API key first 10 chars: {api_key[:10]}...")
    
    # Check headers
    headers = config.headers or {}
    print(f"  headers: {headers}")
    
    # Create model using the same method as in agent_config
    model = config.get_model()
    print(f"  Model created: {model}")
    
    # Check model's internal configuration
    print(f"  Model model_name: {model.model_name}")
    # print(f"  Model base_url: {model.base_url}")  # Attribute may not exist
    print(f"  Model default_headers keys: {list(model.default_headers.keys()) if model.default_headers else 'None'}")
    
    # Try to invoke
    try:
        from langchain_core.messages import HumanMessage
        response = await model.ainvoke([HumanMessage(content="Hello")])
        print(f"  SUCCESS: Response received: {response.content[:50]}...")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

async def debug_marketing_agents():
    """Debug the actual marketing_agents.py execution."""
    print("\n" + "="*60)
    print("Debugging marketing_agents.py execution...")
    
    # Import the app from marketing_agents
    from marketing_agents import app
    
    # Run a simple invocation
    try:
        result = await app.ainvoke({
            "messages": [
                {
                    "role": "user",
                    "content": "Faire une recherche sur le marketing open source"
                }
            ]
        })
        print("SUCCESS: marketing_agents.py executed")
        for msg in result["messages"]:
            if msg.type == "ai":
                print(f"  Agent response: {msg.content[:100]}...")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main debug function"""
    print("=" * 60)
    print("Authentication Debug Script")
    print("=" * 60)
    
    await debug_agent_config()
    await debug_marketing_agents()
    
    print("\n" + "=" * 60)
    print("Debug completed")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())