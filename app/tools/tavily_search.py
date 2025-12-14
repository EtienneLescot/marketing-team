#!/usr/bin/env python3
"""
Tavily search API integration for web research.
"""

import os
import json
import aiohttp
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.tools.tool_registry import BaseTool, ToolMetadata
from app.models.state_models import APIError, RateLimitError, TimeoutError


class TavilySearchTool(BaseTool):
    """Web search using Tavily API"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="tavily_search",
            description="Perform web searches using Tavily API",
            category="research",
            cost_per_call=0.001,  # $0.001 per search (estimated)
            rate_limit=100,  # 100 calls per minute (free tier)
            requires_auth=True,
            auth_env_var="TAVILY_API_KEY"
        )
        super().__init__(metadata)
        self.api_key = os.getenv("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com"
        
        # Cache for search results (simple in-memory cache)
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 3600  # 1 hour in seconds
    
    async def execute(
        self, 
        query: str, 
        max_results: int = 5, 
        search_depth: str = "basic",
        use_cache: bool = True,
        cache_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a web search"""
        start_time = datetime.now()
        self.call_count += 1
        
        # Check if API key is available
        if not self.api_key:
            self.error_count += 1
            raise APIError(
                message="TAVILY_API_KEY environment variable not set",
                component="TavilySearchTool",
                operation="execute",
                context={"query": query},
                suggested_action="Set TAVILY_API_KEY environment variable with your Tavily API key",
                retryable=False
            )
        
        # Generate cache key if not provided
        if cache_key is None:
            cache_key = f"{query}_{max_results}_{search_depth}"
        
        # Check cache if enabled
        if use_cache and cache_key in self.cache:
            cached_result = self.cache[cache_key]
            cache_age = (datetime.now() - cached_result["cached_at"]).total_seconds()
            
            if cache_age < self.cache_ttl:
                # Update stats for cache hit
                duration = (datetime.now() - start_time).total_seconds() * 1000
                self.total_duration += duration
                
                result = cached_result["result"].copy()
                result["cached"] = True
                result["cache_age_seconds"] = cache_age
                return result
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": True,
            "include_raw_content": False,
            "include_images": True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/search",
                    json=payload,
                    headers=headers,
                    timeout=30
                ) as response:
                    # Get response text first to handle both JSON and text responses
                    response_text = await response.text()
                    
                    if response.status == 200:
                        try:
                            # Try to parse as JSON
                            data = json.loads(response_text)
                            
                            # Validate that data is a dictionary
                            if not isinstance(data, dict):
                                self.error_count += 1
                                raise APIError(
                                    message=f"Tavily API returned non-dict response: {type(data)}",
                                    component="TavilySearchTool",
                                    operation="execute",
                                    context={
                                        "query": query,
                                        "status_code": response.status,
                                        "response_type": str(type(data)),
                                        "response_preview": str(data)[:200]
                                    },
                                    suggested_action="Check Tavily API documentation or contact support",
                                    retryable=True
                                )
                            
                            # Calculate cost and duration
                            duration = (datetime.now() - start_time).total_seconds() * 1000
                            self.total_duration += duration
                            self.total_cost += self.metadata.cost_per_call
                            
                            # Format results
                            result = self._format_results(data, query)
                            
                            # Cache the result
                            self.cache[cache_key] = {
                                "result": result,
                                "cached_at": datetime.now()
                            }
                            
                            # Clean old cache entries
                            self._clean_cache()
                            
                            return result
                            
                        except json.JSONDecodeError:
                            # If not JSON, treat as text response
                            self.error_count += 1
                            raise APIError(
                                message=f"Tavily API returned non-JSON response: {response_text[:200]}",
                                component="TavilySearchTool",
                                operation="execute",
                                context={
                                    "query": query,
                                    "status_code": response.status,
                                    "response": response_text[:500]
                                },
                                suggested_action="Check Tavily API status or contact support",
                                retryable=True
                            )
                    
                    elif response.status == 429:
                        # Rate limit exceeded
                        self.error_count += 1
                        raise RateLimitError(
                            message="Tavily API rate limit exceeded",
                            component="TavilySearchTool",
                            operation="execute",
                            context={
                                "query": query,
                                "status_code": response.status,
                                "response": response_text[:500]
                            },
                            suggested_action="Wait before retrying or upgrade your Tavily plan",
                            retryable=True
                        )
                    
                    elif response.status == 401:
                        # Authentication error
                        self.error_count += 1
                        raise APIError(
                            message=f"Tavily API authentication failed: {response_text}",
                            component="TavilySearchTool",
                            operation="execute",
                            context={
                                "query": query,
                                "status_code": response.status,
                                "response": response_text[:500]
                            },
                            suggested_action="Check your TAVILY_API_KEY environment variable",
                            retryable=False
                        )
                    
                    else:
                        # Other API error
                        self.error_count += 1
                        raise APIError(
                            message=f"Tavily API error: {response.status} - {response_text}",
                            component="TavilySearchTool",
                            operation="execute",
                            context={
                                "query": query,
                                "status_code": response.status,
                                "error": response_text[:500]
                            },
                            retryable=True
                        )
        
        except asyncio.TimeoutError:
            self.error_count += 1
            raise TimeoutError(
                message="Tavily API request timed out after 30 seconds",
                component="TavilySearchTool",
                operation="execute",
                context={"query": query},
                suggested_action="Check your network connection or try again later",
                retryable=True
            )
        
        except Exception as e:
            self.error_count += 1
            raise APIError(
                message=f"Unexpected error in Tavily search: {str(e)}",
                component="TavilySearchTool",
                operation="execute",
                context={"query": query, "error": str(e)},
                original_exception=e,
                retryable=True
            )
    
    def _format_results(self, data: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Format search results"""
        try:
            # Safely get values with type checking
            if not isinstance(data, dict):
                raise ValueError(f"Expected dict but got {type(data)}: {str(data)[:200]}")
            
            results = data.get("results", [])
            answer = data.get("answer", "")
            images = data.get("images", [])
            
            # Ensure results is a list
            if not isinstance(results, list):
                results = []
            
            # Ensure images is a list
            if not isinstance(images, list):
                images = []
            
            # Format individual results
            formatted_results = []
            for i, result in enumerate(results[:10]):  # Limit to 10 results
                if isinstance(result, dict):
                    formatted_results.append({
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": str(result.get("content", ""))[:500],  # Truncate content
                        "score": float(result.get("score", 0.0)),
                        "published_date": result.get("published_date"),
                        "rank": i + 1
                    })
            
            # Format images
            formatted_images = []
            for image in images[:5]:  # Limit to 5 images
                if isinstance(image, dict):
                    formatted_images.append({
                        "url": image.get("url", ""),
                        "title": image.get("title", ""),
                        "source": image.get("source", "")
                    })
            
            return {
                "query": query,
                "answer": str(answer),
                "total_results": len(formatted_results),
                "results": formatted_results,
                "images": formatted_images,
                "search_timestamp": datetime.now().isoformat(),
                "source": "tavily",
                "cached": False
            }
            
        except Exception as e:
            # If formatting fails, return a minimal result with error info
            return {
                "query": query,
                "answer": f"Error formatting results: {str(e)[:200]}",
                "total_results": 0,
                "results": [],
                "images": [],
                "search_timestamp": datetime.now().isoformat(),
                "source": "tavily",
                "cached": False,
                "error": str(e)
            }
    
    def _clean_cache(self):
        """Clean old cache entries"""
        current_time = datetime.now()
        keys_to_remove = []
        
        for key, cached_data in self.cache.items():
            cache_age = (current_time - cached_data["cached_at"]).total_seconds()
            if cache_age > self.cache_ttl:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.cache[key]
    
    async def search_multiple(
        self, 
        queries: List[str], 
        max_results_per_query: int = 3
    ) -> Dict[str, Any]:
        """Execute multiple searches and combine results"""
        tasks = []
        for query in queries:
            task = self.execute(
                query=query,
                max_results=max_results_per_query,
                search_depth="basic"
            )
            tasks.append(task)
        
        # Execute all searches concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        combined_results = {
            "queries": queries,
            "total_searches": len(queries),
            "successful_searches": 0,
            "failed_searches": 0,
            "all_results": [],
            "combined_answer": "",
            "search_timestamp": datetime.now().isoformat()
        }
        
        answers = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                combined_results["failed_searches"] += 1
                continue
            
            combined_results["successful_searches"] += 1
            combined_results["all_results"].append({
                "query": queries[i],
                "results": result.get("results", []),
                "answer": result.get("answer", "")
            })
            
            if result.get("answer"):
                answers.append(result["answer"])
        
        # Create a combined answer
        if answers:
            combined_results["combined_answer"] = " ".join(answers)
        
        return combined_results
    
    def clear_cache(self):
        """Clear the search cache"""
        self.cache.clear()


# Factory function to create and register Tavily search tool
def create_tavily_search_tool() -> TavilySearchTool:
    """Create and return a Tavily search tool instance"""
    tool = TavilySearchTool()
    
    # Check if API key is available
    if not tool.api_key:
        print("⚠️  WARNING: TAVILY_API_KEY environment variable not set.")
        print("   Tavily search tool will not work without an API key.")
        print("   Get a free API key from: https://app.tavily.com/")
        print("   Then set it in your .env file: TAVILY_API_KEY=your_key_here")
    
    return tool