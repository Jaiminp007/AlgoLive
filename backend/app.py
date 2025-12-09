import eventlet
eventlet.monkey_patch()
from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS
from pymongo import MongoClient
import os
import threading
import time
import requests as http_requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Keep-alive ping for Render free tier
def keep_alive():
    """Pings the server every 10 minutes to prevent Render from sleeping"""
    render_url = os.getenv('RENDER_EXTERNAL_URL')
    if not render_url:
        print("RENDER_EXTERNAL_URL not set, keep-alive disabled")
        return
    
    while True:
        time.sleep(600)  # 10 minutes
        try:
            response = http_requests.get(f"{render_url}/health", timeout=30)
            print(f"Keep-alive ping: {response.status_code}")
        except Exception as e:
            print(f"Keep-alive ping failed: {e}")

# Start keep-alive thread
keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
keep_alive_thread.start()

@socketio.on('request_history')
def handle_request_history():
    print(f"Client requested history. Sending {len(arena.chart_history)} points.")
    socketio.emit('chart_history_response', arena.chart_history)

# Database Connection
mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/algoclash')
try:
    client = MongoClient(mongo_uri)
    db = client.get_default_database()
    print(f"Connected to MongoDB at {mongo_uri}")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    db = None

from brain import Brain
from arena import Arena

# ... (Previous imports kept) ...

# Global State
# Global State
arena = Arena(socketio, db) # Pass db if needed or None
brain = Brain()

# Auto-Deploy Default Agents
default_agents = [
    "Tongyi_DeepResearch_30b",
    "GPT_OSS_20B",
    "Gemini_2_5_Flash_Lite",
    # Custom Pre-Built Agents (Not AI-generated)
    "Conservative_Captain",   # EMA Trend Follower (Golden/Death Cross)
    "Aggressive_Scalper",     # RSI Mean Reversion (Oversold/Overbought)
    "Volatility_Hunter"       # Bollinger Bands Breakout Trader
]

# AUTO-GENERATE AGENTS ON STARTUP
print("--- 🧠 INITIALIZING AI AGENT GENERATION ---")

# Specific model mapping requested by user
AGENT_MODELS = {
    "Tongyi_DeepResearch_30b": "tngtech/tng-r1t-chimera:free",
    "GPT_OSS_20B": "openai/gpt-oss-20b:free",
    "Gemini_2_5_Flash_Lite": "google/gemini-2.5-flash-lite"
}

for agent_name in default_agents:
    # Check if agent file already exists
    agent_path = os.path.join("agents", f"{agent_name}.py")
    if os.path.exists(agent_path):
        print(f"Skipping generation for {agent_name} (File exists)")
        continue

    # Use specific model if defined, otherwise fallback to Gemini Flash
    target_model = AGENT_MODELS.get(agent_name, "google/gemini-2.5-flash-preview-09-2025")
    
    print(f"Generating strategy for {agent_name} using {target_model}...")
    try:
        gen_result = brain.generate_agent_code(agent_name, model=target_model)
        if "error" in gen_result:
            print(f"FAILED to generate {agent_name}: {gen_result['error']}")
        else:
            print(f"SUCCESS: Generated {agent_name} with {target_model}")
    except Exception as e:
        print(f"CRITICAL ERROR generating {agent_name}: {e}")

print("--- 🤖 DEPLOYING GENERATED AGENTS ---")
for agent_name in default_agents:
    if arena.load_agent(agent_name):
        print(f"Auto-deployed {agent_name}")
arena.start_loop()

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        'status': 'online',
        'arena_running': arena.running,
        'agent_count': len(arena.agents),
        'active_agents': list(arena.agents.keys())
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Render keep-alive"""
    return jsonify({'status': 'healthy', 'timestamp': time.time()})

@app.route('/generate_agent', methods=['POST'])
def generate_agent():
    data = request.json
    name = data.get('name', 'AgentX')
    model = data.get('model', 'openai/gpt-oss-20b:free')
    
    result = brain.generate_agent_code(name, model)
    if "error" in result:
        return jsonify(result), 500
    
    return jsonify(result)

@app.route('/deploy_agent', methods=['POST'])
def deploy_agent():
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Name required'}), 400
        
    success = arena.load_agent(name)
    if success:
        if not arena.running:
            arena.start_loop()
        return jsonify({'status': 'deployed', 'name': name})
    else:
        return jsonify({'error': 'Failed to load agent'}), 400

@app.route('/stop_agent', methods=['POST'])
def stop_agent():
    data = request.json
    name = data.get('name')
    if name in arena.agents:
        del arena.agents[name]
        return jsonify({'status': 'stopped', 'name': name})
    return jsonify({'error': 'Agent not found'}), 404

@app.route('/start_arena', methods=['POST'])
def start_arena():
    arena.start_loop()
    return jsonify({'status': 'arena_started'})

@app.route('/stop_arena', methods=['POST'])
def stop_arena():
    arena.stop_loop()
    return jsonify({'status': 'arena_stopped'})

@app.route('/reset_arena', methods=['POST'])
def reset_arena():
    print("HARD RESET INITIATED")
    # Pass the global default agents list to the arena reset
    arena.reset(default_agents)
    return jsonify({'status': 'arena_reset'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"Starting AlgoClash Live Backend on port {port}...")
    socketio.run(app, debug=False, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)

