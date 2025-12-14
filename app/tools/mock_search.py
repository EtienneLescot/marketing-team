#!/usr/bin/env python3
"""
Mock search tool for testing when real API keys are not available.
"""

import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.tools.tool_registry import BaseTool, ToolMetadata


class MockSearchTool(BaseTool):
    """Mock search tool for testing and development"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="mock_search",
            description="Mock search tool for testing (returns simulated results)",
            category="research",
            cost_per_call=0.0,
            requires_auth=False
        )
        super().__init__(metadata)
        
        # Pre-defined mock results for common queries
        self.mock_results_db = {
            "ai marketing trends": [
                {
                    "title": "Top AI Marketing Trends for 2024",
                    "url": "https://example.com/ai-marketing-trends-2024",
                    "content": "AI is transforming marketing with personalized content, predictive analytics, and automated campaign optimization.",
                    "score": 0.95,
                    "published_date": "2024-01-15"
                },
                {
                    "title": "How Generative AI is Changing Content Marketing",
                    "url": "https://example.com/generative-ai-content-marketing",
                    "content": "Generative AI tools like GPT-4 are enabling marketers to create high-quality content at scale.",
                    "score": 0.88,
                    "published_date": "2024-02-20"
                }
            ],
            "github project promotion": [
                {
                    "title": "Effective GitHub Project Marketing Strategies",
                    "url": "https://example.com/github-project-marketing",
                    "content": "Learn how to promote your GitHub projects through social media, technical blogs, and community engagement.",
                    "score": 0.92,
                    "published_date": "2024-03-10"
                },
                {
                    "title": "Building a Developer Community Around Your Project",
                    "url": "https://example.com/developer-community-building",
                    "content": "Strategies for attracting contributors and users to your open-source project.",
                    "score": 0.85,
                    "published_date": "2024-01-30"
                }
            ],
            "open source marketing": [
                {
                    "title": "Marketing Open Source Projects: A Complete Guide",
                    "url": "https://example.com/open-source-marketing-guide",
                    "content": "Comprehensive guide to marketing open source projects including branding, documentation, and community building.",
                    "score": 0.90,
                    "published_date": "2024-02-15"
                },
                {
                    "title": "The Role of Social Media in Open Source Success",
                    "url": "https://example.com/social-media-open-source",
                    "content": "How platforms like Twitter, LinkedIn, and Dev.to can help promote open source projects.",
                    "score": 0.82,
                    "published_date": "2024-03-05"
                }
            ]
        }
        
        # Generic mock answers
        self.mock_answers = [
            "Based on current trends, {query} is seeing significant growth with new tools and methodologies emerging.",
            "Research indicates that {query} has become increasingly important for modern marketing strategies.",
            "The latest developments in {query} show a shift towards more automated and data-driven approaches.",
            "Experts suggest that {query} will continue to evolve with advancements in AI and machine learning."
        ]
    
    async def execute(
        self, 
        query: str, 
        max_results: int = 5, 
        search_depth: str = "basic",
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a mock search"""
        start_time = datetime.now()
        self.call_count += 1
        
        # Simulate processing delay
        await self._simulate_delay()
        
        # Check for pre-defined mock results
        query_lower = query.lower()
        results = []
        
        for key, mock_results in self.mock_results_db.items():
            if key in query_lower:
                results.extend(mock_results[:max_results])
                break
        
        # If no pre-defined results, generate generic ones
        if not results:
            results = self._generate_generic_results(query, max_results)
        
        # Select a mock answer
        answer_template = random.choice(self.mock_answers)
        answer = answer_template.format(query=query)
        
        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds() * 1000
        self.total_duration += duration
        
        return {
            "query": query,
            "answer": answer,
            "total_results": len(results),
            "results": results[:max_results],
            "images": self._generate_mock_images(),
            "search_timestamp": datetime.now().isoformat(),
            "source": "mock",
            "cached": False,
            "note": "This is mock data for testing. Set TAVILY_API_KEY for real search results."
        }
    
    def _generate_generic_results(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Generate generic mock results"""
        results = []
        domains = ["example.com", "techblog.com", "marketinginsights.com", "devjournal.com"]
        
        for i in range(max_results):
            results.append({
                "title": f"Article about {query} - Part {i+1}",
                "url": f"https://{random.choice(domains)}/article-{i+1}",
                "content": f"This is a mock article about {query}. It discusses various aspects and provides insights into current trends and best practices.",
                "score": round(0.7 + random.random() * 0.3, 2),  # Random score between 0.7 and 1.0
                "published_date": (datetime.now() - timedelta(days=random.randint(1, 90))).strftime("%Y-%m-%d"),
                "rank": i + 1
            })
        
        return results
    
    def _generate_mock_images(self) -> List[Dict[str, str]]:
        """Generate mock image results"""
        images = [
            {
                "url": "https://example.com/images/marketing-trends.jpg",
                "title": "Marketing Trends Visualization",
                "source": "Example.com"
            },
            {
                "url": "https://example.com/images/data-analysis.png",
                "title": "Data Analysis Infographic",
                "source": "TechBlog.com"
            }
        ]
        return images[:2]  # Return max 2 images
    
    async def _simulate_delay(self, min_ms: int = 100, max_ms: int = 500):
        """Simulate network delay"""
        import asyncio
        delay_ms = random.randint(min_ms, max_ms)
        await asyncio.sleep(delay_ms / 1000.0)
    
    async def search_multiple(
        self, 
        queries: List[str], 
        max_results_per_query: int = 3
    ) -> Dict[str, Any]:
        """Execute multiple mock searches"""
        tasks = []
        for query in queries:
            task = self.execute(
                query=query,
                max_results=max_results_per_query
            )
            tasks.append(task)
        
        # Import here to avoid circular imports
        import asyncio
        results = await asyncio.gather(*tasks)
        
        combined_answer = " ".join([r.get("answer", "") for r in results])
        
        return {
            "queries": queries,
            "total_searches": len(queries),
            "successful_searches": len(queries),
            "failed_searches": 0,
            "all_results": [
                {
                    "query": queries[i],
                    "results": results[i].get("results", []),
                    "answer": results[i].get("answer", "")
                }
                for i in range(len(results))
            ],
            "combined_answer": combined_answer,
            "search_timestamp": datetime.now().isoformat(),
            "source": "mock",
            "note": "Mock data for testing purposes"
        }


# Factory function to create mock search tool
def create_mock_search_tool() -> MockSearchTool:
    """Create and return a mock search tool instance"""
    return MockSearchTool()