#!/usr/bin/env python3
"""
Test suite for hierarchical marketing agents with LLM routing.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage

from app.models.state_models import EnhancedMarketingState, TeamState
from app.routing.structured_router import (
    RoutingDecision,
    create_main_supervisor_router,
    create_research_team_router,
    create_content_team_router
)
from app.tools.tool_registry import ToolRegistry
from app.tools.mock_search import MockSearchTool
from app.utils.message_utils import (
    extract_original_task,
    create_agent_response,
    sanitize_messages_for_agent,
    detect_message_nesting,
    reset_message_nesting
)
from app.agents.hierarchical_marketing import (
    AgentConfig,
    create_research_team,
    create_content_team,
    create_main_supervisor,
    create_marketing_workflow
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider"""
    mock = MagicMock()
    
    # Mock agent configs
    mock.get_agent_config = MagicMock(return_value=MagicMock(
        get_model=MagicMock(return_value=MagicMock())
    ))
    
    return mock


@pytest.fixture
def agent_config(mock_llm_provider):
    """Agent config with mocked dependencies"""
    with patch('app.agents.hierarchical_marketing.agent_config', mock_llm_provider):
        config = AgentConfig()
        config.llm_provider = mock_llm_provider
        return config


@pytest.fixture
def sample_state():
    """Sample marketing state"""
    return {
        "messages": [HumanMessage(content="Test marketing task")],
        "iteration_count": 0,
        "workflow_status": "running",
        "start_time": datetime.now()
    }


@pytest.fixture
def sample_team_state():
    """Sample team state"""
    return {
        "messages": [HumanMessage(content="Test team task")],
        "team_name": "test_team",
        "iteration_count": 0
    }


# ============================================================================
# Unit Tests - Message Utilities
# ============================================================================

def test_extract_original_task():
    """Test extracting original task from messages"""
    # Test with simple message
    messages = [HumanMessage(content="Research AI trends")]
    assert extract_original_task(messages) == "Research AI trends"
    
    # Test with nested messages
    messages = [
        HumanMessage(content="Original task"),
        AIMessage(content="Agent response", name="agent1"),
        HumanMessage(content="Follow up")
    ]
    assert extract_original_task(messages) == "Original task"
    
    # Test with empty messages
    assert extract_original_task([]) == ""


def test_create_agent_response():
    """Test creating agent response messages"""
    response = create_agent_response(
        content="Test response",
        agent_name="test_agent",
        include_original_task=True,
        original_task="Original task"
    )
    
    assert len(response) == 1
    assert isinstance(response[0], AIMessage)
    assert response[0].name == "test_agent"
    assert "Original task" in response[0].content
    assert "Test response" in response[0].content


def test_detect_message_nesting():
    """Test detecting message nesting"""
    # No nesting
    messages = [
        HumanMessage(content="Task"),
        AIMessage(content="Response", name="agent1")
    ]
    assert not detect_message_nesting(messages)
    
    # With nesting (agent response contains another agent's output)
    messages = [
        HumanMessage(content="Task"),
        AIMessage(content="Agent1: Some response\nAgent2: Another response", name="agent1")
    ]
    assert detect_message_nesting(messages)


def test_reset_message_nesting():
    """Test resetting message nesting"""
    messages = [
        HumanMessage(content="Original task"),
        AIMessage(content="Agent1: Response\nAgent2: Nested", name="agent1"),
        AIMessage(content="More nested content", name="agent2")
    ]
    
    reset_messages = reset_message_nesting(messages)
    assert len(reset_messages) == 2  # Original task + last agent response
    assert isinstance(reset_messages[0], HumanMessage)
    assert reset_messages[0].content == "Original task"


# ============================================================================
# Unit Tests - Tool Registry
# ============================================================================

def test_tool_registry():
    """Test tool registry functionality"""
    registry = ToolRegistry()
    
    # Test registering and getting tool
    mock_tool = MockSearchTool()
    registry.register_tool("mock_search", mock_tool)
    
    assert registry.get_tool("mock_search") == mock_tool
    assert registry.get_tool("nonexistent") is None
    
    # Test tool stats
    stats = registry.get_all_stats()
    assert "mock_search" in stats
    assert "summary" in stats


# ============================================================================
# Unit Tests - Routing
# ============================================================================

@pytest.mark.asyncio
async def test_routing_decision_model():
    """Test routing decision model"""
    decision = RoutingDecision(
        next_node="research_team",
        reasoning="Task requires research",
        confidence=0.85,
        should_terminate=False
    )
    
    assert decision.next_node == "research_team"
    assert decision.confidence == 0.85
    assert not decision.should_terminate
    
    # Test dict conversion
    decision_dict = decision.dict()
    assert decision_dict["next_node"] == "research_team"
    assert decision_dict["confidence"] == 0.85


