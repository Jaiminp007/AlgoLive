from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime
import os
import json
import threading
import time
import requests as http_requests
from dotenv import load_dotenv

# Track server start time for uptime calculation
START_TIME = time.time()

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


# Database Connection - with short timeout for Railway (no MongoDB available)
mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/algoclash')
db = None

if os.getenv('MONGO_URI'):  # Only try to connect if explicitly configured
    try:
        import certifi
        print(f"Connecting to MongoDB: {mongo_uri[:20]}...")
        # OPTION 2 & 3 Combined: Robust SSL + Memory Fallback
        client = MongoClient(
            mongo_uri, 
            serverSelectionTimeoutMS=5000,
            tls=True,
            tlsAllowInvalidCertificates=True,
            directConnection=False,
            ssl_cert_reqs='CERT_NONE'
        )
        db = client.get_default_database()
        
        # Test connection
        client.admin.command('ping')
        print(f"✅ MongoDB connected at {mongo_uri[:20]}...")
    except Exception as e:
        print(f"⚠️ MongoDB unavailable: {e}")
        print("Running in MEMORY-ONLY mode")
        db = None
else:
    print("MONGO_URI not set - running without database (no persistence)")

# Add root directory to sys.path to allow sibling imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyst_engine.brain import Brain
from market_simulation.arena import Arena

# Agents to auto-load on start/reset
default_agents = [
    "Agent_10_github_openai_gpt_5",
    "Agent_11_github_openai_gpt_4o",
    "Agent_7_github_openai_gpt_5_",
    "Agent_qwen_3_max",
    "Agent_claude_opus_4_5",
    "Agent_claude_sonnet_4_5",
    "Agent_deepseek",
    "Agent_gemini_3_flash_quick",
    "Agent_gemini_3_flash_thinking",
    "Agent_gemini_3_pro",
    "Agent_glm_4_7",
    "Agent_grok_4_thinking",
    "Agent_kat_coder_pilot",
    "Agent_nvidia_nemotron",
    "Agent_open_ai_4o",
    "Agent_open_ai_5_2_thinking",
    "Agent_xiomi_mimo"
]

# Global State
arena = Arena(socketio, db)
brain = Brain() # Instantiate Brain

# DEFERRED STARTUP: Deploy agents and start arena AFTER server is ready
def delayed_startup():
    """Run heavy initialization in background to not block healthcheck"""
    try:
        import time
        import sys
        print("[STARTUP] Delayed startup beginning in 5 seconds...", flush=True)
        sys.stdout.flush()
        time.sleep(5)
        
        print(f"[STARTUP] Agent directory: {arena.agent_dir}", flush=True)
        
        import glob
        agent_files = glob.glob(os.path.join(arena.agent_dir, 'Agent_*.py'))
        print(f"[STARTUP] Found {len(agent_files)} agent files: {agent_files}", flush=True)
        
        for filepath in agent_files:
            agent_name = os.path.basename(filepath).replace('.py', '')
            try:
                if arena.load_agent(agent_name):
                    print(f"[STARTUP] ✅ Deployed: {agent_name}", flush=True)
                else:
                    print(f"[STARTUP] ❌ Failed: {agent_name}", flush=True)
            except Exception as e:
                print(f"[STARTUP] ❌ Error loading {agent_name}: {e}", flush=True)
        
        if len(arena.agents) > 0:
            print(f"[STARTUP] Starting arena with {len(arena.agents)} agents...", flush=True)
            arena.start_loop()
            print("[STARTUP] Arena started!", flush=True)
        else:
            print("[STARTUP] No agents loaded - waiting for manual deployment.", flush=True)
    except Exception as e:
        import traceback
        print(f"[STARTUP] FATAL ERROR: {e}", flush=True)
        traceback.print_exc()

# Start deferred initialization in background thread
print("[STARTUP] Creating startup thread...", flush=True)
startup_thread = threading.Thread(target=delayed_startup, daemon=True)
startup_thread.start()
print("[STARTUP] Startup thread started!", flush=True)

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

@app.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    """Returns a sorted leaderboard of all agents"""
    agents_list = []
    try:
        for name, agent in arena.agents.items():
            agents_list.append({
                'name': name,
                'equity': agent.get('equity', 100.0),
                'roi': agent.get('roi', 0.0),
                'cash': agent.get('cash', 100.0),
                'cashed_out': agent.get('cashed_out', 0.0),
                'total_fees': agent.get('total_fees', 0.0),
                'portfolio': agent.get('portfolio', {}),
                'last_decision': agent.get('last_decision', 'WAIT')
            })
        
        # Sort by ROI descending
        agents_list.sort(key=lambda x: x['roi'], reverse=True)
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'count': len(agents_list),
            'leaderboard': agents_list
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """
    Enhanced health check endpoint for Render keep-alive and monitoring.
    Returns detailed metrics about the service status.
    """
    try:
        # Calculate uptime
        uptime_seconds = time.time() - START_TIME
        uptime_hours = uptime_seconds / 3600

        # Get agent statistics
        active_agents = len(arena.agents)
        total_trades = 0
        total_equity = 0
        total_cashed_out = 0

        if active_agents > 0:
            for agent_name, agent_data in arena.agents.items():
                total_trades += agent_data.get('trades_count', 0)
                total_equity += agent_data.get('equity', 100.0)
                total_cashed_out += agent_data.get('cashed_out', 0.0)

        # Calculate average ROI
        avg_roi = 0
        if active_agents > 0:
            avg_roi = ((total_equity - (active_agents * 100)) / (active_agents * 100)) * 100

        response = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'uptime_seconds': round(uptime_seconds, 2),
            'uptime_hours': round(uptime_hours, 2),
            'service': 'AlgoClash Backend',
            'version': '2.0.0',
            'arena': {
                'running': arena.running,
                'tick_count': getattr(arena, 'tick_count', 0)
            },
            'agents': {
                'active': active_agents,
                'total_trades': total_trades,
                'total_equity': round(total_equity, 2),
                'total_cashed_out': round(total_cashed_out, 2),
                'avg_roi': round(avg_roi, 3)
            },
            'database': {
                'connected': db is not None
            },
            'environment': 'render' if os.getenv('RENDER') else 'local'
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/')
def root():
    """Root endpoint with API info"""
    return jsonify({
        'message': 'AlgoClash Live - AI Trading Arena',
        'status': 'running',
        'endpoints': {
            'health': '/health',
            'status': '/status',
            'generate_agent': '/generate_agent (POST)',
            'deploy_agent': '/deploy_agent (POST)',
            'available_models': '/available_models'
        }
    }), 200

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

