#!/usr/bin/env python3
"""
Test script to verify OpenRouter authentication and model configuration.
"""

import os
import asyncio
from dotenv import load_dotenv
from agent_config import create_default_config

# Load environment variables from .env file
load_dotenv()

async def test_openrouter():
    """Test OpenRouter connection with the configured agents."""
    print("Testing OpenRouter authentication...")
    
    # Load configuration
    config_manager = create_default_config()
    
    # Test each agent's model
    agents = ["research_agent", "content_agent", "social_media_agent", "analytics_agent", "supervisor"]
    
    for agent_name in agents:
        print(f"\n--- Testing {agent_name} ---")
        config = config_manager.get_agent_config(agent_name)
        if not config:
            print(f"  ERROR: No configuration found for {agent_name}")
            continue
            
        print(f"  Model: {config.model_name}")
        print(f"  API Key Env Var: {config.api_key_env_var}")
        
        # Check if API key is set
        api_key = os.getenv(config.api_key_env_var)
        if not api_key:
            print(f"  WARNING: API key not found in environment variable {config.api_key_env_var}")
            continue
            
        print(f"  API Key present: {api_key[:10]}...")
        
        # Try to create the model
        try:
            model = config.get_model()
            print(f"  Model created successfully")
            
            # Try a simple async call
            try:
                response = await model.ainvoke("Hello, are you working?")
                print(f"  Response received: {response.content[:50]}...")
                print(f"  SUCCESS: {agent_name} is working!")
            except Exception as e:
                print(f"  ERROR during model invocation: {type(e).__name__}: {e}")
                # Print more details if it's an authentication error
                if "401" in str(e):
                    print(f"  AUTHENTICATION FAILED: Check API key and model permissions")
                elif "404" in str(e):
                    print(f"  MODEL NOT FOUND: The model '{config.model_name}' may not be available")
        except Exception as e:
            print(f"  ERROR creating model: {type(e).__name__}: {e}")

async def main():
    """Main test function"""
    print("=" * 60)
    print("OpenRouter Authentication Test")
    print("=" * 60)
    
    # Check environment
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY environment variable is not set")
        print("Please add it to your .env file")
        return
    
    print(f"OPENROUTER_API_KEY found: {api_key[:10]}...")
    
    # Run tests
    await test_openrouter()
    
    print("\n" + "=" * 60)
    print("Test completed")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())