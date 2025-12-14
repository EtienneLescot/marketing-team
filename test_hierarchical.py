#!/usr/bin/env python3
"""
Test script for the hierarchical marketing agents architecture.
"""

import asyncio
from marketing_agents import marketing_graph
from langchain_core.messages import HumanMessage

async def test_basic():
    """Test basic functionality of the hierarchical architecture."""
    print("=" * 60)
    print("Testing hierarchical marketing agents architecture")
    print("=" * 60)
    
    # Test 1: Simple research task
    print("\nTest 1: Research task")
    print("-" * 40)
    task = "Faire une recherche sur les tendances du marketing open source"
    print(f"Task: {task}")
    
    try:
        result = await marketing_graph.ainvoke({
            'messages': [HumanMessage(content=task)]
        })
        
        print("\nResult received successfully!")
        print(f"Number of messages: {len(result['messages'])}")
        
        for i, message in enumerate(result['messages']):
            if hasattr(message, 'name') and message.name:
                print(f"  Message {i+1} from {message.name}: {message.content[:80]}...")
            else:
                print(f"  Message {i+1}: {message.content[:80]}...")
        
        print("\n✓ Test 1 passed!")
        
    except Exception as e:
        print(f"\n✗ Test 1 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Content creation task
    print("\n\nTest 2: Content creation task")
    print("-" * 40)
    task = "Créer du contenu pour promouvoir un dépôt GitHub sur l'IA"
    print(f"Task: {task}")
    
    try:
        result = await marketing_graph.ainvoke({
            'messages': [HumanMessage(content=task)]
        })
        
        print("\nResult received successfully!")
        print(f"Number of messages: {len(result['messages'])}")
        print("\n✓ Test 2 passed!")
        
    except Exception as e:
        print(f"\n✗ Test 2 failed: {e}")
        return False
    
    # Test 3: Social media task
    print("\n\nTest 3: Social media task")
    print("-" * 40)
    task = "Publier sur LinkedIn un post sur un projet open source"
    print(f"Task: {task}")
    
    try:
        result = await marketing_graph.ainvoke({
            'messages': [HumanMessage(content=task)]
        })
        
        print("\nResult received successfully!")
        print(f"Number of messages: {len(result['messages'])}")
        print("\n✓ Test 3 passed!")
        
    except Exception as e:
        print(f"\n✗ Test 3 failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
    return True

async def test_complex_workflow():
    """Test a complex marketing workflow."""
    print("\n\n" + "=" * 60)
    print("Testing complex marketing workflow")
    print("=" * 60)
    
    task = "I need you to promote my open source GitHub repository. As a marketing expert, you will orchestrate the creation of a marketing plan for my repository. You may work with other agents to complete this task. here is the repo url:https://github.com/stimm-ai/stimm"
    
    print(f"Task: {task[:100]}...")
    
    try:
        result = await marketing_graph.ainvoke({
            'messages': [HumanMessage(content=task)]
        })
        
        print("\nComplex workflow executed successfully!")
        print(f"Total messages in workflow: {len(result['messages'])}")
        
        # Show team interactions
        team_interactions = {}
        for message in result['messages']:
            if hasattr(message, 'name') and message.name:
                team = message.name.split('_')[0] if '_' in message.name else message.name
                team_interactions[team] = team_interactions.get(team, 0) + 1
        
        print("\nTeam interactions:")
        for team, count in team_interactions.items():
            print(f"  {team}: {count} message(s)")
        
        print("\n✓ Complex workflow test passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Complex workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting hierarchical marketing agents tests...")
    
    # Run basic tests
    basic_result = asyncio.run(test_basic())
    
    # Run complex workflow test
    complex_result = asyncio.run(test_complex_workflow())
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Basic tests: {'PASSED' if basic_result else 'FAILED'}")
    print(f"Complex workflow: {'PASSED' if complex_result else 'FAILED'}")
    
    if basic_result and complex_result:
        print("\n✅ All tests passed! Hierarchical architecture is working correctly.")
    else:
        print("\n❌ Some tests failed. Check the errors above.")