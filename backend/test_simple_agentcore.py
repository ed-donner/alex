#!/usr/bin/env python3
"""
Test all agents by running their individual test_simple.py files in their own directories.
This ensures each agent runs with its own dependencies and environment.
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, cwd):
    """Run a command and capture output."""
    print(f"Running in {cwd}: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr

def test_agent(agent_name, test_file="test_simple.py"):
    """Test an individual agent in its directory."""
    backend_dir = Path(__file__).parent
    agent_dir = backend_dir / f"agent_{agent_name}"
    
    if not agent_dir.exists():
        print(f"  ❌ {agent_name}: Directory not found")
        return False
    
    test_path = agent_dir / test_file
    if not test_path.exists():
        print(f"  ⚠️  {agent_name}: No {test_file} found, skipping")
        return True  # Not a failure, just skip
    
    # Set environment for mocked lambdas
    env = os.environ.copy()
    env['MOCK_LAMBDAS'] = 'true'
    
    # Run the test with uv
    success, stdout, stderr = run_command(
        ['uv', 'run', test_file],
        cwd=str(agent_dir)
    )
    
    if success:
        print(f"  ✅ {agent_name}: Test passed")
        if stdout and "Status Code: 200" in stdout:
            # Extract key info from successful runs
            for line in stdout.split('\n'):
                if 'Tagged:' in line or 'Success:' in line or 'Message:' in line:
                    print(f"     {line.strip()}")
    else:
        print(f"  ❌ {agent_name}: Test failed")
        if stderr:
            # Show first error line
            error_lines = [l for l in stderr.split('\n') if l.strip()]
            if error_lines:
                print(f"     Error: {error_lines[0][:100]}")
    
    return success

def main():
    """Run all agent tests."""
    print("="*60)
    print("TESTING ALL AGENTS")
    print("Running individual test_simple.py in each agent directory")
    print("="*60)
    
    # List of agents to test
    agents = [
        'tagger',
        'reporter', 
        'charter',
        'retirement',
        'planner'
    ]
    
    results = {}
    
    for agent in agents:
        print(f"\n{agent.upper()} Agent:")
        results[agent] = test_agent(agent)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results.values() if r)
    failed = sum(1 for r in results.values() if not r)
    
    print(f"Passed: {passed}/{len(agents)}")
    print(f"Failed: {failed}/{len(agents)}")
    
    if failed > 0:
        print("\nFailed agents:")
        for agent, success in results.items():
            if not success:
                print(f"  - {agent}")
    
    print("="*60)
    
    if failed > 0:
        print("\n⚠️  SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("\n✅ ALL TESTS PASSED!")
        sys.exit(0)

if __name__ == "__main__":
    main()