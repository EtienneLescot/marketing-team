#!/usr/bin/env python3
"""
Marketing Agents - Hierarchical agent system for marketing automation.

This package provides hierarchical marketing agents with LLM-based routing,
tool integration, and comprehensive monitoring.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Export version
__version__ = "0.1.0"

# Export key components for easy access
__all__ = [
    "load_dotenv",
    "__version__"
]

# Print debug info in development
if os.getenv("DEBUG", "false").lower() == "true":
    print(f"Marketing Agents v{__version__}")
    print(f"Environment loaded: {'TAVILY_API_KEY' in os.environ}")
    print(f"Current directory: {os.getcwd()}")