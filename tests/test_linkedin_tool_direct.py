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
    builder = OrchestratedGraphBuilder("config/agents.yaml")
    
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
         
        # Check for pending approval (HITL)
        if "pending_approval" in result:
            print(f"\n🔔 PENDING APPROVAL DETECTED!")
            print(f"Agent: {result['pending_approval'].get('agent')}")
            print(f"Tools: {result['pending_approval'].get('tools')}")
            print(f"Content preview: {result['pending_approval'].get('content', '')[:200]}...")
        elif any("[AWAITING APPROVAL]" in str(output) for output in result.get("agent_results", {}).values()):
            # Show simulated human approval prompt
            print(f"\n🔔 HUMAN APPROVAL REQUIRED")
            print("="*80)
            print("This is what the human approval prompt would look like:")
            print("="*80)
            
            # Extract the agent and content from agent_results
            for agent, output in result.get("agent_results", {}).items():
                if "[AWAITING APPROVAL]" in output:
                    content = output.replace("[AWAITING APPROVAL] ", "")
                    print(f"Agent: {agent}")
                    print(f"Tools: linkedin_post")
                    print(f"\nContent to publish:")
                    print("-"*40)
                    print(content[:500] + ("..." if len(content) > 500 else ""))
                    print("-"*40)
                    print("\nOptions:")
                    print("1. Approve - Execute the tools")
                    print("2. Reject - Skip tool execution")
                    print("3. View full content")
                    print("\n(In a real interactive session, you would enter 1, 2, or 3)")
                    break
             
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()


async def test_web_researcher_tool():
    """Test tavily_search tool directly with web_researcher agent"""
    print("\n" + "="*80)
    print("🧪 Testing tavily_search tool with web_researcher agent...")
    
    # Create graph builder
    builder = OrchestratedGraphBuilder("config/agents.yaml")
    
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


async def test_linkedin_interactive_approval():
    """Test LinkedIn post tool with REAL interactive human approval and ENDLESS feedback loop"""
    print("\n" + "="*80)
    print("🧪 Testing LinkedIn post tool with REAL interactive approval and ENDLESS feedback loop...")
     
    # Create graph builder
    builder = OrchestratedGraphBuilder("config/agents.yaml")
    
    # Create initial state - start from scratch like a real workflow
    current_state = {
        "messages": [],
        "original_task": "Create a LinkedIn post about open source",
        "current_task": "Create a LinkedIn post about open source",
        "agent_results": {},
        "execution_plan": None
    }
    
    print(f"📝 Test task: {current_state['original_task']}")
    print(f"🤖 Testing agent: linkedin_manager")
    print(f"🔧 This test will demonstrate the complete feedback loop (infinite iterations allowed)")
    
    # Create nodes
    human_approval_node = builder._create_human_approval_node()
    worker_node = builder._create_worker_node("linkedin_manager")
    
    print("\n🚀 Starting REAL interactive approval process...")
    
    try:
        # Initial Generation
        print("🤖 Generating initial content...")
        result = await worker_node(current_state)
        current_state.update(result.update)
        
        # Feedback Loop
        iteration = 1
        while True:
            print(f"\n--- Iteration {iteration} ---")
            
            # Check if content is waiting for approval
            if "agent_results" in current_state and "linkedin_manager" in current_state["agent_results"]:
                content = current_state["agent_results"]["linkedin_manager"]
                if "[AWAITING APPROVAL]" in content:
                    print("\n📝 CONTENT GENERATED:")
                    print("="*60)
                    display_content = content.replace("[AWAITING APPROVAL] ", "")
                    print(display_content[:500] + ("..." if len(display_content) > 500 else ""))
                    print("="*60)
            
            print("\n⚠️  YOU WILL BE PROMPTED TO ENTER YOUR CHOICE (1=Approve, 2=Reject, 3=View, 4=Feedback)!")
            
            # Call human approval node - REAL INTERACTIVE INPUT
            approval_result = await human_approval_node(current_state)
            
            print(f"DEBUG: Approval Result Type: {type(approval_result)}")
            print(f"DEBUG: Approval Result: {approval_result}")
            
            # Update state with approval result
            if approval_result and hasattr(approval_result, 'update'):
                current_state.update(approval_result.update)
                
                # Check for Feedback
                if "agent_results" in approval_result.update:
                    output = approval_result.update["agent_results"].get("linkedin_manager", "")
                    
                    if "[FEEDBACK RECEIVED]" in output:
                        print("\n🔄 FEEDBACK PROVIDED: Agent will revise content")
                        print("🤖 Agent is revising content based on feedback...")
                        
                        # Call worker node for revision
                        revision_result = await worker_node(current_state)
                        current_state.update(revision_result.update)
                        iteration += 1
                        continue # Restart loop with new content
                        
                    elif "LINKEDIN POST TOOL EXECUTED" in output:
                        print("\n🎉 FINAL SUCCESS: Content approved and executed!")
                        print(f"Result: {output[:300]}...")
                        break # Exit loop
                        
                    elif "[REJECTED BY HUMAN]" in output:
                        print("\n❌ Content rejected by human.")
                        break # Exit loop
            else:
                # Should not happen ideally, but breaks loop if None
                print("\n⚠️ Loop ended (approval result was None)")
                break
                
        print("\n✅ Interactive test session completed.")
        
    except Exception as e:
        print(f"❌ Error during real approval: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests"""
    print("🔧 Testing tool integration...")

    # Test web_researcher with tavily_search
    await test_web_researcher_tool()

    # Test linkedin_manager with linkedin_post
    await test_linkedin_tool()

    # Test interactive approval
    await test_linkedin_interactive_approval()

    print("\n" + "="*80)
    print("✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())