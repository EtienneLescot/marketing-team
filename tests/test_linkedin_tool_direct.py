#!/usr/bin/env python3
"""
Direct test of LinkedIn post tool with linkedin_manager agent.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.orchestrated_graph_builder import OrchestratedGraphBuilder
from app.monitoring.streaming_monitor import StreamingMonitor


async def test_linkedin_tool():
    """Test LinkedIn post tool directly with linkedin_manager agent"""
    print("🧪 Testing LinkedIn post tool with linkedin_manager agent...")
    
    # Create graph builder
    builder = OrchestratedGraphBuilder("config/agents_with_dependencies.yaml")
    
    # Build single agent graph for linkedin_manager
    graph = builder._build_single_agent_graph("linkedin_manager")
    
    # Prepare test state
    test_state = {
        "messages": [],
        "original_task": "Create a LinkedIn post about promoting open source repository https://github.com/stimm-ai/stimm",
        "current_task": "Create a LinkedIn post about promoting open source repository https://github.com/stimm-ai/stimm",
        "agent_results": {},
        "execution_plan": None
    }
    
    print(f"\n📝 Test task: {test_state['original_task']}")
    print(f"🤖 Testing agent: linkedin_manager")
    
    # Execute the graph
    try:
        result = await graph.ainvoke(test_state)
        
        print(f"\n✅ Execution completed!")
        print(f"\n📊 Final state keys: {list(result.keys())}")
        
        if "agent_results" in result:
            print(f"\n📋 Agent results:")
            for agent, output in result["agent_results"].items():
                print(f"\n--- {agent} ---")
                print(output[:500] + "..." if len(output) > 500 else output)
        
        if "final_result" in result:
            print(f"\n🎯 Final result: {result['final_result'][:500]}...")
            
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()


async def test_web_researcher_tool():
    """Test tavily_search tool directly with web_researcher agent"""
    print("\n" + "="*80)
    print("🧪 Testing tavily_search tool with web_researcher agent...")
    
    # Create graph builder
    builder = OrchestratedGraphBuilder("config/agents_with_dependencies.yaml")
    
    # Build single agent graph for web_researcher
    graph = builder._build_single_agent_graph("web_researcher")
    
    # Prepare test state
    test_state = {
        "messages": [],
        "original_task": "Research how to promote open source repositories on LinkedIn",
        "current_task": "Research how to promote open source repositories on LinkedIn",
        "agent_results": {},
        "execution_plan": None
    }
    
    print(f"\n📝 Test task: {test_state['original_task']}")
    print(f"🤖 Testing agent: web_researcher")
    
    # Execute the graph
    try:
        result = await graph.ainvoke(test_state)
        
        print(f"\n✅ Execution completed!")
        
        if "agent_results" in result:
            print(f"\n📋 Agent results:")
            for agent, output in result["agent_results"].items():
                print(f"\n--- {agent} ---")
                # Check if search results are in the output
                if "Search query:" in output:
                    print("✅ Tavily search tool WAS called!")
                    # Show first few lines
                    lines = output.split('\n')
                    for line in lines[:10]:
                        print(f"  {line}")
                    if len(lines) > 10:
                        print(f"  ... and {len(lines)-10} more lines")
                else:
                    print("❌ Tavily search tool was NOT called")
                    print(output[:500] + "..." if len(output) > 500 else output)
                    
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests"""
    print("🔧 Testing tool integration...")
    
    # Test web_researcher with tavily_search
    await test_web_researcher_tool()
    
    # Test linkedin_manager with linkedin_post
    await test_linkedin_tool()
    
    print("\n" + "="*80)
    print("✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())