#!/usr/bin/env python3
"""
Utilities for message processing in hierarchical agent systems.
"""

from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage


def extract_original_task(
    messages: List[BaseMessage],
    clean_text: bool = True
) -> Optional[str]:
    """
    Extract the original user task from message history.
    
    Args:
        messages: List of messages in the conversation
        clean_text: Whether to clean the text (extract repo info, remove URLs)
        
    Returns:
        The original user task text, or None if not found
    """
    # Look for the first human message (original task)
    for message in messages:
        if isinstance(message, HumanMessage):
            task_text = message.content
            if clean_text:
                return clean_task_text(task_text)
            return task_text
    
    # If no human message found, check the last message
    if messages:
        task_text = messages[-1].content
        if clean_text:
            return clean_task_text(task_text)
        return task_text
    
    return None


def extract_last_agent_output(messages: List[BaseMessage]) -> Optional[str]:
    """
    Extract the last agent output from message history.
    
    Args:
        messages: List of messages in the conversation
        
    Returns:
        The last agent output text, or None if not found
    """
    # Look for the last AI message (agent output)
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return message.content
    
    return None


def create_agent_response(
    content: str,
    agent_name: str,
    include_original_task: bool = False,
    original_task: Optional[str] = None
) -> List[BaseMessage]:
    """
    Create a proper agent response message.
    
    Args:
        content: The agent's response content
        agent_name: Name of the agent
        include_original_task: Whether to include the original task in the response
        original_task: The original user task (required if include_original_task is True)
        
    Returns:
        List of messages to update the state with
    """
    message = AIMessage(content=content, name=agent_name)
    
    if include_original_task and original_task:
        # Include both the original task and the agent's response
        return [
            HumanMessage(content=original_task, name="user"),
            message
        ]
    else:
        # Just include the agent's response
        return [message]


def sanitize_messages_for_agent(
    messages: List[BaseMessage],
    max_history: int = 3
) -> List[BaseMessage]:
    """
    Sanitize messages for agent processing.
    
    This prevents message nesting by keeping only:
    1. The original user task
    2. Recent agent responses (up to max_history)
    
    Args:
        messages: Original message list
        max_history: Maximum number of recent agent responses to keep
        
    Returns:
        Sanitized message list
    """
    if not messages:
        return []
    
    # Find the original user task
    original_task = None
    for message in messages:
        if isinstance(message, HumanMessage):
            original_task = message
            break
    
    # Find recent agent responses
    agent_responses = []
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            agent_responses.append(message)
            if len(agent_responses) >= max_history:
                break
    
    # Build sanitized list
    sanitized = []
    if original_task:
        sanitized.append(original_task)
    
    # Add agent responses in chronological order
    for response in reversed(agent_responses):
        sanitized.append(response)
    
    return sanitized


def calculate_message_complexity(messages: List[BaseMessage]) -> Dict[str, Any]:
    """
    Calculate complexity metrics for message history.
    
    Args:
        messages: List of messages
        
    Returns:
        Dictionary with complexity metrics
    """
    if not messages:
        return {
            "total_messages": 0,
            "human_messages": 0,
            "ai_messages": 0,
            "system_messages": 0,
            "total_characters": 0,
            "avg_message_length": 0
        }
    
    human_count = 0
    ai_count = 0
    system_count = 0
    total_chars = 0
    
    for message in messages:
        if isinstance(message, HumanMessage):
            human_count += 1
        elif isinstance(message, AIMessage):
            ai_count += 1
        elif isinstance(message, SystemMessage):
            system_count += 1
        
        total_chars += len(message.content)
    
    total_messages = len(messages)
    avg_length = total_chars / max(total_messages, 1)
    
    return {
        "total_messages": total_messages,
        "human_messages": human_count,
        "ai_messages": ai_count,
        "system_messages": system_count,
        "total_characters": total_chars,
        "avg_message_length": avg_length,
        "nesting_ratio": ai_count / max(human_count, 1)  # Higher ratio indicates more nesting
    }


def detect_message_nesting(messages: List[BaseMessage], threshold: float = 3.0) -> bool:
    """
    Detect if message nesting is occurring.
    
    Nesting occurs when there are many more AI messages than human messages,
    indicating agents are processing other agents' outputs.
    
    Args:
        messages: List of messages
        threshold: AI-to-human ratio threshold for detecting nesting
        
    Returns:
        True if nesting is detected, False otherwise
    """
    metrics = calculate_message_complexity(messages)
    return metrics["nesting_ratio"] > threshold


def reset_message_nesting(
    messages: List[BaseMessage],
    keep_original: bool = True
) -> List[BaseMessage]:
    """
    Reset message nesting by keeping only essential messages.
    
    Args:
        messages: Original message list
        keep_original: Whether to keep the original user task
        
    Returns:
        Reset message list
    """
    if not messages:
        return []
    
    reset_messages = []
    
    if keep_original:
        # Find and keep the original user task
        for message in messages:
            if isinstance(message, HumanMessage):
                reset_messages.append(message)
                break
    
    # If no original task was found but we have messages, keep the first one
    if not reset_messages and messages:
        reset_messages.append(messages[0])
    
    return reset_messages


def extract_github_repo_info(task_text: str) -> Dict[str, Any]:
    """
    Extract GitHub repository information from task text.
    
    Args:
        task_text: The task text that may contain GitHub URLs
        
    Returns:
        Dictionary with repository information
    """
    import re
    
    # Pattern to match GitHub URLs
    github_pattern = r'https?://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)'
    
    matches = re.findall(github_pattern, task_text)
    
    if not matches:
        return {
            "has_repo": False,
            "repo_url": None,
            "owner": None,
            "repo_name": None,
            "full_name": None
        }
    
    # Get the first match
    owner, repo_name = matches[0]
    repo_url = f"https://github.com/{owner}/{repo_name}"
    full_name = f"{owner}/{repo_name}"
    
    return {
        "has_repo": True,
        "repo_url": repo_url,
        "owner": owner,
        "repo_name": repo_name,
        "full_name": full_name
    }


def clean_task_text(task_text: str) -> str:
    """
    Clean task text by removing URLs and extracting key information.
    
    Args:
        task_text: Original task text
        
    Returns:
        Cleaned task text
    """
    import re
    
    # Extract GitHub repo info
    repo_info = extract_github_repo_info(task_text)
    
    if repo_info["has_repo"]:
        # Remove the URL from the text
        url_pattern = re.escape(repo_info["repo_url"])
        cleaned = re.sub(url_pattern, '', task_text)
        
        # Also remove common URL preface phrases
        url_phrases = [
            r'here is the repo url:',
            r'here is the repository:',
            r'repository url:',
            r'github url:',
            r'url:',
            r'link:'
        ]
        
        for phrase in url_phrases:
            cleaned = re.sub(phrase, '', cleaned, flags=re.IGNORECASE)
        
        # Clean up extra spaces and punctuation
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        cleaned = re.sub(r'[.,;:\s]+$', '', cleaned)
        
        # If the cleaned text is empty or just whitespace, create a concise version
        if not cleaned or len(cleaned.strip()) < 10:
            return f"Promote GitHub repository: {repo_info['full_name']}"
        
        # Add repo name context if not already mentioned
        if repo_info["full_name"].lower() not in cleaned.lower():
            cleaned = f"{cleaned} (Repository: {repo_info['full_name']})"
        
        return cleaned
    
    return task_text