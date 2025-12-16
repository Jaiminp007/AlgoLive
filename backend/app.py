from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS
from pymongo import MongoClient
import os
import json
import threading
import time
import requests as http_requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

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
    socketio.emit('chart_history_response', list(arena.chart_history))

# Database Connection
mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/algoclash')
try:
    client = MongoClient(mongo_uri)
    db = client.get_default_database()
    print(f"Connected to MongoDB at {mongo_uri}")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    db = None

# Add root directory to sys.path to allow sibling imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyst_engine.brain import Brain
from market_simulation.arena import Arena

# Global State
arena = Arena(socketio, db)
brain = Brain()

# DEFERRED STARTUP: Deploy agents and start arena AFTER server is ready
def delayed_startup():
    """Run heavy initialization in background to not block healthcheck"""
    import time
    time.sleep(5)  # Wait for Flask to be ready
    
    import glob
    agent_files = glob.glob(os.path.join(arena.agent_dir, 'Agent_*.py'))
    print(f"Found {len(agent_files)} existing agents to auto-deploy...")
    
    for filepath in agent_files:
        agent_name = os.path.basename(filepath).replace('.py', '')
        if arena.load_agent(agent_name):
            print(f"  ✅ Auto-deployed: {agent_name}")
        else:
            print(f"  ❌ Failed to load: {agent_name}")
    
    if len(arena.agents) > 0:
        print(f"Starting arena with {len(arena.agents)} agents...")
        arena.start_loop()
    else:
        print("No agents loaded - waiting for manual deployment.")

# Start deferred initialization in background thread
startup_thread = threading.Thread(target=delayed_startup, daemon=True)
startup_thread.start()

@app.route('/available_models', methods=['GET'])
def get_available_models():
    try:
        # Use absolute path relative to this file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to root, then into analyst_engine
        json_path = os.path.join(os.path.dirname(base_dir), 'analyst_engine', 'ai_agents.json')
        print(f"DEBUG: Loading models from: {json_path}")
        print(f"DEBUG: File exists: {os.path.exists(json_path)}")
        
        with open(json_path, 'r') as f:
            models = json.load(f)
        print(f"DEBUG: Loaded {len(models)} provider groups")
        return jsonify(models)
    except Exception as e:
        import traceback
        print(f"Error reading ai_agents.json: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# PREVIOUSLY: arena.start_loop() was here. Now we wait for explicit start.


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
        
    success = arena.load_agent(name, reload_module=True)
    if success:
        # NOTE: Do NOT start arena here. Wait for explicit /start_arena call
        # after ALL agents are generated and deployed.
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

@app.route('/soft_reset_arena', methods=['POST'])
def soft_reset_arena():
    print("SOFT RESET INITIATED")
    arena.soft_reset()
    return jsonify({'status': 'arena_soft_reset'})

@app.route('/rebuild_algos', methods=['POST'])
def rebuild_algos():
    print("MANUAL REBUILD ALGOS INITIATED")
    # Run in background to avoid timeout
    t = threading.Thread(target=arena.force_evolution)
    t.start()
    return jsonify({'status': 'rebuild_initiated'})

@app.route('/clear_all_data', methods=['POST'])
def clear_all_data():
    """Clears all MongoDB data: agents, chart_history, trades, and agent files"""
    print("CLEARING ALL DATA...")
    try:
        # Stop arena if running
        arena.stop_loop()
        
        # Clear MongoDB collections
        db.agents.drop()
        db.chart_history.drop()
        db.trades.drop()
        
        # Clear in-memory state
        arena.agents.clear()
        arena.chart_history.clear()
        
        # Delete agent files
        import glob
        agent_files = glob.glob(os.path.join(arena.agent_dir, 'Agent_*.py'))
        for f in agent_files:
            os.remove(f)
            print(f"Deleted: {f}")
        
        print("ALL DATA CLEARED SUCCESSFULLY")
        return jsonify({'status': 'all_data_cleared'})
    except Exception as e:
        print(f"Error clearing data: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"Starting AlgoClash Live Backend on port {port}...")
    socketio.run(app, debug=False, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)

