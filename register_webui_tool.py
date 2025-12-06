import requests
import sys
import os

# ==============================================================================
# 🛠️ OPEN WEBUI TOOL REGISTRATION SCRIPT
# ==============================================================================
# This script automates the process of adding a custom Python tool to Open WebUI.
# 1. Logs in to get an authentication token.
# 2. Reads the Python tool code from a file.
# 3. Pushes the code to the Open WebUI Tools API.
# ==============================================================================

# --- CONFIGURATION ---

# Open WebUI URL (Internal)
BASE_URL = "http://localhost:8000"

# Admin Credentials (MUST MATCH YOUR OPEN WEBUI ADMIN ACCOUNT)
# You must create this account manually in the browser first if it doesn't exist.
LOGIN_EMAIL = "admin@example.com"
LOGIN_PASSWORD = "password123"

# Tool Metadata
TOOL_ID = "rag_retrieval_tool"  # Unique ID for the system
TOOL_NAME = "RAG_Retrieval_Tool" # Display Name in UI
TOOL_DESCRIPTION = "Retrieves information from local documents via the RAG API (Port 9000)."

# ---------------------

def register_tool(tool_file_path):
    print(f"--- 🛠️ Registering Tool: {TOOL_NAME} ---")
    
    # 1. VALIDATE INPUT
    if not os.path.exists(tool_file_path):
        print(f"❌ Error: Tool file not found at: {tool_file_path}")
        sys.exit(1)
        
    print(f"   Reading code from: {tool_file_path}")
    with open(tool_file_path, "r") as f:
        tool_content = f.read()

    # 2. AUTHENTICATE
    print("   Authenticating with Open WebUI...")
    try:
        auth_resp = requests.post(f"{BASE_URL}/api/v1/auths/signin", json={
            "email": LOGIN_EMAIL,
            "password": LOGIN_PASSWORD
        })
        auth_resp.raise_for_status()
        token = auth_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("   ✅ Login successful.")
    except Exception as e:
        print(f"❌ Authentication Failed: {e}")
        print("   (Ensure Open WebUI is running and admin credentials are correct)")
        sys.exit(1)

    # 3. REGISTER TOOL
    print("   Pushing tool configuration...")
    
    tool_payload = {
        "id": TOOL_ID,
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "content": tool_content,
        "meta": {
            "description": TOOL_DESCRIPTION,
            "manifest": {} 
        },
        "access_control": None
    }
    
    try:
        # Attempt to CREATE
        resp = requests.post(f"{BASE_URL}/api/v1/tools/create", json=tool_payload, headers=headers)
        
        if resp.status_code == 200:
             print("   ✅ Tool CREATED successfully!")
             
        elif resp.status_code == 400 and "already exists" in resp.text:
             # Attempt to UPDATE if it exists
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
    # Expects the tool filename as the first argument
    if len(sys.argv) < 2:
        print("Usage: python3 register_webui_tool.py <path_to_tool_file.py>")
        sys.exit(1)
    
    target_tool_file = sys.argv[1]
    register_tool(target_tool_file)