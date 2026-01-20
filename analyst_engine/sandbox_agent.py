"""
Sandbox Quant Research Agent

Provides a multi-turn chat system where an LLM agent can explore the
FinancialDatasets.ai API, execute Python code in an E2B cloud sandbox,
analyze results, and produce a deployable trading strategy.
"""

import os
import re
import ast
import time
import uuid
import json
import requests
import threading
from typing import Dict, List, Optional, Tuple, Callable

# Load environment variables from .env file
# Try multiple locations: current dir, parent dir (AlgoLive), and backend dir
from dotenv import load_dotenv
import pathlib

# Get the directory of this file
_this_dir = pathlib.Path(__file__).parent
_root_dir = _this_dir.parent  # AlgoLive directory
_backend_dir = _root_dir / "backend"

# Try loading from multiple locations
load_dotenv(_backend_dir / ".env")  # backend/.env
load_dotenv(_root_dir / ".env")     # AlgoLive/.env
load_dotenv()                        # Current working directory

# E2B Code Interpreter SDK
try:
    from e2b_code_interpreter import Sandbox
    E2B_AVAILABLE = True
except ImportError:
    E2B_AVAILABLE = False
    print("Warning: e2b-code-interpreter not installed. Sandbox features disabled.")

# GitHub AI Inference SDK
try:
    from azure.ai.inference import ChatCompletionsClient
    from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
    from azure.core.credentials import AzureKeyCredential
    GITHUB_AI_AVAILABLE = True
except ImportError:
    GITHUB_AI_AVAILABLE = False


class SandboxSession:
    """Manages E2B sandbox lifecycle and execution history for a single session."""

    def __init__(self, session_id: str, model: str):
        self.session_id = session_id
        self.model = model
        self.sandbox: Optional[Sandbox] = None
        self.created_at = time.time()
        self.last_activity = time.time()
        self.message_history: List[Dict] = []
        self.execution_history: List[Dict] = []
        self.final_code: Optional[str] = None
        self.status = "created"  # created, active, completed, expired, error

    def create_sandbox(self) -> bool:
        """Initialize E2B sandbox with required packages."""
        if not E2B_AVAILABLE:
            print("SandboxSession: E2B not available")
            return False

        # Get E2B API key from environment
        e2b_api_key = os.getenv('E2B_API_KEY')
        if not e2b_api_key:
            print("SandboxSession: E2B_API_KEY not set in environment")
            return False

        try:
            # Create sandbox with API key explicitly passed
            self.sandbox = Sandbox(
                api_key=e2b_api_key,
                timeout=300,  # 5 minute sandbox lifetime
            )

            # Install required packages
            print(f"SandboxSession {self.session_id}: Installing packages...")
            install_result = self.sandbox.run_code("""
import subprocess
import sys

# Install packages silently
packages = ['pandas', 'numpy', 'scipy', 'requests', 'matplotlib']
for pkg in packages:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg],
                   capture_output=True)

# Set up API access
import os
print("Packages installed successfully")
""")

            if install_result and install_result.error:
                print(f"SandboxSession: Package install error: {install_result.error}")

            # Set up environment in the sandbox
            api_key = os.getenv('FINANCIAL_DATASETS_API_KEY', '')
            setup_result = self.sandbox.run_code(f"""
import os
os.environ['FINANCIAL_DATASETS_API_KEY'] = '{api_key}'
os.environ['BASE_URL'] = 'https://api.financialdatasets.ai'
print("Environment configured")
""")

            self.status = "active"
            print(f"SandboxSession {self.session_id}: Sandbox created successfully")
            return True

        except Exception as e:
            print(f"SandboxSession: Failed to create sandbox: {e}")
            self.status = "error"
            return False

    def execute_code(self, code: str, timeout: int = 60) -> Dict:
        """
        Execute code in sandbox with timeout.

        Returns:
            Dict with 'result', 'error', 'logs' keys
        """
        if not self.sandbox:
            return {"result": None, "error": "Sandbox not initialized", "logs": []}

        self.last_activity = time.time()

        try:
            execution = self.sandbox.run_code(code, timeout=timeout)

            result = {
                "result": execution.text if execution else None,
                "error": str(execution.error) if execution and execution.error else None,
                "logs": execution.logs if execution and hasattr(execution, 'logs') else [],
                "timestamp": time.time()
            }

            self.execution_history.append({
                "code": code,
                **result
            })

            return result

        except Exception as e:
            error_result = {
                "result": None,
                "error": str(e),
                "logs": [],
                "timestamp": time.time()
            }
            self.execution_history.append({
                "code": code,
                **error_result
            })
            return error_result

    def close(self):
        """Clean up sandbox resources."""
        if self.sandbox:
            try:
                self.sandbox.kill()
                print(f"SandboxSession {self.session_id}: Sandbox closed")
            except Exception as e:
                print(f"SandboxSession {self.session_id}: Error closing sandbox: {e}")
            finally:
                self.sandbox = None
        self.status = "completed"

    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired due to inactivity."""
        return (time.time() - self.last_activity) > (timeout_minutes * 60)

    def to_dict(self) -> Dict:
        """Serialize session state for API response."""
        return {
            "session_id": self.session_id,
            "model": self.model,
            "status": self.status,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "message_count": len(self.message_history),
            "execution_count": len(self.execution_history),
            "has_final_strategy": self.final_code is not None
        }


class SandboxAgent:
    """
    Manages multi-turn research conversation with LLM and code execution.

    This agent allows users to have a conversation with an LLM that can
    explore financial data, write and execute Python code, and ultimately
    produce a trading strategy.
    """

    def __init__(self, socketio=None):
        self.sessions: Dict[str, SandboxSession] = {}
        self.socketio = socketio

        # OpenRouter config
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

        # GitHub AI config
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_endpoint = "https://models.github.ai/inference"

        # Load system prompt
        self.system_prompt = self._load_system_prompt()

        # Start cleanup thread
        self._start_cleanup_thread()

    def _load_system_prompt(self) -> str:
        """Load system prompt from SANDBOX_AGENT_PROMPT.md."""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            prompt_file = os.path.join(base_dir, "SANDBOX_AGENT_PROMPT.md")

            if os.path.exists(prompt_file):
                with open(prompt_file, 'r') as f:
                    return f.read()
            else:
                print("SandboxAgent: SANDBOX_AGENT_PROMPT.md not found, using default")
                return self._get_default_system_prompt()
        except Exception as e:
            print(f"SandboxAgent: Error loading system prompt: {e}")
            return self._get_default_system_prompt()

    def _get_default_system_prompt(self) -> str:
        """Fallback system prompt if file not found."""
        return """You are a Quantitative Research Agent for the AlgoClash trading platform.
