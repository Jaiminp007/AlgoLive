#!/usr/bin/env python3
"""
Deploy agents to Railway backend and start trading.
Run this locally to control the remote Railway backend.
"""
import requests
import time

BACKEND_URL = "http://localhost:5000"

# Agents to deploy - customize models as needed
AGENTS = [
    {"name": "Agent_1_gpt4o", "model": "openai/gpt-4o"},
    {"name": "Agent_2_mistral", "model": "mistralai/mistral-large-latest"},
    {"name": "Agent_3_claude", "model": "anthropic/claude-3-5-sonnet"},
]

def check_status():
    """Check backend status"""
    try:
        r = requests.get(f"{BACKEND_URL}/status", timeout=30)
        return r.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

def generate_agent(name, model):
    """Generate agent code via AI"""
    print(f"Generating {name} with {model}...")
    try:
        r = requests.post(f"{BACKEND_URL}/generate_agent", 
                         json={"name": name, "model": model}, 
                         timeout=120)
        return r.json()
    except Exception as e:
        print(f"Error generating {name}: {e}")
        return {"error": str(e)}

def deploy_agent(name):
    """Deploy a generated agent to the arena"""
    print(f"Deploying {name}...")
    try:
        r = requests.post(f"{BACKEND_URL}/deploy_agent", 
                         json={"name": name}, 
                         timeout=30)
        return r.json()
    except Exception as e:
        print(f"Error deploying {name}: {e}")
        return {"error": str(e)}

def start_arena():
    """Start the trading arena"""
    print("Starting arena...")
    try:
        r = requests.post(f"{BACKEND_URL}/start_arena", timeout=30)
        return r.json()
    except Exception as e:
        print(f"Error starting arena: {e}")
        return {"error": str(e)}

def main():
    # Check connection
    print(f"Connecting to {BACKEND_URL}...")
    status = check_status()
    if not status:
        print("Failed to connect to backend!")
        return
    
    print(f"Backend status: {status}")
    
    # Generate and deploy agents
    for agent in AGENTS:
        result = generate_agent(agent["name"], agent["model"])
        if "error" not in result:
            print(f"  ✅ Generated: {agent['name']}")
            deploy_result = deploy_agent(agent["name"])
            print(f"  ✅ Deployed: {deploy_result}")
        else:
            print(f"  ❌ Failed: {result}")
        time.sleep(2)  # Rate limiting
    
    # Start trading
    arena_result = start_arena()
    print(f"\n🚀 Arena started: {arena_result}")
    
    # Final status
    time.sleep(3)
    final_status = check_status()
    print(f"\n📊 Final Status:")
    print(f"   Arena Running: {final_status.get('arena_running')}")
    print(f"   Active Agents: {final_status.get('active_agents')}")

if __name__ == "__main__":
    main()
