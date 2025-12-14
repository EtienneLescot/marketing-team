# Tool Integrations Design for Hierarchical Marketing Agents

## Overview
This document outlines the design for implementing actual tool integrations (web search, APIs, etc.) in the hierarchical marketing agents system, replacing the current mock implementations with real external service integrations.

## Current State Analysis
1. **Mock implementations**: Current tools return placeholder text
2. **No external APIs**: No real web search, data analysis, or social media integrations
3. **Limited functionality**: Cannot perform actual marketing tasks
4. **No error handling**: No handling of API failures or rate limits

## Design Goals
1. **Real functionality**: Replace mocks with actual API integrations
2. **Modular design**: Easy to add/remove tools
3. **Error resilience**: Graceful handling of API failures
4. **Cost optimization**: Efficient use of paid APIs
5. **Caching**: Reduce API calls and improve performance
6. **Monitoring**: Track tool usage and performance

## Architecture

### 1. Tool Registry Pattern

```python
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
import asyncio

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
    
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters"""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tool usage statistics"""
        return {
            "name": self.metadata.name,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "success_rate": 1 - (self.error_count / max(self.call_count, 1)),
            "estimated_cost": self.call_count * self.metadata.cost_per_call
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
        
        for name, tool in self.tools.items():
            tool_stats = tool.get_stats()
            stats[name] = tool_stats
            total_cost += tool_stats["estimated_cost"]
            total_calls += tool_stats["call_count"]
        
        stats["summary"] = {
            "total_tools": len(self.tools),
            "total_calls": total_calls,
            "total_estimated_cost": total_cost,
            "categories": self.categories
        }
        
        return stats
```

### 2. Research Team Tools

#### 2.1 Web Search Tool (Tavily API)

```python
import os
from typing import List, Dict
import aiohttp
from datetime import datetime

class TavilySearchTool(BaseTool):
    """Web search using Tavily API"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="tavily_search",
            description="Perform web searches using Tavily API",
            category="research",
            cost_per_call=0.001,  # $0.001 per search
            rate_limit=100,  # 100 calls per minute
            requires_auth=True,
            auth_env_var="TAVILY_API_KEY"
        )
        super().__init__(metadata)
        self.api_key = os.getenv("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com"
    
    async def execute(self, query: str, max_results: int = 5, search_depth: str = "basic") -> Dict[str, Any]:
        """Execute a web search"""
        self.call_count += 1
        
        if not self.api_key:
            self.error_count += 1
            raise ValueError("TAVILY_API_KEY environment variable not set")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": True,
            "include_raw_content": False
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/search",
                    json=payload,
                    headers=headers,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._format_results(data)
                    else:
                        self.error_count += 1
                        error_text = await response.text()
                        raise Exception(f"Tavily API error: {response.status} - {error_text}")
        
        except asyncio.TimeoutError:
            self.error_count += 1
            raise Exception("Tavily API timeout")
        except Exception as e:
            self.error_count += 1
            raise
    
    def _format_results(self, data: Dict) -> Dict[str, Any]:
        """Format search results"""
        return {
            "query": data.get("query", ""),
            "answer": data.get("answer", ""),
            "results": data.get("results", []),
            "images": data.get("images", []),
            "timestamp": datetime.now().isoformat()
        }
```

#### 2.2 GitHub API Tool

