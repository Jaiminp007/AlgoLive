
import sys
import os
sys.path.append(os.getcwd())

from analyst_engine.brain import Brain

def test_sandbox():
    print("\n--- SANDBOX SECURITY VERIFICATION ---")
    brain = Brain()
    
    # Test 1: Malicious Import
    malicious_code = """
import os
def execute_strategy(a,b,c,d):
    os.system('rm -rf /')
    return "BUY", "BTC", 1.0
"""
    print("Test 1: Malicious Import (os)...")
    if not brain._validate_code(malicious_code, "MaliciousAgent"):
        print("✅ BLOCKED: Malicious import detected.")
    else:
        print("❌ FAILED: Malicious import allowed!")

    # Test 2: Missing Function
    bad_func_code = """
def trade():
    pass
"""
    print("Test 2: Missing execute_strategy...")
    if not brain._validate_code(bad_func_code, "BadFuncAgent"):
        print("✅ BLOCKED: Missing entry point detected.")
    else:
        print("❌ FAILED: Invalid structure allowed!")

    # Test 3: Valid Code
    valid_code = """
import numpy as np
def execute_strategy(market, tick, cash, port):
    return "HOLD", None, 0
"""
    print("Test 3: Valid Code...")
    if brain._validate_code(valid_code, "GoodAgent"):
        print("✅ PASSED: Valid code accepted.")
    else:
        print("❌ FAILED: Valid code rejected!")

if __name__ == "__main__":
    test_sandbox()
