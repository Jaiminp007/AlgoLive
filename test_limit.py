import requests
import time

BACKEND_URL = "http://localhost:5000"

def deploy_agent(name):
    # Use existing Agent_1 code but deploy with new name
    # Note: We must ensure the agent file exists or we generate it.
    # To save time, we will 'generate' them but really they use the same prompts.
    print(f"Generating {name}...")
    try:
        r = requests.post(f"{BACKEND_URL}/generate_agent", 
                         json={"name": name, "model": "openai/gpt-4o"}, 
                         timeout=120)
        print(f"Gen status: {r.status_code}")
    except Exception as e:
        print(f"Gen error: {e}")

    print(f"Deploying {name}...")
    try:
        r = requests.post(f"{BACKEND_URL}/deploy_agent", 
                         json={"name": name}, 
                         timeout=30)
        print(r.json())
    except Exception as e:
        print(f"Deploy error: {e}")

def main():
    print("Testing 7 Agent Limit...")
    for i in range(1, 8):
        deploy_agent(f"Agent_LimitTest_{i}")
        time.sleep(1)
        
    print("Starting Arena...")
    requests.post(f"{BACKEND_URL}/start_arena")

if __name__ == "__main__":
    main()