Your goal is to analyze financial data, discover trading signals, and create profitable trading algorithms.

You have access to a Python sandbox where you can:
1. Write and execute Python code
2. Make HTTP requests to the FinancialDatasets.ai API
3. Analyze data with pandas, numpy, scipy

Create a trading algorithm with the function signature:
def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    # Your strategy here
    return ("HOLD", None, 0)  # or ("BUY"/"SELL", symbol, quantity)
"""

    def _start_cleanup_thread(self):
        """Start background thread to clean up expired sessions."""
        def cleanup_loop():
            while True:
                time.sleep(300)  # Check every 5 minutes
                self._cleanup_expired_sessions()

        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()

    def _cleanup_expired_sessions(self):
        """Close and remove expired sessions."""
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired()
        ]
        for sid in expired:
            print(f"SandboxAgent: Cleaning up expired session {sid}")
            self.close_session(sid)

    def create_session(self, model: str) -> Dict:
        """
        Create a new sandbox research session.

        Args:
            model: LLM model to use (e.g., 'github:openai/gpt-4o')

        Returns:
            Dict with session_id and status
        """
        if not E2B_AVAILABLE:
            return {"error": "E2B sandbox not available. Install with: pip install e2b-code-interpreter"}

        session_id = str(uuid.uuid4())
        session = SandboxSession(session_id, model)

        # Initialize sandbox
        if not session.create_sandbox():
            return {"error": "Failed to create sandbox"}

        # Add system prompt to message history
        session.message_history.append({
            "role": "system",
            "content": self.system_prompt
        })

        self.sessions[session_id] = session
        print(f"[SandboxAgent] Session created: {session_id} with model: {model}")
        print(f"[SandboxAgent] Total active sessions: {len(self.sessions)}")

        return {
            "session_id": session_id,
            "status": "created",
            "model": model
        }

    def process_message(self, session_id: str, user_message: str,
                       on_stream: Optional[Callable] = None) -> Dict:
        """
        Process a user message: call LLM, execute code, return results.

        Args:
            session_id: Session identifier
            user_message: User's message
            on_stream: Optional callback for streaming updates

        Returns:
            Dict with response, code_blocks, is_final, final_code
        """
        print(f"[SandboxAgent] process_message called for session: {session_id}")
        session = self.sessions.get(session_id)
        if not session:
            print(f"[SandboxAgent] Session not found: {session_id}")
            print(f"[SandboxAgent] Available sessions: {list(self.sessions.keys())}")
            return {"error": "Session not found"}

        if session.status != "active":
            return {"error": f"Session is not active (status: {session.status})"}

        # Add user message to history
        session.message_history.append({
            "role": "user",
            "content": user_message
        })

        # Call LLM
        try:
            response_content = self._call_llm(session)
        except Exception as e:
            return {"error": f"LLM call failed: {str(e)}"}

        # Parse structured sections (thinking, api_calls, analysis)
        parsed = self._parse_structured_response(response_content)

        # Extract code blocks from response
        code_blocks = self._extract_code_blocks(response_content)
        executed_blocks = []

        # Execute each code block
        for code in code_blocks:
            if on_stream:
                on_stream("executing", {"code": code[:100] + "..."})

            result = session.execute_code(code)
            executed_blocks.append({
                "code": code,
                "result": result.get("result"),
                "error": result.get("error")
            })

            # Emit via Socket.IO if available
            if self.socketio:
                self.socketio.emit('sandbox_execution', {
                    "session_id": session_id,
                    "code": code,
                    "result": result.get("result"),
                    "error": result.get("error")
                })

            if on_stream:
                on_stream("executed", result)

        # If there were executed blocks, add results context to the conversation
        if executed_blocks:
            results_summary = self._format_execution_results(executed_blocks)
            # Add execution results as a system message for context
            session.message_history.append({
                "role": "assistant",
                "content": response_content
            })
            session.message_history.append({
                "role": "user",
                "content": f"[Code Execution Results]\n{results_summary}\n\nContinue your analysis based on these results."
            })
        else:
            # No code to execute, just add assistant response
            session.message_history.append({
                "role": "assistant",
                "content": response_content
            })

        # Check if response contains final execute_strategy function
        is_final, final_code = self._check_for_final_strategy(response_content)
        if is_final:
            session.final_code = final_code

        return {
            "response": parsed["clean_response"],
            "thinking": parsed["thinking"],
            "api_calls": parsed["api_calls"],
            "analysis": parsed["analysis"],
            "code_blocks": executed_blocks,
            "is_final": is_final,
            "final_code": final_code
        }

    def execute_code(self, session_id: str, code: str) -> Dict:
        """
        Manually execute code in sandbox (user override).

        Args:
            session_id: Session identifier
            code: Python code to execute

        Returns:
            Dict with result and error
        """
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        result = session.execute_code(code)

        # Emit via Socket.IO if available
        if self.socketio:
            self.socketio.emit('sandbox_execution', {
                "session_id": session_id,
                "code": code,
                "result": result.get("result"),
                "error": result.get("error")
            })

        return result

    def finalize_strategy(self, session_id: str, agent_name: str, code_override: str = None) -> Dict:
        """
        Extract final strategy, validate (static + runtime), and save.
        Includes auto-repair loop: if validation fails, asks LLM to fix it.
        """
        session = self.sessions.get(session_id)
        
        # 1. Get initial code
        code = None
        if session and session.final_code:
            code = session.final_code
        elif code_override:
            code = code_override

        if not code:
            return {"error": "No final strategy found in session. Try regenerating the algorithm."}

        # 2. Validation & Repair Loop (Max 3 retries)
        max_retries = 3
        attempt = 0
        validation_error = None
        
        while attempt < max_retries:
            print(f"[SandboxAgent] Validation Attempt {attempt + 1}/{max_retries}")
            if self.socketio:
                self.socketio.emit('sandbox_log', {
                    'session_id': session_id,
                    'type': 'thinking',
                    'message': f"Validating Algorithm (Attempt {attempt + 1}/{max_retries})..."
                })
            
            # A. Static Validation
            static_val = self._validate_strategy_code(code)
            if not static_val["valid"]:
                validation_error = f"Static Syntax Error: {static_val['errors'][0]}"
                print(f"[SandboxAgent] Static Validation Failed: {validation_error}")
            else:
                # B. Runtime Validation (The "Compiler")
                runtime_val = self._validate_runtime_safety(code)
                if not runtime_val["valid"]:
                    validation_error = f"Runtime Error during Simulation: {runtime_val['error']}"
                    print(f"[SandboxAgent] Runtime Validation Failed: {validation_error}")
                else:
                    # Success!
                    print("[SandboxAgent] Code passed all validations.")
                    if self.socketio:
                        self.socketio.emit('sandbox_log', {
                            'session_id': session_id,
                            'type': 'success',
                            'message': "Algorithm passed all safety checks."
                        })
                    validation_error = None
                    break
            
            # C. Attempt Repair
            if validation_error:
                if self.socketio:
                    self.socketio.emit('sandbox_log', {
                        'session_id': session_id,
                        'type': 'error',
                        'message': f"Validation Failed: {validation_error}"
                    })
                
                attempt += 1
                if attempt < max_retries and session:
                    print("[SandboxAgent] Attempting auto-repair with LLM...")
                    if self.socketio:
                        self.socketio.emit('sandbox_log', {
                            'session_id': session_id,
                            'type': 'thinking',
                            'message': "Attempting to auto-fix the algorithm..."
                        })

                    repair_prompt = f"""
