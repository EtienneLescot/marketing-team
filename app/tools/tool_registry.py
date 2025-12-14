#!/usr/bin/env python3
"""
Tool registry for managing all tools in the hierarchical marketing agents system.
"""

import os
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
import asyncio
from datetime import datetime


@dataclass
class ToolMetadata:
    """Metadata for a tool"""
    name: str
    description: str
    category: str  # "research", "content", "social_media", "analytics"
    cost_per_call: float = 0.0  # Estimated cost in USD
    rate_limit: Optional[int] = None  # Calls per minute
    requires_auth: bool = False
    auth_env_var: Optional[str] = None


class BaseTool(ABC):
    """Base class for all tools"""
    
    def __init__(self, metadata: ToolMetadata):
        self.metadata = metadata
        self.call_count = 0
        self.error_count = 0
        self.total_cost = 0.0
        self.total_duration = 0.0
    
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters"""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tool usage statistics"""
        success_rate = 1 - (self.error_count / max(self.call_count, 1))
        
        return {
            "name": self.metadata.name,
            "description": self.metadata.description,
            "category": self.metadata.category,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "success_rate": success_rate,
            "total_cost": self.total_cost,
            "total_duration": self.total_duration,
            "avg_duration": self.total_duration / max(self.call_count, 1),
            "requires_auth": self.metadata.requires_auth,
            "rate_limit": self.metadata.rate_limit
        }


class ToolRegistry:
    """Registry for managing all tools"""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self.categories: Dict[str, List[str]] = {}
    
    def register_tool(self, tool: BaseTool):
        """Register a tool"""
        self.tools[tool.metadata.name] = tool
        
        # Categorize
        category = tool.metadata.category
        if category not in self.categories:
            self.categories[category] = []
        self.categories[category].append(tool.metadata.name)
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self.tools.get(name)
    
    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """Get all tools in a category"""
        tool_names = self.categories.get(category, [])
        return [self.tools[name] for name in tool_names]
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all tools"""
        stats = {}
        total_cost = 0.0
        total_calls = 0
        total_errors = 0
        
        for name, tool in self.tools.items():
            tool_stats = tool.get_stats()
            stats[name] = tool_stats
            total_cost += tool_stats["total_cost"]
            total_calls += tool_stats["call_count"]
            total_errors += tool_stats["error_count"]
        
        overall_success_rate = 1 - (total_errors / max(total_calls, 1))
        
        stats["summary"] = {
            "total_tools": len(self.tools),
            "total_calls": total_calls,
            "total_errors": total_errors,
            "overall_success_rate": overall_success_rate,
            "total_cost": total_cost,
            "categories": self.categories
        }
        
        return stats
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools"""
        tools_list = []
        for name, tool in self.tools.items():
            tools_list.append({
                "name": name,
                "description": tool.metadata.description,
                "category": tool.metadata.category,
                "requires_auth": tool.metadata.requires_auth,
                "cost_per_call": tool.metadata.cost_per_call,
                "rate_limit": tool.metadata.rate_limit
            })
        return tools_list