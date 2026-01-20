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
from analyst_engine.sandbox_agent import SandboxAgent, get_sandbox_agent
from market_simulation.arena import Arena

# Agents to auto-load on start/reset
default_agents = [
    "Agent_momentum_breakout",
    "Agent_mean_reversion",
    "Agent_orderflow_alpha",
    "Agent_volatility_regime",
    "Agent_sentiment_momentum",
    "Agent_multitimeframe_trend"
]

# Global State
arena = Arena(socketio, db)
brain = Brain() # Instantiate Brain
sandbox_agent = get_sandbox_agent(socketio)  # Sandbox research agent

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

@app.route('/agent_code/<name>', methods=['GET'])
def get_agent_code(name):
    """Returns the source code for a specific agent"""
    try:
        # Sanitize name to prevent path traversal
        safe_name = name.replace('..', '').replace('/', '').replace('\\', '')
        filepath = os.path.join(arena.agent_dir, f'{safe_name}.py')

        if not os.path.exists(filepath):
            return jsonify({'error': 'Agent not found'}), 404

        with open(filepath, 'r') as f:
            code = f.read()

        return jsonify({
            'name': safe_name,
            'code': code,
            'filepath': filepath
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
                total_equity += agent_data.get('equity', 10000.0)
                total_cashed_out += agent_data.get('cashed_out', 0.0)

        # Calculate average ROI (starting balance is $10,000 per agent)
        avg_roi = 0
        STARTING_BALANCE = 10000
        if active_agents > 0:
            avg_roi = ((total_equity - (active_agents * STARTING_BALANCE)) / (active_agents * STARTING_BALANCE)) * 100

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
    
    # NEW: Persist code to DB
    if "code" in result:
        arena.save_agent_code(name, result["code"])
    
    return jsonify(result)

@app.route('/deploy_agent', methods=['POST'])
def deploy_agent():
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Name required'}), 400
        
    success = arena.load_agent(name, reload_module=True)
    if success:
        # NEW: Ensure code is in DB (for migration/manual uploads)
        try:
            filepath = os.path.join(arena.agent_dir, f"{name}.py")
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    code = f.read()
                arena.save_agent_code(name, code)
        except Exception as e:
            print(f"Error syncing {name} code to DB: {e}")

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
        # Also delete the agent file
        agent_file = os.path.join(arena.agent_dir, f"{name}.py")
        if os.path.exists(agent_file):
            try:
                os.remove(agent_file)
                print(f"Deleted agent file: {agent_file}")
            except Exception as e:
                print(f"Failed to delete agent file {agent_file}: {e}")
        # Remove from database as well
        if arena.db is not None:
            try:
                arena.db.agents.delete_one({'name': name})
            except Exception as e:
                print(f"Failed to remove agent from DB: {e}")
        return jsonify({'status': 'stopped', 'name': name, 'file_deleted': True})
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


# ==================== SANDBOX RESEARCH AGENT ENDPOINTS ====================

@app.route('/sandbox/create', methods=['POST'])
def create_sandbox_session():
    """
    Create a new sandbox research session.

    Request JSON:
        { "model": "github:openai/gpt-4o" }

    Response:
        { "session_id": "uuid", "status": "created", "model": "..." }
    """
    data = request.json or {}
    model = data.get('model', 'openai/gpt-4-turbo')

    result = sandbox_agent.create_session(model)

    if "error" in result:
        return jsonify(result), 500

    return jsonify(result)


@app.route('/sandbox/message', methods=['POST'])
def send_sandbox_message():
    """
    Send a message to the sandbox agent (multi-turn chat).

    Request JSON:
        { "session_id": "uuid", "message": "Explore insider trading patterns" }

    Response:
        {
            "response": "I'll analyze insider trading data...",
            "code_blocks": [{ "code": "...", "result": "...", "error": null }],
            "is_final": false,
            "final_code": null
        }
    """
    data = request.json or {}
    session_id = data.get('session_id')
    message = data.get('message')

    if not session_id:
        return jsonify({'error': 'session_id is required'}), 400
    if not message:
        return jsonify({'error': 'message is required'}), 400

    # Process message (this may take a while due to LLM + code execution)
    print(f"[SANDBOX] Processing message for session {session_id}: {message[:50]}...")
    result = sandbox_agent.process_message(session_id, message)

    if "error" in result:
        print(f"[SANDBOX] Error in process_message: {result['error']}")
        return jsonify(result), 400

    print(f"[SANDBOX] Message processed successfully")

    return jsonify(result)


@app.route('/sandbox/execute', methods=['POST'])
def execute_sandbox_code():
    """
    Manually execute code in sandbox (user override).

    Request JSON:
        { "session_id": "uuid", "code": "print('Hello')" }

    Response:
        { "result": "Hello", "error": null }
    """
    data = request.json or {}
    session_id = data.get('session_id')
    code = data.get('code')

    if not session_id:
        return jsonify({'error': 'session_id is required'}), 400
    if not code:
        return jsonify({'error': 'code is required'}), 400

    result = sandbox_agent.execute_code(session_id, code)

    if "error" in result and result.get("error") == "Session not found":
        return jsonify(result), 404

    return jsonify(result)


@app.route('/sandbox/finalize', methods=['POST'])
def finalize_sandbox_agent():
    """
    Extract final strategy from session and deploy to arena.

    Request JSON:
        { "session_id": "uuid", "agent_name": "Agent_sandbox_insider_001", "code": "optional fallback code" }

    Response:
        {
            "success": true,
            "agent_name": "Agent_sandbox_insider_001",
            "filepath": "/path/to/agent.py",
            "validation": { "syntax_valid": true, ... }
        }
    """
    data = request.json or {}
    session_id = data.get('session_id')
    agent_name = data.get('agent_name')
    code_override = data.get('code')  # Optional fallback code from frontend

    if not session_id:
        return jsonify({'error': 'session_id is required'}), 400
    if not agent_name:
        return jsonify({'error': 'agent_name is required'}), 400

    result = sandbox_agent.finalize_strategy(session_id, agent_name, code_override)

    if "error" in result:
        status_code = 404 if "not found" in result.get("error", "").lower() else 400
        return jsonify(result), status_code

    return jsonify(result)


@app.route('/sandbox/status/<session_id>', methods=['GET'])
def get_sandbox_status(session_id):
    """
    Get session status and metadata.

    Response:
        {
            "session_id": "uuid",
            "status": "active",
            "model": "...",
            "message_count": 5,
            "has_final_strategy": false
        }
    """
    result = sandbox_agent.get_session_status(session_id)

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result)


@app.route('/sandbox/history/<session_id>', methods=['GET'])
def get_sandbox_history(session_id):
    """
    Get full message and execution history for a session.

    Response:
        {
            "session_id": "uuid",
            "messages": [...],
            "executions": [...],
            "final_code": "..."
        }
    """
    result = sandbox_agent.get_session_history(session_id)

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result)


@app.route('/sandbox/close', methods=['POST'])
def close_sandbox_session():
    """
    Close session and cleanup sandbox resources.

    Request JSON:
        { "session_id": "uuid" }

    Response:
        { "success": true, "session_id": "uuid" }
    """
    data = request.json or {}
    session_id = data.get('session_id')

    if not session_id:
        return jsonify({'error': 'session_id is required'}), 400

    result = sandbox_agent.close_session(session_id)

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result)


# Socket.IO events for sandbox
@socketio.on('sandbox_subscribe')
def handle_sandbox_subscribe(data):
    """Subscribe to sandbox session for real-time updates."""
    from flask_socketio import join_room
    session_id = data.get('session_id')
    if session_id:
        join_room(f"sandbox_{session_id}")
        print(f"Client subscribed to sandbox session: {session_id}")


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"Starting AlgoClash Live Backend on port {port}...")
    socketio.run(app, debug=False, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)

