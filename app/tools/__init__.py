#!/usr/bin/env python3
"""
Tools package for hierarchical marketing agents system.
"""

import os
from typing import Dict, Any

from app.tools.tool_registry import ToolRegistry, BaseTool, ToolMetadata
from app.tools.tavily_search import create_tavily_search_tool
from app.tools.mock_search import create_mock_search_tool
from app.tools.linkedin import create_linkedin_tool
from app.tools.mock_linkedin import create_mock_linkedin_tool


def create_tool_registry() -> ToolRegistry:
    """Create and populate the tool registry"""
    registry = ToolRegistry()
    
    # Create search tool (Tavily if API key available, otherwise mock)
    search_tool = create_search_tool()
    registry.register_tool(search_tool)
    
    # Create LinkedIn tool (real if credentials available, otherwise mock)
    linkedin_tool = create_linkedin_tool_choice()
    registry.register_tool(linkedin_tool)
    
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


def create_linkedin_tool_choice() -> BaseTool:
    """Create appropriate LinkedIn tool based on credentials availability"""
    linkedin_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    
    if linkedin_token:
        print("✅ Using real LinkedIn API (requires valid credentials)")
        return create_linkedin_tool()
    else:
        print("⚠️  Using mock LinkedIn tool (LINKEDIN_ACCESS_TOKEN not set)")
        print("   To use real LinkedIn API:")
        print("   1. Run: python scripts/get_linkedin_token.py")
        print("   2. Set LINKEDIN_ACCESS_TOKEN in your .env file")
        print("   3. Set LINKEDIN_COMPANY_URN for company posts")
        return create_mock_linkedin_tool()


# Export main classes and functions
__all__ = [
    "ToolRegistry",
    "BaseTool",
    "ToolMetadata",
    "create_tool_registry",
    "create_search_tool",
    "create_linkedin_tool_choice",
]