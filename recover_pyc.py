import marshal
import dis
import os

filename = 'market_simulation/agents/__pycache__/Agent_sandbox_mistralai_devst.cpython-313.pyc'

try:
    with open(filename, 'rb') as f:
        f.seek(16) # Skip header (standard for 3.7+)
        code_obj = marshal.load(f)
        
        print("--- DISASSEMBLY ---")
        dis.dis(code_obj)
        print("\n--- CONSTANTS ---")
        print(code_obj.co_consts)
        print("\n--- NAMES ---")
        print(code_obj.co_names)
        print("\n--- VARNAMES ---")
        print(code_obj.co_varnames)
except Exception as e:
    print(f"Error: {e}")
