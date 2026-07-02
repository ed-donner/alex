#!/usr/bin/env python3
"""
Test script to validate the deploy_agents.py functionality
"""

import os
import sys
import subprocess

def test_deploy_script():
    """Test the deploy_agents.py script with validation only"""
    
    # Check if we're in the right directory
    current_dir = os.getcwd()
    expected_dir = "terraform/6_agents"
    
    if not current_dir.endswith(expected_dir):
        print(f"❌ Please run this from the {expected_dir} directory")
        print(f"Current directory: {current_dir}")
        return False
    
    # Check if deploy_agents.py exists
    if not os.path.exists("deploy_agents.py"):
        print("❌ deploy_agents.py not found in current directory")
        return False
    
    # Check if backend directory structure exists
    backend_path = "../../backend"
    if not os.path.exists(backend_path):
        print(f"❌ Backend directory not found: {backend_path}")
        return False
    
    # Check if all agent directories exist
    agents = ["planner", "tagger", "reporter", "charter", "retirement"]
    missing_agents = []
    
    for agent in agents:
        agent_dir = os.path.join(backend_path, agent)
        agent_file = os.path.join(agent_dir, "agent.py")
        
        if not os.path.exists(agent_dir):
            missing_agents.append(f"{agent} (directory)")
        elif not os.path.exists(agent_file):
            missing_agents.append(f"{agent} (agent.py)")
    
    if missing_agents:
        print(f"❌ Missing agent components: {', '.join(missing_agents)}")
        return False
    
    print("✅ All agent directories and files found")
    
    # Test import functionality (without actually deploying)
    print("Testing Python imports...")
    try:
        # Test if we can import the script without running it
        result = subprocess.run([
            sys.executable, "-c",
            "import sys; sys.path.insert(0, '../../backend'); from utils import configure_runtime, create_agentcore_role; print('✅ Backend utils imported successfully')"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"❌ Import test failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Import test timed out")
        return False
    except Exception as e:
        print(f"❌ Import test error: {e}")
        return False
    
    print("\n✅ All validation tests passed!")
    print("\nTo deploy agents, run:")
    print("  terraform apply")
    print("\nOr deploy individual agents:")
    for agent in agents:
        print(f"  python deploy_agents.py {agent}")
    
    return True

if __name__ == "__main__":
    print("🧪 Testing deploy_agents.py setup...")
    print("=" * 50)
    
    success = test_deploy_script()
    sys.exit(0 if success else 1)