import requests
import sys
import os

# ==============================================================================
# 🛠️ OPEN WEBUI TOOL REGISTRATION SCRIPT (AUTO-CREATE USER & OLLAMA PROVIDER)
# ==============================================================================

# --- CONFIGURATION ---
BASE_URL = "http://localhost:8000"

# NEW: Define the Ollama Port here for easy adjustment
OLLAMA_PORT = 21434
OLLAMA_API_URL = f"http://localhost:{OLLAMA_PORT}"

# Credentials for the Admin Account to Create/Use
LOGIN_EMAIL = "alexander_foster@yahoo.com"
LOGIN_PASSWORD = "Cjr2SvQ@RQ@q8jU"
LOGIN_NAME = "Alexander Foster"

# Tool Metadata
TOOL_ID = "rag_retrieval_tool"
TOOL_NAME = "RAG_Retrieval_Tool"
TOOL_DESCRIPTION = "Retrieves information from local documents via the RAG API (Port 9000)."

# ---------------------

def get_auth_token():
    print("   🔐 Authenticating...")
    
    # 1. Attempt SIGN UP (Create Account)
    try:
        signup_payload = {
            "email": LOGIN_EMAIL,
            "password": LOGIN_PASSWORD,
            "name": LOGIN_NAME
        }
        resp = requests.post(f"{BASE_URL}/api/v1/auths/signup", json=signup_payload)
        
        if resp.status_code == 200:
            print("   ✅ Account created successfully!")
            return resp.json()["token"]
    except Exception:
        pass

    # 2. Attempt SIGN IN (Login)
    print("   User might exist. Trying login...")
    try:
        signin_payload = {"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD}
        resp = requests.post(f"{BASE_URL}/api/v1/auths/signin", json=signin_payload)
        
        if resp.status_code == 200:
            return resp.json()["token"]
        else:
            print(f"❌ Login Failed (Status {resp.status_code}).")
            return None
    except Exception:
        return None

def register_ollama_provider(headers):
    """Adds the Ollama service as a Model Provider to Open WebUI."""
    print("   🌐 Registering Ollama Provider...")
    
    provider_payload = {
        "provider_name": "ollama",
        "base_url": OLLAMA_API_URL, # Uses the new variable
        "api_key": ""
    }
    
    try:
        # Check if provider exists first
        resp = requests.get(f"{BASE_URL}/api/v1/model/providers", headers=headers)
        resp.raise_for_status()
        
        providers = [p for p in resp.json() if p['provider_name'] == 'ollama']
        
        if providers:
            print("   ⚠️ Ollama provider already configured. Skipping creation.")
            return

        # Attempt to CREATE the Ollama provider
        resp = requests.post(f"{BASE_URL}/api/v1/model/providers", json=provider_payload, headers=headers)
        
        if resp.status_code == 200:
            print("   ✅ Ollama Provider registered successfully!")
        else:
            print(f"   ❌ Failed to register Ollama provider (Status {resp.status_code}): {resp.text}")
            
    except Exception as e:
        print(f"   ❌ Connection error during Ollama setup: {e}")

def register_tool(tool_file_path):
    print(f"--- 🛠️ Registering Tool: {TOOL_NAME} ---")
    
    if not os.path.exists(tool_file_path):
        print(f"❌ Error: Tool file not found at: {tool_file_path}")
        sys.exit(1)
        
    with open(tool_file_path, "r") as f:
        tool_content = f.read()

    # Get Token (Auto-Create or Login)
    token = get_auth_token()
    if not token:
        print("❌ CRITICAL: Could not authenticate. Exiting.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    # 1. Register Ollama Provider (NEW AUTO-CONFIGURATION STEP)
    register_ollama_provider(headers)

    # 2. Register Custom Tool (Existing Logic)
    tool_payload = {
        "id": TOOL_ID,
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "content": tool_content,
        "meta": {"description": TOOL_DESCRIPTION, "manifest": {}},
        "access_control": None
    }
    
    try:
        print("   Pushing tool configuration...")
        resp = requests.post(f"{BASE_URL}/api/v1/tools/create", json=tool_payload, headers=headers)
        
        if resp.status_code == 200:
             print("   ✅ Tool CREATED successfully!")
        elif "already exists" in resp.text:
             print("   ⚠️ Tool exists. Updating...")
             update_resp = requests.post(f"{BASE_URL}/api/v1/tools/id/{TOOL_ID}/update", json=tool_payload, headers=headers)
             if update_resp.status_code == 200:
                 print("   ✅ Tool UPDATED successfully!")
             else:
                 print(f"❌ Update failed: {update_resp.text}")
        else:
             print(f"❌ Creation failed: {resp.text}")
             
    except Exception as e:
        print(f"❌ Connection error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 register_webui_tool.py <path_to_tool_file.py>")
        sys.exit(1)
    
    register_tool(sys.argv[1])