import os
import sys
import webbrowser
import requests
import uvicorn
from fastapi import FastAPI, Request
from dotenv import load_dotenv, set_key
from pathlib import Path
import threading
import asyncio

# Load existing .env
env_path = Path(".env")
load_dotenv(env_path)

CLIENT_ID = os.getenv("LINKED_IN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKED_IN_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/callback"

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ Error: LINKED_IN_CLIENT_ID or LINKED_IN_CLIENT_SECRET not found in .env")
    sys.exit(1)

app = FastAPI()
server_shutdown_event = asyncio.Event()

@app.get("/callback")
async def callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return {"error": "No code provided"}
    
    print(f"\n✅ Authorization Code captured: {code[:10]}...")
    
    # Exchange code for access token
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    print("🔄 Exchanging code for access token...")
    response = requests.post(token_url, data=payload, headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Failed to get access token: {response.text}")
        return {"error": "Failed to get token", "details": response.json()}
    
    access_token = response.json().get("access_token")
    print(f"✅ Access Token retrieved: {access_token[:10]}...")
    
    # Parse ID Token to get User URN
    id_token = response.json().get("id_token")
    if id_token:
        print("✅ ID Token retrieved.")
        import base64
        import json
        
        # Decode the payload (2nd part of JWT)
        try:
            payload_part = id_token.split('.')[1]
            # Add padding if needed
            payload_part += '=' * (-len(payload_part) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_part))
            user_sub = payload.get('sub')
            user_urn = f"urn:li:person:{user_sub}"
            print(f"✅ User URN extracted from ID Token: {user_urn}")
        except Exception as e:
            print(f"❌ Failed to decode ID Token: {e}")
            return {"error": "Failed to decode ID Token", "details": str(e)}
    else:
        # Fallback to userinfo if no ID Token (though openid scope should ensure it)
        print("⚠️  No ID Token found, trying userinfo endpoint...")
        profile_url = "https://api.linkedin.com/v2/userinfo"
        profile_headers = {"Authorization": f"Bearer {access_token}"}
        profile_response = requests.get(profile_url, headers=profile_headers)
        
        if profile_response.status_code != 200:
            print(f"❌ Failed to get profile: {profile_response.text}")
            return {"error": "Failed to get profile", "details": profile_response.json()}
        
        data = profile_response.json()
        user_urn = f"urn:li:person:{data.get('sub')}"
        print(f"✅ User URN retrieved from API: {user_urn}")
    
    # Update .env
    print("💾 Saving to .env...")
    set_key(env_path, "LINKEDIN_ACCESS_TOKEN", access_token)
    set_key(env_path, "LINKEDIN_USER_URN", user_urn)
    
    print("\n✨ Success! LINKEDIN_ACCESS_TOKEN and LINKEDIN_USER_URN have been saved to .env")
    print("⚠️  You can now close this script and the browser tab.")
    
    # Signal shutdown
    server_shutdown_event.set()
    
    return {"message": "Success! You can close this tab and the script."}

def run_server():
    config = uvicorn.Config(app, host="localhost", port=8000, log_level="error")
    server = uvicorn.Server(config)
    
    # Override simple loop for threading
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def serve():
        # Start server task
        server_task = loop.create_task(server.serve())
        # Wait for shutdown event
        await server_shutdown_event.wait()
        # Create a task to shut down the server
        server.should_exit = True
        await server_task

    loop.run_until_complete(serve())

if __name__ == "__main__":
    print("🚀 Starting LinkedIn OAuth Token Generator")
    print(f"Using Client ID: {CLIENT_ID[:5]}...***")
    
    # Generate Auth URL
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        "response_type=code&"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        "state=random_state_string&"
        "scope=openid%20profile%20w_member_social%20email"
    )
    
    print(f"\n👉 Please open this URL in your browser:\n{auth_url}\n")
    
    # Try opening browser
    try:
        webbrowser.open(auth_url)
    except:
        pass
        
    print("Waiting for callback on http://localhost:8000/callback...")
    run_server()
