#!/usr/bin/env python3
"""
Main script for the LangGraph project.
This script demonstrates the basic setup and usage of LangGraph and LangChain.
"""

from langchain.tools import tool
from langchain.chat_models import init_chat_model


def main():
    print("LangGraph project initialized successfully!")
    print("Dependencies installed:")
    print("  - langgraph")
    print("  - langchain")
    print("\nYou can now start building your LangGraph agents.")


if __name__ == "__main__":
    main()
