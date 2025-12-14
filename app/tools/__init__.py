#!/usr/bin/env python3
"""
Tools package for hierarchical marketing agents system.
"""

import os
from typing import Dict, Any

from app.tools.tool_registry import ToolRegistry, BaseTool
from app.tools.tavily_search import create_tavily_search_tool
from app.tools.mock_search import create_mock_search_tool


def create_tool_registry() -> ToolRegistry:
    """Create and populate the tool registry"""
    registry = ToolRegistry()
    
    # Create search tool (Tavily if API key available, otherwise mock)
    search_tool = create_search_tool()
    registry.register_tool(search_tool)
    
    # Create other tools (to be implemented)
    # registry.register_tool(create_github_tool())
    # registry.register_tool(create_content_generation_tool())
    # registry.register_tool(create_seo_analysis_tool())
    
    return registry


def create_search_tool() -> BaseTool:
    """Create appropriate search tool based on API key availability"""
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    
    if tavily_api_key:
        print("✅ Using Tavily search API (real search results)")
        return create_tavily_search_tool()
    else:
        print("⚠️  Using mock search tool (TAVILY_API_KEY not set)")
        print("   Get a free API key from: https://app.tavily.com/")
        print("   Then set it in your .env file: TAVILY_API_KEY=your_key_here")
        return create_mock_search_tool()


# Export main classes and functions
__all__ = [
    "ToolRegistry",
    "BaseTool",
    "ToolMetadata",
    "create_tool_registry",
    "create_search_tool",
]