#!/usr/bin/env python3
"""
Unit tests for config_loader module.
"""

import pytest
import tempfile
import os
import yaml
from pathlib import Path

from app.utils.config_loader import load_config, _load_yaml_with_inheritance, _merge_configs


class TestConfigLoader:
    """Test suite for config_loader module."""
    
    def test_load_yaml_with_inheritance_basic(self):
        """Test loading YAML without inheritance."""
        # Create a simple YAML file
        yaml_content = """
        defaults:
          provider: "test"
        agents:
          - name: "test_agent"
            role: "worker"
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = _load_yaml_with_inheritance(temp_path)
            
            assert config is not None
            assert "defaults" in config
            assert config["defaults"]["provider"] == "test"
            assert "agents" in config
            assert len(config["agents"]) == 1
            assert config["agents"][0]["name"] == "test_agent"
        finally:
            os.unlink(temp_path)
    
    def test_load_yaml_with_inheritance_single_level(self):
        """Test loading YAML with single-level inheritance."""
        # Create parent YAML
        parent_content = """
        defaults:
          provider: "parent"
          model: "parent-model"
        agents:
          - name: "parent_agent"
            role: "supervisor"
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as parent_file:
            parent_file.write(parent_content)
            parent_path = parent_file.name
        
        # Create child YAML
        child_content = f"""
        inherit_from: "{parent_path}"
        defaults:
          provider: "child"  # Override
        agents:
          - name: "child_agent"
            role: "worker"
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as child_file:
            child_file.write(child_content)
            child_path = child_file.name
        
        try:
            config = _load_yaml_with_inheritance(child_path)
            
            # Should inherit from parent
            assert config is not None
            
            # Defaults should be merged (child overrides parent)
            assert config["defaults"]["provider"] == "child"
            assert config["defaults"]["model"] == "parent-model"  # From parent
            
            # Agents should be merged
            agent_names = [agent["name"] for agent in config["agents"]]
            assert "parent_agent" in agent_names
            assert "child_agent" in agent_names
        finally:
            os.unlink(parent_path)
            os.unlink(child_path)
    
    def test_load_yaml_with_inheritance_multi_level(self):
        """Test loading YAML with multi-level inheritance."""
        # Create grandparent
        grandparent_content = """
        defaults:
          provider: "grandparent"
          temperature: 0.7
        agents:
          - name: "grandparent_agent"
            role: "supervisor"
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as gp_file:
            gp_file.write(grandparent_content)
            gp_path = gp_file.name
        
        # Create parent
        parent_content = f"""
        inherit_from: "{gp_path}"
        defaults:
          provider: "parent"
          max_tokens: 1000
        agents:
          - name: "parent_agent"
            role: "worker"
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as p_file:
            p_file.write(parent_content)
            p_path = p_file.name
        
        # Create child
        child_content = f"""
        inherit_from: "{p_path}"
        defaults:
          provider: "child"
        agents:
          - name: "child_agent"
            role: "worker"
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as c_file:
            c_file.write(child_content)
            c_path = c_file.name
        
        try:
            config = _load_yaml_with_inheritance(c_path)
            
            # Should inherit from all ancestors
            assert config is not None
            
            # Defaults should be merged with child having highest priority
            assert config["defaults"]["provider"] == "child"
            assert config["defaults"]["temperature"] == 0.7  # From grandparent
            assert config["defaults"]["max_tokens"] == 1000  # From parent
            
            # Agents should be merged from all levels
            agent_names = [agent["name"] for agent in config["agents"]]
            assert "grandparent_agent" in agent_names
            assert "parent_agent" in agent_names
            assert "child_agent" in agent_names
        finally:
            os.unlink(gp_path)
            os.unlink(p_path)
            os.unlink(c_path)
    
    def test_load_yaml_with_inheritance_circular(self):
        """Test loading YAML with circular inheritance (should handle gracefully)."""
        # Create file A that inherits from B
        content_a = """
        inherit_from: "file_b.yaml"
        defaults:
          provider: "a"
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as a_file:
            a_file.write(content_a)
            a_path = a_file.name
        
        # Create file B that inherits from A (circular)
        content_b = f"""
        inherit_from: "{a_path}"
        defaults:
          provider: "b"
        """
        
        b_path = os.path.join(os.path.dirname(a_path), "file_b.yaml")
        with open(b_path, 'w') as b_file:
            b_file.write(content_b)
        
        try:
            # Should detect circular reference and handle it
            config = _load_yaml_with_inheritance(a_path)
            
            # Should still load something
            assert config is not None
            # Should have defaults from both (order depends on implementation)
            assert "defaults" in config
        finally:
            os.unlink(a_path)
            os.unlink(b_path)
    
    def test_merge_configs_basic(self):
        """Test basic config merging."""
        parent = {
            "defaults": {"provider": "parent", "model": "gpt-4"},
            "agents": [{"name": "parent_agent", "role": "supervisor"}]
        }
        
        child = {
            "defaults": {"provider": "child"},  # Override provider
            "agents": [{"name": "child_agent", "role": "worker"}]
        }
        
        merged = _merge_configs(parent, child)
        
        # Defaults should be merged with child overriding
        assert merged["defaults"]["provider"] == "child"
        assert merged["defaults"]["model"] == "gpt-4"  # From parent
        
        # Agents should be concatenated
        assert len(merged["agents"]) == 2
        agent_names = [agent["name"] for agent in merged["agents"]]
        assert "parent_agent" in agent_names
        assert "child_agent" in agent_names
    
    def test_merge_configs_nested_dicts(self):
        """Test merging nested dictionaries."""
        parent = {
            "tools": {
                "search": {"type": "tavily", "max_results": 5},
                "analyze": {"type": "local"}
            }
        }
        
        child = {
            "tools": {
                "search": {"type": "google"},  # Override
                "new_tool": {"type": "custom"}  # Add new
            }
        }
        
        merged = _merge_configs(parent, child)
        
        # Tools should be merged
        assert "tools" in merged
        assert merged["tools"]["search"]["type"] == "google"  # Child overrides
        assert merged["tools"]["analyze"]["type"] == "local"  # From parent
        assert merged["tools"]["new_tool"]["type"] == "custom"  # From child
    
    def test_merge_configs_lists_append(self):
        """Test that lists are appended, not replaced."""
        parent = {
            "providers": ["deepseek", "openai"],
            "models": ["gpt-4", "claude-3"]
        }
        
        child = {
            "providers": ["anthropic"],  # Should append, not replace
            "models": ["llama-3"]  # Should append
        }
        
        merged = _merge_configs(parent, child)
        
        # Lists should be concatenated
        assert len(merged["providers"]) == 3
        assert "deepseek" in merged["providers"]
        assert "openai" in merged["providers"]
        assert "anthropic" in merged["providers"]
        
        assert len(merged["models"]) == 3
        assert "gpt-4" in merged["models"]
        assert "claude-3" in merged["models"]
        assert "llama-3" in merged["models"]
    
    def test_load_config_function(self):
        """Test the public load_config function."""
        # Create a test config
        yaml_content = """
        description: "Test config"
        defaults:
          provider: "test"
        agents:
          - name: "test_agent"
            role: "worker"
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            
            assert config is not None
            assert config["description"] == "Test config"
            assert config["defaults"]["provider"] == "test"
            assert len(config["agents"]) == 1
            assert config["agents"][0]["name"] == "test_agent"
        finally:
            os.unlink(temp_path)
    
    def test_load_config_with_relative_path(self):
        """Test loading config with relative path from config directory."""
        # This test assumes config/agents.yaml exists
        config_path = "config/agents.yaml"
        
        if os.path.exists(config_path):
            config = load_config(config_path)
            
            assert config is not None
            assert "agents" in config
            assert len(config["agents"]) > 0
    
    def test_load_config_nonexistent(self):
        """Test loading non-existent config file."""
        with pytest.raises(FileNotFoundError):
            load_config("config/nonexistent.yaml")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])