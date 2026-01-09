#!/usr/bin/env python3
"""
Monitor agent trading results from Railway backend.
Run this to check how your agents are performing.
"""
import requests
import time
from datetime import datetime

BACKEND_URL = "https://algolive-production.up.railway.app"

def get_status():
    """Get current arena status"""
    r = requests.get(f"{BACKEND_URL}/status", timeout=30)
    return r.json()

def watch_live(interval=5, duration=60):
    """Watch live updates for a duration (seconds)"""
    print(f"Watching for {duration}s at {interval}s intervals...\n")
    start = time.time()
    
    while (time.time() - start) < duration:
        try:
            status = get_status()
            now = datetime.now().strftime("%H:%M:%S")
            
            print(f"[{now}] Arena: {'🟢 Running' if status.get('arena_running') else '🔴 Stopped'}")
            print(f"   Agents: {status.get('active_agents', [])}")
            print()
            
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(interval)

def main():
    print(f"📊 Checking {BACKEND_URL}...\n")
    
    try:
        status = get_status()
        print(f"Arena Running: {status.get('arena_running')}")
        print(f"Agent Count: {status.get('agent_count')}")
        print(f"Active Agents: {status.get('active_agents')}")
        
        if status.get('arena_running'):
            print("\n" + "="*50)
            watch_live(interval=10, duration=300)  # Watch for 5 minutes
            
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    main()