```python
import aiohttp
from typing import List, Dict

class GitHubAPITool(BaseTool):
    """Fetch GitHub repository data"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="github_api",
            description="Fetch GitHub repository metrics and data",
            category="research",
            cost_per_call=0.0,  # Free API (with rate limits)
            rate_limit=60,  # 60 calls per hour for unauthenticated
            requires_auth=False
        )
        super().__init__(metadata)
        self.base_url = "https://api.github.com"
    
    async def execute(self, repo_owner: str, repo_name: str) -> Dict[str, Any]:
        """Get repository information"""
        self.call_count += 1
        
        endpoints = [
            f"/repos/{repo_owner}/{repo_name}",
            f"/repos/{repo_owner}/{repo_name}/stats/contributors",
            f"/repos/{repo_owner}/{repo_name}/languages",
            f"/repos/{repo_owner}/{repo_name}/stargazers?per_page=1"
        ]
        
        results = {}
        
        try:
            async with aiohttp.ClientSession() as session:
                for endpoint in endpoints:
                    async with session.get(
                        f"{self.base_url}{endpoint}",
                        headers={"Accept": "application/vnd.github.v3+json"},
                        timeout=10
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            endpoint_name = endpoint.split("/")[-1]
                            results[endpoint_name] = data
                        else:
                            results[endpoint_name] = {"error": f"Status {response.status}"}
            
            return self._format_repository_data(results)
        
        except Exception as e:
            self.error_count += 1
            raise
    
    def _format_repository_data(self, data: Dict) -> Dict[str, Any]:
        """Format GitHub repository data"""
        repo_info = data.get("repos", {})
        
        return {
            "name": repo_info.get("full_name", ""),
            "description": repo_info.get("description", ""),
            "stars": repo_info.get("stargazers_count", 0),
            "forks": repo_info.get("forks_count", 0),
            "watchers": repo_info.get("watchers_count", 0),
            "open_issues": repo_info.get("open_issues_count", 0),
            "language": repo_info.get("language", ""),
            "languages": data.get("languages", {}),
            "contributor_count": len(data.get("stats", [])),
            "created_at": repo_info.get("created_at", ""),
            "updated_at": repo_info.get("updated_at", "")
        }
```

#### 2.3 Data Analysis Tool (Pandas)

```python
import pandas as pd
import numpy as np
from io import StringIO
import json

class DataAnalysisTool(BaseTool):
    """Perform data analysis using Pandas"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="data_analysis",
            description="Perform data analysis and visualization",
            category="research",
            cost_per_call=0.0,
            requires_auth=False
        )
        super().__init__(metadata)
    
    async def execute(self, data: str, analysis_type: str = "summary") -> Dict[str, Any]:
        """Analyze data"""
        self.call_count += 1
        
        try:
            # Parse data (could be CSV, JSON, or dict)
            if isinstance(data, str):
                # Try to parse as CSV first
                try:
                    df = pd.read_csv(StringIO(data))
                except:
                    # Try as JSON
                    try:
                        data_dict = json.loads(data)
                        df = pd.DataFrame(data_dict)
                    except:
                        raise ValueError("Data must be CSV or JSON format")
            elif isinstance(data, dict):
                df = pd.DataFrame(data)
            else:
                raise ValueError(f"Unsupported data type: {type(data)}")
            
            # Perform analysis based on type
            if analysis_type == "summary":
                result = self._generate_summary(df)
            elif analysis_type == "trends":
                result = self._analyze_trends(df)
            elif analysis_type == "correlation":
                result = self._calculate_correlations(df)
            else:
                result = self._generate_summary(df)
            
            return result
        
        except Exception as e:
            self.error_count += 1
            raise
    
    def _generate_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate statistical summary"""
        return {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "summary_stats": df.describe().to_dict(),
            "missing_values": df.isnull().sum().to_dict(),
            "unique_counts": {col: df[col].nunique() for col in df.columns}
        }
    
    def _analyze_trends(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze trends in time series data"""
        # Implementation for trend analysis
        pass
    
    def _calculate_correlations(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate correlations between numeric columns"""
        numeric_df = df.select_dtypes(include=[np.number])
        if len(numeric_df.columns) < 2:
            return {"message": "Not enough numeric columns for correlation analysis"}
        
        correlation_matrix = numeric_df.corr()
        return {
            "correlation_matrix": correlation_matrix.to_dict(),
            "strong_correlations": self._find_strong_correlations(correlation_matrix)
        }
```

### 3. Content Team Tools

#### 3.1 Content Generation Tool (OpenAI/Anthropic)

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

