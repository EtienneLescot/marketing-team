#!/usr/bin/env python3
"""
Test Tavily API directly.
"""

import os
import aiohttp
import asyncio
import json

async def test_tavily_api():
    """Test Tavily API directly"""
    api_key = os.getenv("TAVILY_API_KEY", "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")
    
    if not api_key:
        print("❌ No TAVILY_API_KEY found")
        return
    
    print(f"Testing Tavily API with key: {api_key[:10]}...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": "Python web frameworks 2024",
        "max_results": 3,
        "search_depth": "basic",
        "include_answer": True,
        "include_raw_content": False,
        "include_images": True
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.tavily.com/search",
                json=payload,
                headers=headers,
                timeout=30
            ) as response:
                print(f"Status code: {response.status}")
                print(f"Content-Type: {response.headers.get('Content-Type')}")
                
                # Get response as text
                response_text = await response.text()
                print(f"\nResponse length: {len(response_text)} characters")
                print(f"\nFirst 500 chars of response:")
                print(response_text[:500])
                
                # Try to parse as JSON
                try:
                    data = json.loads(response_text)
                    print(f"\n✅ Successfully parsed as JSON")
                    print(f"JSON type: {type(data)}")
                    if isinstance(data, dict):
                        print(f"Keys: {list(data.keys())}")
                        if 'error' in data:
                            print(f"Error in response: {data.get('error')}")
                except json.JSONDecodeError as e:
                    print(f"\n❌ Failed to parse as JSON: {e}")
                    
    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tavily_api())