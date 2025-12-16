#!/usr/bin/env python3
"""
LinkedIn posting tool implementation.
"""

import os
import requests
import json
from typing import Dict, Any, Optional
from datetime import datetime

from app.tools.tool_registry import BaseTool, ToolMetadata
from app.models.state_models import APIError

class LinkedInPostTool(BaseTool):
    """Tool for posting content to LinkedIn"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="linkedin_post",
            description="Post content to LinkedIn personal profile or page",
            category="social_media",
            cost_per_call=0.0,
            rate_limit=10, # Conservative limit
            requires_auth=True,
            auth_env_var="LINKEDIN_ACCESS_TOKEN"
        )
        super().__init__(metadata)
        self.access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        self.user_urn = os.getenv("LINKEDIN_USER_URN")
    
    async def execute(self, content: str, **kwargs) -> str:
        """Execute the LinkedIn post"""
        self.call_count += 1
        start_time = datetime.now()
        
        # Validation
        if not self.access_token or not self.user_urn:
            self.error_count += 1
            raise APIError(
                message="Missing LinkedIn credentials (LINKEDIN_ACCESS_TOKEN or LINKEDIN_USER_URN)",
                component="LinkedInPostTool",
                operation="execute",
                suggested_action="Run scripts/get_linkedin_token.py to generate credentials",
                retryable=False
            )
            
        try:
            post_url = "https://api.linkedin.com/v2/ugcPosts"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            }
            
            payload = {
                "author": self.user_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": content
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            
            # Synchronous request in async method (should ideally be async, but okay for low volume)
            response = requests.post(post_url, headers=headers, json=payload, timeout=30)
            
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self.total_duration += duration
            
            if response.status_code in [200, 201]:
                post_id = response.json().get('id', 'unknown')
                feed_url = f"https://www.linkedin.com/feed/update/{post_id}"
                return f"✅ Successfully published to LinkedIn! View post: {feed_url}"
            else:
                self.error_count += 1
                raise APIError(
                    message=f"LinkedIn API Error: {response.status_code} - {response.text}",
                    component="LinkedInPostTool",
                    operation="execute",
                    context={"status_code": response.status_code, "response": response.text},
                    retryable=True
                )
                
        except Exception as e:
            self.error_count += 1
            if isinstance(e, APIError):
                raise e
            raise APIError(
                message=f"Unexpected error posting to LinkedIn: {str(e)}",
                component="LinkedInPostTool",
                operation="execute",
                original_exception=e,
                retryable=True
            )

def create_linkedin_tool() -> LinkedInPostTool:
    return LinkedInPostTool()