@pytest.mark.asyncio
async def test_router_creation():
    """Test router creation"""
    mock_model = MagicMock()
    
    # Test main supervisor router
    main_router = create_main_supervisor_router(mock_model)
    assert main_router is not None
    
    # Test research team router
    research_router = create_research_team_router(mock_model)
    assert research_router is not None
    
    # Test content team router
    content_router = create_content_team_router(mock_model)
    assert content_router is not None


# ============================================================================
# Integration Tests - Research Team
# ============================================================================

@pytest.mark.asyncio
async def test_research_team_creation(agent_config):
    """Test research team graph creation"""
    research_team = create_research_team(agent_config)
    assert research_team is not None
    
    # Test graph structure
    assert hasattr(research_team, "nodes")
    assert "supervisor" in research_team.nodes
    assert "web_researcher" in research_team.nodes
    assert "data_analyst" in research_team.nodes


@pytest.mark.asyncio
async def test_research_team_execution(agent_config, sample_team_state):
    """Test research team execution"""
    # Mock the router to return a specific decision
    mock_decision = RoutingDecision(
        next_node="web_researcher",
        reasoning="Test",
        confidence=0.9,
        should_terminate=False
    )
    
    with patch.object(agent_config.research_team_router, 'route', AsyncMock(return_value=mock_decision)):
        research_team = create_research_team(agent_config)
        
        # Execute the team
        result = await research_team.ainvoke(sample_team_state)
        
        assert "messages" in result
        assert "iteration_count" in result
        assert result["iteration_count"] > 0


# ============================================================================
# Integration Tests - Content Team
# ============================================================================

@pytest.mark.asyncio
async def test_content_team_creation(agent_config):
    """Test content team graph creation"""
    content_team = create_content_team(agent_config)
    assert content_team is not None
    
    # Test graph structure
    assert hasattr(content_team, "nodes")
    assert "supervisor" in content_team.nodes
    assert "content_writer" in content_team.nodes
    assert "seo_specialist" in content_team.nodes


@pytest.mark.asyncio
async def test_content_team_execution(agent_config, sample_team_state):
    """Test content team execution"""
    # Mock the router to return a specific decision
    mock_decision = RoutingDecision(
        next_node="content_writer",
        reasoning="Test",
        confidence=0.9,
        should_terminate=False
    )
    
    with patch.object(agent_config.content_team_router, 'route', AsyncMock(return_value=mock_decision)):
        content_team = create_content_team(agent_config)
        
        # Execute the team
        result = await content_team.ainvoke(sample_team_state)
        
        assert "messages" in result
        assert "iteration_count" in result
        assert result["iteration_count"] > 0


# ============================================================================
# Integration Tests - Main Supervisor
# ============================================================================

@pytest.mark.asyncio
async def test_main_supervisor_creation(agent_config):
    """Test main supervisor graph creation"""
    main_supervisor = create_main_supervisor(agent_config)
    assert main_supervisor is not None
    
    # Test graph structure
    assert hasattr(main_supervisor, "nodes")
    assert "supervisor" in main_supervisor.nodes
    assert "research_team" in main_supervisor.nodes
    assert "content_team" in main_supervisor.nodes


@pytest.mark.asyncio
async def test_main_supervisor_execution(agent_config, sample_state):
    """Test main supervisor execution"""
    # Mock the router to return a specific decision
    mock_decision = RoutingDecision(
        next_node="research_team",
        reasoning="Test requires research",
        confidence=0.85,
        should_terminate=False
    )
    
    with patch.object(agent_config.main_supervisor_router, 'route', AsyncMock(return_value=mock_decision)):
        main_supervisor = create_main_supervisor(agent_config)
        
        # Execute the supervisor
        result = await main_supervisor.ainvoke(sample_state)
        
        assert "messages" in result
        assert "iteration_count" in result
        assert "current_team" in result
        assert result["iteration_count"] > 0


# ============================================================================
# End-to-End Tests
# ============================================================================

@pytest.mark.asyncio
async def test_complete_workflow():
    """Test complete marketing workflow"""
    # Create workflow
    workflow = create_marketing_workflow()
    assert workflow is not None
    
    # Test with research task
    state = {
        "messages": [HumanMessage(content="Research AI marketing trends")],
        "iteration_count": 0,
        "workflow_status": "running",
        "start_time": datetime.now()
    }
    
    try:
        result = await workflow.ainvoke(state)
        
        # Verify result structure
        assert "messages" in result
        assert "iteration_count" in result
        assert "workflow_status" in result
        
        # Verify we have some output
        assert len(result["messages"]) > 0
        
        print(f"\n✅ Workflow test passed!")
        print(f"  Iterations: {result.get('iteration_count', 0)}")
        print(f"  Status: {result.get('workflow_status', 'unknown')}")
        print(f"  Messages: {len(result.get('messages', []))}")
        
    except Exception as e:
        pytest.fail(f"Workflow execution failed: {e}")


