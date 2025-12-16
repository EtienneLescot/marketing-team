#!/usr/bin/env python3
"""
Unit tests for DynamicGraphBuilder class.
"""

import pytest
import tempfile
import os
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.agents.dynamic_graph_builder import DynamicGraphBuilder
from app.utils.config_loader import load_config


class TestDynamicGraphBuilder:
    """Test suite for DynamicGraphBuilder."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_config_dir = Path("config")
        
    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        builder = DynamicGraphBuilder("config/simple_team.yaml")
        assert builder.config is not None
        assert "agents" in builder.config
        assert len(builder.config["agents"]) > 0
        
    def test_load_nonexistent_config(self):
        """Test loading a non-existent configuration file."""
        with pytest.raises(FileNotFoundError):
            DynamicGraphBuilder("config/nonexistent.yaml")
    
    def test_list_available_entry_points(self):
        """Test listing available entry points."""
        builder = DynamicGraphBuilder("config/simple_team.yaml")
        entry_points = builder.list_available_entry_points()
        
        assert isinstance(entry_points, list)
        assert len(entry_points) == 3  # simple_supervisor, worker_a, worker_b
        
        # Check structure of entry points
        for ep in entry_points:
            assert "name" in ep
            assert "type" in ep
            assert "managed_agents" in ep
            assert "has_tools" in ep
            assert "require_approval" in ep
    
    def test_validate_entry_point(self):
        """Test entry point validation."""
        builder = DynamicGraphBuilder("config/simple_team.yaml")
        
        # Valid entry points
        assert builder.validate_entry_point("simple_supervisor") is True
        assert builder.validate_entry_point("worker_a") is True
        assert builder.validate_entry_point("worker_b") is True
        
        # Invalid entry points
        assert builder.validate_entry_point("nonexistent") is False
        assert builder.validate_entry_point("") is False
    
    def test_validate_config_for_graph_valid(self):
        """Test configuration validation with valid config."""
        builder = DynamicGraphBuilder("config/simple_team.yaml")
        errors = builder.validate_config_for_graph()
        
        # Simple team should have no errors
        assert errors == []
    
    def test_validate_config_for_graph_cycle(self):
        """Test configuration validation with cycles."""
        builder = DynamicGraphBuilder("config/cycle_test.yaml")
        errors = builder.validate_config_for_graph()
        
        # Should detect cycles
        assert len(errors) > 0
        assert any("Cycle detected" in error for error in errors)
    
    def test_build_graph_single_agent(self):
        """Test building graph for single agent entry point."""
        builder = DynamicGraphBuilder("config/simple_team.yaml")
        
        # Mock checkpointer
        mock_checkpointer = Mock()
        
        # Build graph for worker_a (single worker)
        with patch.object(builder, '_create_worker_node') as mock_create_worker:
            mock_create_worker.return_value = Mock()
            
            workflow = builder.build_graph(
                entry_point="worker_a",
                checkpointer=mock_checkpointer
            )
            
            # Should create a workflow
            assert workflow is not None
            # Should call create_worker_node for worker_a
            mock_create_worker.assert_called_once()
    
    def test_build_graph_supervisor(self):
        """Test building graph for supervisor entry point."""
        builder = DynamicGraphBuilder("config/simple_team.yaml")
        
        # Mock methods
        mock_checkpointer = Mock()
        
        with patch.object(builder, '_create_supervisor_node') as mock_create_supervisor, \
             patch.object(builder, '_create_worker_node') as mock_create_worker, \
             patch.object(builder, '_build_recursive') as mock_build_recursive:
            
            mock_create_supervisor.return_value = Mock()
            mock_create_worker.return_value = Mock()
            mock_build_recursive.return_value = ({"simple_supervisor": Mock()}, [])
            
            workflow = builder.build_graph(
                entry_point="simple_supervisor",
                checkpointer=mock_checkpointer
            )
            
            assert workflow is not None
            # Should call build_recursive for supervisor hierarchy
            mock_build_recursive.assert_called_once()
    
    def test_build_recursive(self):
        """Test recursive graph building."""
        builder = DynamicGraphBuilder("config/simple_team.yaml")
        
        # Mock node creation methods
        with patch.object(builder, '_create_supervisor_node') as mock_create_supervisor, \
             patch.object(builder, '_create_worker_node') as mock_create_worker:
            
            mock_create_supervisor.return_value = Mock()
            mock_create_worker.return_value = Mock()
            
            nodes, edges = builder._build_recursive("simple_supervisor")
            
            # Should create nodes for supervisor and its workers
            assert "simple_supervisor" in nodes
            assert "worker_a" in nodes
            assert "worker_b" in nodes
            
            # Should create edges
            assert len(edges) > 0
    
    def test_detect_cycles(self):
        """Test cycle detection."""
        builder = DynamicGraphBuilder("config/cycle_test.yaml")
        
        cycles = builder._detect_cycles()
        
        # Should detect cycles in cycle_test.yaml
        assert len(cycles) > 0
        
        # Check specific cycles
        cycle_strings = [str(cycle) for cycle in cycles]
        assert any("agent_a" in s and "agent_b" in s and "agent_c" in s for s in cycle_strings)
        assert any("self_ref_agent" in s for s in cycle_strings)
    
    def test_check_missing_managed_agents(self):
        """Test detection of missing managed agents."""
        # Create a temporary config with missing agent reference
        config_content = """
        agents:
          - name: "supervisor"
            role: "supervisor"
            managed_agents:
              - "missing_worker"
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name
        
        try:
            builder = DynamicGraphBuilder(temp_path)
            missing = builder._check_missing_managed_agents()
            
            # Should detect missing_worker
            assert len(missing) > 0
            assert any("missing_worker" in item for item in missing)
        finally:
            os.unlink(temp_path)
    
    def test_create_supervisor_node(self):
        """Test supervisor node creation."""
        builder = DynamicGraphBuilder("config/simple_team.yaml")
        
        # Get supervisor config
        supervisor_config = None
        for agent in builder.config["agents"]:
            if agent["name"] == "simple_supervisor":
                supervisor_config = agent
                break
        
        assert supervisor_config is not None
        
        # Mock dependencies
        with patch('app.agents.dynamic_graph_builder.create_structured_router') as mock_router:
            mock_router.return_value = Mock()
            
            node = builder._create_supervisor_node(supervisor_config)
            
            # Should create a node
            assert node is not None
            # Should call create_structured_router
            mock_router.assert_called_once()
    
    def test_create_worker_node(self):
        """Test worker node creation."""
        builder = DynamicGraphBuilder("config/simple_team.yaml")
        
        # Get worker config
        worker_config = None
        for agent in builder.config["agents"]:
            if agent["name"] == "worker_a":
                worker_config = agent
                break
        
        assert worker_config is not None
        
        # Mock dependencies
        with patch('app.agents.dynamic_graph_builder.create_agent_with_tools') as mock_agent:
            mock_agent.return_value = Mock()
            
            node = builder._create_worker_node(worker_config)
            
            # Should create a node
            assert node is not None
            # Should call create_agent_with_tools
            mock_agent.assert_called_once()
    
    def test_config_inheritance(self):
        """Test configuration inheritance."""
        builder = DynamicGraphBuilder("config/inheritance_test.yaml")
        
        # Check that inheritance worked
        assert builder.config is not None
        assert "agents" in builder.config
        
        # Should have agents from both parent and child
        agent_names = [agent["name"] for agent in builder.config["agents"]]
        assert "research_supervisor" in agent_names
        assert "specialized_supervisor" in agent_names
        assert "analytics_tracker" in agent_names
        
        # Check that web_researcher was overridden (has linkedin_post tool)
        web_researcher = None
        for agent in builder.config["agents"]:
            if agent["name"] == "web_researcher":
                web_researcher = agent
                break
        
        assert web_researcher is not None
        assert "tools" in web_researcher
        assert "linkedin_post" in web_researcher["tools"]
    
    def test_tool_configuration_integration(self):
        """Test tool configuration loading and integration."""
        builder = DynamicGraphBuilder("config/research_team.yaml")
        
        # Check that tools are loaded
        assert "tools" in builder.config
        
        # Check specific tool configurations
        tools = builder.config["tools"]
        assert "tavily_search" in tools
        assert "mock_search" in tools
        
        # Check tool parameters
        tavily_config = tools["tavily_search"]
        assert tavily_config["type"] == "tavily"
        assert tavily_config["max_results"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])