class ContentGenerationTool(BaseTool):
    """Generate marketing content using LLMs"""
    
    def __init__(self, provider: str = "openai"):
        metadata = ToolMetadata(
            name="content_generation",
            description="Generate marketing content using LLMs",
            category="content",
            cost_per_call=0.01,  # Estimated cost
            requires_auth=True,
            auth_env_var="OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
        )
        super().__init__(metadata)
        self.provider = provider
        
        if provider == "openai":
            self.llm = ChatOpenAI(
                model="gpt-4-turbo-preview",
                api_key=os.getenv("OPENAI_API_KEY")
            )
        else:
            self.llm = ChatAnthropic(
                model="claude-3-sonnet-20240229",
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
        
        self.prompt_templates = {
            "blog_post": ChatPromptTemplate.from_template(
                "Write a blog post about {topic} for a technical audience. "
                "Include: 1. Introduction 2. Key points 3. Examples 4. Conclusion. "
                "Make it engaging and informative."
            ),
            "social_media_post": ChatPromptTemplate.from_template(
                "Create a {platform} post about {topic}. "
                "Make it {tone} and include relevant hashtags. "
                "Character limit: {char_limit}."
            ),
            "email_newsletter": ChatPromptTemplate.from_template(
                "Write an email newsletter about {topic}. "
                "Include: Subject line, greeting, main content, call to action, and signature."
            )
        }
    
    async def execute(self, content_type: str, **kwargs) -> Dict[str, Any]:
        """Generate content"""
        self.call_count += 1
        
        if content_type not in self.prompt_templates:
            self.error_count += 1
            raise ValueError(f"Unsupported content type: {content_type}")
        
        try:
            prompt = self.prompt_templates[content_type].format(**kwargs)
            response = await self.llm.ainvoke(prompt)
            
            return {
                "content_type": content_type,
                "content": response.content,
                "provider": self.provider,
                "model": self.llm.model_name,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            self.error_count += 1
            raise
```

#### 3.2 SEO Analysis Tool

```python
import re
from typing import List

class SEOAnalysisTool(BaseTool):
    """Analyze content for SEO optimization"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="seo_analysis",
            description="Analyze content for SEO optimization",
            category="content",
            cost_per_call=0.0,
            requires_auth=False
        )
        super().__init__(metadata)
    
    async def execute(self, content: str, target_keywords: List[str] = None) -> Dict[str, Any]:
        """Analyze SEO metrics"""
        self.call_count += 1
        
        try:
            analysis = {
                "word_count": len(content.split()),
                "character_count": len(content),
                "reading_time_minutes": len(content.split()) / 200,  # 200 wpm
                "keyword_density": self._calculate_keyword_density(content, target_keywords),
                "headings": self._extract_headings(content),
                "links": self._extract_links(content),
                "readability_score": self._calculate_readability(content),
                "recommendations": self._generate_recommendations(content, target_keywords)
            }
            
            return analysis
        
        except Exception as e:
            self.error_count += 1
            raise
    
    def _calculate_keyword_density(self, content: str, keywords: List[str]) -> Dict[str, float]:
        """Calculate keyword density"""
        if not keywords:
            return {}
        
        content_lower = content.lower()
        word_count = len(content.split())
        
        densities = {}
        for keyword in keywords:
            keyword_lower = keyword.lower()
            count = len(re.findall(rf'\b{re.escape(keyword_lower)}\b', content_lower))
            density = (count / max(word_count, 1)) * 100
            densities[keyword] = round(density, 2)
        
        return densities
    
    def _extract_headings(self, content: str) -> Dict[str, List[str]]:
        """Extract headings from content"""
        headings = {
            "h1": re.findall(r'^#\s+(.+)$', content, re.MULTILINE),
            "h2": re.findall(r'^##\s+(.+)$', content, re.MULTILINE),
            "h3": re.findall(r'^###\s+(.+)$', content, re.MULTILINE)
        }
        return headings
    
    def _extract_links(self, content: str) -> List[Dict[str, str]]:
        """Extract links from content"""
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        links = []
        
        for match in re.finditer(link_pattern, content):
            links.append({
                "text": match.group(1),
                "url": match.group(2)
            })
        
        return links
    
    def _calculate_readability(self, content: str) -> float:
        """Calculate Flesch Reading Ease score"""
        # Simplified implementation
        sentences = len(re.split(r'[.!?]+', content))
        words = len(content.split())
        syllables = sum(len(re.findall(r'[aeiouy]+', word.lower