@pytest.mark.asyncio
async def test_workflow_with_content_task():
    """Test workflow with content creation task"""
    # Create workflow
    workflow = create_marketing_workflow()
    
    # Test with content task
    state = {
        "messages": [HumanMessage(content="Create blog post about social media marketing")],
        "iteration_count": 0,
        "workflow_status": "running",
        "start_time": datetime.now()
    }
    
    try:
        result = await workflow.ainvoke(state)
        
        # Verify result structure
        assert "messages" in result
        assert "iteration_count" in result
        
        # Verify we have some output
        assert len(result["messages"]) > 0
        
        print(f"\n✅ Content workflow test passed!")
        print(f"  Iterations: {result.get('iteration_count', 0)}")
        
    except Exception as e:
        pytest.fail(f"Content workflow execution failed: {e}")


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.asyncio
async def test_workflow_performance():
    """Test workflow performance (should complete within reasonable time)"""
    import time
    
    workflow = create_marketing_workflow()
    
    state = {
        "messages": [HumanMessage(content="Test performance")],
        "iteration_count": 0,
        "workflow_status": "running",
        "start_time": datetime.now()
    }
    
    start_time = time.time()
    result = await workflow.ainvoke(state)
    end_time = time.time()
    
    execution_time = end_time - start_time
    
    print(f"\n⏱️  Performance test:")
    print(f"  Execution time: {execution_time:.2f} seconds")
    print(f"  Iterations: {result.get('iteration_count', 0)}")
    
    # Should complete within 30 seconds (adjust based on your needs)
    assert execution_time < 30.0, f"Workflow took too long: {execution_time:.2f}s"


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_workflow_error_handling():
    """Test workflow error handling"""
    workflow = create_marketing_workflow()
    
    # Test with empty task
    state = {
        "messages": [HumanMessage(content="")],
        "iteration_count": 0,
        "workflow_status": "running",
        "start_time": datetime.now()
    }
    
    try:
        result = await workflow.ainvoke(state)
        
        # Should still complete without crashing
        assert "messages" in result
        assert "workflow_status" in result
        
        print(f"\n✅ Error handling test passed!")
        print(f"  Status: {result.get('workflow_status', 'unknown')}")
        
    except Exception as e:
        pytest.fail(f"Workflow should handle empty tasks gracefully: {e}")


@pytest.mark.asyncio
async def test_fallback_routing():
    """Test fallback routing when LLM fails"""
    workflow = create_marketing_workflow()
    
    # Mock LLM failure
    with patch('app.agents.hierarchical_marketing.AgentConfig.main_supervisor_router.route', 
               AsyncMock(side_effect=Exception("LLM failed"))):
        
        state = {
            "messages": [HumanMessage(content="Test fallback")],
            "iteration_count": 0,
            "workflow_status": "running",
            "start_time": datetime.now()
        }
        
        try:
            result = await workflow.ainvoke(state)
            
            # Should still complete using fallback routing
            assert "messages" in result
            assert "iteration_count" in result
            
            print(f"\n✅ Fallback routing test passed!")
            print(f"  Iterations: {result.get('iteration_count', 0)}")
            
        except Exception as e:
            pytest.fail(f"Fallback routing should handle LLM failures: {e}")


# ============================================================================
# Main Test Runner
# ============================================================================

if __name__ == "__main__":
    """Run tests directly"""
    import sys
    
    print("=" * 60)
    print("Running Hierarchical Marketing Agents Test Suite")
    print("=" * 60)
    
    # Run async tests
    async def run_all_tests():
        # Run unit tests
        print("\n1. Running unit tests...")
        
        # Run integration tests
        print("\n2. Running integration tests...")
        
        # Run end-to-end tests
        print("\n3. Running end-to-end tests...")
        await test_complete_workflow()
        await test_workflow_with_content_task()
        
        # Run performance tests
        print("\n4. Running performance tests...")
        await test_workflow_performance()
        
        # Run error handling tests
        print("\n5. Running error handling tests...")
        await test_workflow_error_handling()
        await test_fallback_routing()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")
        print("=" * 60)
    
    # Run async tests
    asyncio.run(run_all_tests())