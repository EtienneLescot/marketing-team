"""
Mock LinkedIn posting tool for testing without actual LinkedIn API credentials.
This tool simulates the LinkedIn posting process and can be used for development and testing.
"""
import asyncio
import random
from datetime import datetime
from typing import Optional
from app.tools.tool_registry import BaseTool, ToolMetadata
from app.models.state_models import APIError


class MockLinkedInPostTool(BaseTool):
    """Mock LinkedIn posting tool for testing."""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="mock_linkedin_post",
            description="Post content to LinkedIn (mock version for testing). Simulates the posting process without actual API calls.",
            category="social_media",
            cost_per_call=0.0,
            rate_limit=100,  # High limit for testing
            requires_auth=False
        )
        super().__init__(metadata)
        self.success_rate = 0.95  # 95% success rate for testing
        self.mock_post_ids = []
        
    async def execute(self, content: str, **kwargs) -> str:
        """
        Mock execution of LinkedIn posting.
        
        Args:
            content: The content to post
            **kwargs: Additional parameters (company_urn, etc.)
            
        Returns:
            Success message with mock post ID
        """
        print(f"DEBUG MockLinkedInPostTool: Starting mock LinkedIn post")
        print(f"DEBUG MockLinkedInPostTool: Content length: {len(content)}")
        
        # Determine posting target (company or personal)
        target_urn = kwargs.get('company_urn', "urn:li:organization:110163013")
        is_company_post = bool(target_urn)
        print(f"DEBUG MockLinkedInPostTool: target_urn={target_urn}, is_company_post={is_company_post}")
        
        # Simulate API call delay
        await asyncio.sleep(random.uniform(0.5, 2.0))
        
        # Randomly fail to test error handling
        if random.random() > self.success_rate:
            error_msg = "Mock LinkedIn API Error: 403 - ACCESS_DENIED (simulated error for testing)"
            print(f"DEBUG MockLinkedInPostTool: Simulating API error: {error_msg}")
            raise APIError(
                message=error_msg,
                component="MockLinkedInPostTool",
                operation="execute",
                context={"mock_error": True},
                retryable=True
            )
        
        # Generate mock post ID
        mock_id = f"urn:li:ugcPost:{int(datetime.now().timestamp())}{random.randint(1000, 9999)}"
        self.mock_post_ids.append(mock_id)
        
        post_type = "company page" if is_company_post else "personal profile"
        
        result = f"✅ [MOCK] Successfully published to LinkedIn {post_type}! Mock post ID: {mock_id}"
        result += f"\n\nContent preview: {content[:100]}..."
        result += f"\n\nNote: This is a mock post. No actual LinkedIn API call was made."
        
        print(f"DEBUG MockLinkedInPostTool: Mock success: {result}")
        return result


def create_mock_linkedin_tool() -> MockLinkedInPostTool:
    return MockLinkedInPostTool()