The algorithm you wrote failed validation with the following error:
{validation_error}

Please fix the code to resolve this error. Ensure you handle None values safely (e.g. data.get('key', 0) or 0).
Return ONLY the fixed complete Python code block.
"""
                    # Add repair request to history
                    session.message_history.append({"role": "user", "content": repair_prompt})
                    
                    try:
                        # Call LLM for fix
                        response = self._call_llm(session)
                        
                        # Extract fixed code
                        code_blocks = self._extract_code_blocks(response)
                        if code_blocks:
                            code = code_blocks[-1] # Take the last block
                            session.message_history.append({"role": "assistant", "content": response})
                            print("[SandboxAgent] LLM provided fixed code.")
                            if self.socketio:
                                self.socketio.emit('sandbox_log', {
                                    'session_id': session_id,
                                    'type': 'success',
                                    'message': "Generated fix. Re-validating..."
                                })
                        else:
                            print("[SandboxAgent] LLM did not provide code in repair response.")
                            break # abort if no code returned
                    except Exception as e:
                        print(f"[SandboxAgent] Auto-repair failed: {e}")
                        break
                else:
                    break # No session or max retries reached

        # 3. Final Check
        if validation_error:
            return {
                "success": False, 
                "error": f"Validation failed after {attempt} attempts. Last error: {validation_error}",
                "validation": {"valid": False, "errors": [validation_error]}
            }

        # 4. Save to agents directory (Only if valid)
        if not agent_name.startswith("Agent_"):
            agent_name = f"Agent_{agent_name}"

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(base_dir, "market_simulation", "agents", f"{agent_name}.py")

        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                f.write(code)
            
            # Update session with final fixed code
            if session:
                session.final_code = code
                
        except Exception as e:
            return {"error": f"Failed to save agent file: {str(e)}"}

        # Close the session on success
        self.close_session(session_id)

        return {
            "success": True,
            "agent_name": agent_name,
            "filepath": filepath,
            "validation": {"valid": True, "errors": []}
        }

    def _validate_runtime_safety(self, code: str) -> Dict:
        """
        Runtime validation: Compiles and executes key logic against 'dirty' mock data
        to catch NoneType errors and other runtime crashes.
        """
        try:
            # 1. Compile
            compiled = compile(code, "<string>", "exec")
            
            # 2. Setup Mock Environment
            mock_globals = {'np': __import__('numpy')}
            mock_locals = {}
            exec(compiled, mock_globals, mock_locals)
            
            if 'execute_strategy' not in mock_locals:
                return {"valid": False, "error": "Function 'execute_strategy' not found"}
                
            execute_strategy = mock_locals['execute_strategy']
            
            # 3. Create Dirty Mock Data (None values, missing keys)
            # This is designed to break non-defensive code
            dirty_market_data = {
                'BTC': {
                    'price': 50000.0,
                    'volume': 100.0,
                    'obi_weighted': None,  # Should be 0
                    'sentiment': None,     # Should be 0
                    'micro_price': None,   # Should be price
                    # Missing keys: 'ofi', 'funding_rate', etc.
                },
                'ETH': None, # Totally missing data
                'SOL': {}    # Empty data
            }
            
            mock_tick = 100
            mock_cash = 10000.0
            mock_portfolio = {'BTC': 0, 'ETH': 0, 'SOL': 0}
            mock_state = {} # Check if it handles empty state initialization
            
            # 4. Run Execution
            # Call it a few times to check state persistence safety
            for i in range(3):
                execute_strategy(
                    dirty_market_data, 
                    mock_tick + i, 
                    mock_cash, 
                    mock_portfolio, 
                    market_state={}, 
                    agent_state=mock_state
                )
                
            return {"valid": True, "error": None}
            
        except Exception as e:
            # Capture the actual runtime error (e.g. "TypeError: unsupported operand...")
            import traceback
            tb = traceback.format_exc()
            # concise error
            error_msg = str(e)
            return {"valid": False, "error": error_msg}

    def get_session_status(self, session_id: str) -> Dict:
        """Get current session status and metadata."""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        return session.to_dict()

    def get_session_history(self, session_id: str) -> Dict:
        """Get full message and execution history for a session."""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        return {
            "session_id": session_id,
            "messages": [
                msg for msg in session.message_history
                if msg["role"] != "system"  # Don't expose system prompt
            ],
            "executions": session.execution_history,
            "final_code": session.final_code
        }

    def close_session(self, session_id: str) -> Dict:
        """Close session and cleanup sandbox resources."""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        session.close()
        del self.sessions[session_id]

        return {"success": True, "session_id": session_id}

    # ==================== Private Methods ====================

    def _call_llm(self, session: SandboxSession) -> str:
        """Call LLM with conversation history."""
        model = session.model
        print(f"[SandboxAgent] Calling LLM with model: {model}")
        is_github_model = model.startswith('github:')
        actual_model = model.replace('github:', '') if is_github_model else model
        print(f"[SandboxAgent] Is GitHub model: {is_github_model}, Actual model: {actual_model}")

        # AGGRESSIVE PRUNING: Keep System Prompt + Last 2 messages only
        # GitHub Models has 8k token limit, so we need to be very conservative
        full_history = session.message_history
        
        # Truncate long messages (over 2000 chars)
        def truncate_message(msg):
            content = msg.get("content", "")
            if len(content) > 2000:
                return {**msg, "content": content[:2000] + "... [truncated for token limit]"}
            return msg
        
        # Keep system prompt (first message) + last 2 messages only
        if len(full_history) > 3:
            pruned_history = [truncate_message(full_history[0])] + [truncate_message(m) for m in full_history[-2:]]
            print(f"[SandboxAgent] Pruned history from {len(full_history)} to {len(pruned_history)} messages")
        else:
            pruned_history = [truncate_message(m) for m in full_history]

        if is_github_model:
            if not GITHUB_AI_AVAILABLE:
                raise Exception("GitHub AI SDK not installed")
            if not self.github_token:
                raise Exception("No GITHUB_TOKEN set")
            return self._call_github_api(actual_model, pruned_history)
        else:
            if not self.api_key:
                raise Exception("No OpenRouter API key set")
            return self._call_openrouter_api(actual_model, pruned_history)

    def _call_openrouter_api(self, model: str, messages: List[Dict]) -> str:
        """Call OpenRouter API with message history."""
        response = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
            },
            json={
                "model": model,
                "messages": messages,
                "max_tokens": 4096
            },
            timeout=120
        )

        if response.status_code != 200:
            raise Exception(f"OpenRouter API error: {response.text}")

        return response.json()['choices'][0]['message']['content']

    def _call_github_api(self, model: str, messages: List[Dict]) -> str:
        """Call GitHub AI API with message history."""
        client = ChatCompletionsClient(
            endpoint=self.github_endpoint,
            credential=AzureKeyCredential(self.github_token),
        )

        # Convert message dicts to SDK message objects
        sdk_messages = []
        for msg in messages:
            if msg["role"] == "system":
                sdk_messages.append(SystemMessage(content=msg["content"]))
            elif msg["role"] == "user":
                sdk_messages.append(UserMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                sdk_messages.append(AssistantMessage(content=msg["content"]))

        response = client.complete(
            messages=sdk_messages,
            model=model
        )

        return response.choices[0].message.content

    def _extract_code_blocks(self, content: str) -> List[str]:
        """Extract Python code blocks from LLM response."""
        # Match ```python ... ``` or ``` ... ```
        pattern = r"```(?:python)?\s*(.*?)\s*```"
        matches = re.findall(pattern, content, re.DOTALL)
        return [match.strip() for match in matches if match.strip()]

    def _parse_structured_response(self, content: str) -> Dict:
        """Parse structured sections from LLM response (thinking, api_calls, analysis)."""
        result = {
            "thinking": None,
            "api_calls": [],
            "analysis": None,
            "clean_response": content
        }

        # Extract <thinking>...</thinking>
        thinking_match = re.search(r"<thinking>(.*?)</thinking>", content, re.DOTALL)
        if thinking_match:
            result["thinking"] = thinking_match.group(1).strip()
            # Remove from clean response
            result["clean_response"] = re.sub(r"<thinking>.*?</thinking>", "", result["clean_response"], flags=re.DOTALL)

        # Extract <api_calls>...</api_calls>
        api_match = re.search(r"<api_calls>(.*?)</api_calls>", content, re.DOTALL)
        if api_match:
            api_text = api_match.group(1).strip()
            # Parse individual API calls (lines starting with - or GET/POST)
            lines = api_text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('-'):
                    line = line[1:].strip()
                if line and ('GET' in line or 'POST' in line or '/' in line):
                    result["api_calls"].append(line)
            # Remove from clean response
            result["clean_response"] = re.sub(r"<api_calls>.*?</api_calls>", "", result["clean_response"], flags=re.DOTALL)

        # Extract <analysis>...</analysis>
        analysis_match = re.search(r"<analysis>(.*?)</analysis>", content, re.DOTALL)
        if analysis_match:
            result["analysis"] = analysis_match.group(1).strip()
            # Remove from clean response
            result["clean_response"] = re.sub(r"<analysis>.*?</analysis>", "", result["clean_response"], flags=re.DOTALL)

        # Clean up extra whitespace
        result["clean_response"] = re.sub(r'\n{3,}', '\n\n', result["clean_response"]).strip()

        return result

    def _format_execution_results(self, executed_blocks: List[Dict]) -> str:
        """Format execution results for feedback to LLM."""
        results = []
        for i, block in enumerate(executed_blocks, 1):
            result_str = f"[Block {i}]\n"
            if block.get("result"):
                result_str += f"Output:\n{block['result']}\n"
            if block.get("error"):
                result_str += f"Error:\n{block['error']}\n"
            results.append(result_str)
        return "\n".join(results)

    def _check_for_final_strategy(self, response: str) -> Tuple[bool, Optional[str]]:
        """Check if response contains complete execute_strategy function."""
        code_blocks = self._extract_code_blocks(response)

        for code in code_blocks:
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        if node.name == "execute_strategy":
                            # Validate signature (4-6 arguments)
                            num_args = len(node.args.args)
                            if 4 <= num_args <= 6:
                                return True, code
            except SyntaxError:
                continue

        return False, None

    def _validate_strategy_code(self, code: str) -> Dict:
        """Validate strategy code before deployment."""
        errors = []

        # Check syntax
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {
                "valid": False,
                "errors": [f"Syntax error: {e}"],
                "syntax_valid": False,
                "signature_valid": False,
                "no_dangerous_imports": False
            }

        # Check for dangerous imports
        dangerous_imports = ['os', 'sys', 'subprocess', 'socket', 'shutil']
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    if module_name in dangerous_imports:
                        errors.append(f"Dangerous import: {alias.name}")

        # Check for execute_strategy function
        has_strategy = False
        signature_valid = False

        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == 'execute_strategy':
                has_strategy = True
                num_args = len(node.args.args)
                if 4 <= num_args <= 6:
                    signature_valid = True
                else:
                    errors.append(f"execute_strategy needs 4-6 args, found {num_args}")

        if not has_strategy:
            errors.append("Missing execute_strategy function")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "syntax_valid": True,
            "signature_valid": signature_valid,
            "no_dangerous_imports": not any('Dangerous' in e for e in errors)
        }


# Singleton instance (optional, for convenience)
_sandbox_agent_instance = None

def get_sandbox_agent(socketio=None) -> SandboxAgent:
    """Get or create the singleton SandboxAgent instance."""
    global _sandbox_agent_instance
    if _sandbox_agent_instance is None:
        _sandbox_agent_instance = SandboxAgent(socketio)
    return _sandbox_agent_instance
