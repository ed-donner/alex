#!/usr/bin/env python3
"""
Test script to validate agent deployment and cleanup functionality
"""

import os
import sys
import subprocess
import json
import glob

def test_deploy_and_destroy():
    """Test the deployment and destruction workflow"""
    
    print("🧪 Testing Agent Deployment and Cleanup Workflow")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not os.path.exists("deploy_agents.py"):
        print("❌ Must run from terraform/6_agents directory")
        return False
    
    # Test with tagger agent (smallest/fastest to deploy)
    test_agent = "tagger"
    deployment_file = f"agent_deployment_{test_agent}.json"
    
    try:
        # Clean up any existing deployment file
        if os.path.exists(deployment_file):
            os.remove(deployment_file)
            print(f"🧹 Cleaned up existing {deployment_file}")
        
        print(f"\n📦 Testing deployment of {test_agent} agent...")
        
        # Test deployment (this will take a few minutes)
        deploy_result = subprocess.run([
            "uv", "run", "deploy_agents.py", test_agent
        ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
        
        if deploy_result.returncode != 0:
            print(f"❌ Deployment failed:")
            print(f"STDOUT: {deploy_result.stdout}")
            print(f"STDERR: {deploy_result.stderr}")
            return False
        
        print(f"✅ Deployment completed successfully")
        
        # Check if deployment file was created
        if not os.path.exists(deployment_file):
            print(f"❌ Deployment file not created: {deployment_file}")
            return False
        
        # Validate deployment file content
        with open(deployment_file, 'r') as f:
            deployment_data = json.load(f)
        
        required_fields = ["agent_name", "agent_id", "agent_arn", "agent_role_arn", "region"]
        missing_fields = [field for field in required_fields if not deployment_data.get(field)]
        
        if missing_fields:
            print(f"❌ Deployment file missing required fields: {missing_fields}")
            return False
        
        print(f"✅ Deployment file created with all required fields")
        print(f"   Agent ID: {deployment_data['agent_id']}")
        print(f"   Agent ARN: {deployment_data['agent_arn']}")
        
        print(f"\n🧹 Testing cleanup of {test_agent} agent...")
        
        # Test cleanup
        destroy_result = subprocess.run([
            "uv", "run", "destroy_agents.py", test_agent
        ], capture_output=True, text=True, timeout=120)  # 2 minute timeout
        
        if destroy_result.returncode != 0:
            print(f"❌ Cleanup failed:")
            print(f"STDOUT: {destroy_result.stdout}")
            print(f"STDERR: {destroy_result.stderr}")
            return False
        
        print(f"✅ Cleanup completed successfully")
        
        # Check if deployment file was removed
        if os.path.exists(deployment_file):
            print(f"❌ Deployment file not removed: {deployment_file}")
            return False
        
        print(f"✅ Deployment file cleaned up")
        
        return True
        
    except subprocess.TimeoutExpired:
        print(f"❌ Test timed out")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
    finally:
        # Emergency cleanup
        if os.path.exists(deployment_file):
            print(f"🚨 Emergency cleanup: removing {deployment_file}")
            try:
                subprocess.run(["uv", "run", "destroy_agents.py", test_agent], 
                             timeout=60, capture_output=True)
                if os.path.exists(deployment_file):
                    os.remove(deployment_file)
            except:
                pass

def list_deployments():
    """List all current agent deployments"""
    
    deployment_files = glob.glob("agent_deployment_*.json")
    
    if not deployment_files:
        print("📋 No agent deployments found")
        return
    
    print(f"📋 Found {len(deployment_files)} agent deployment(s):")
    
    for deployment_file in deployment_files:
        try:
            with open(deployment_file, 'r') as f:
                data = json.load(f)
            
            agent_name = data.get("agent_name", "unknown")
            agent_id = data.get("agent_id", "unknown")
            region = data.get("region", "unknown")
            timestamp = data.get("deployment_timestamp")
            
            print(f"  • {agent_name}")
            print(f"    Agent ID: {agent_id}")
            print(f"    Region: {region}")
            if timestamp:
                import datetime
                dt = datetime.datetime.fromtimestamp(timestamp)
                print(f"    Deployed: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
        except Exception as e:
            print(f"  • {deployment_file} (error reading: {e})")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "list":
            list_deployments()
        elif sys.argv[1] == "test":
            success = test_deploy_and_destroy()
            sys.exit(0 if success else 1)
        else:
            print("Usage:")
            print("  python test_agent_lifecycle.py test  - Test deploy and destroy workflow")
            print("  python test_agent_lifecycle.py list - List current deployments")
            sys.exit(1)
    else:
        print("🔍 Listing current deployments...")
        list_deployments()
        print("\nTo test the deployment workflow, run:")
        print("  python test_agent_lifecycle.py test")