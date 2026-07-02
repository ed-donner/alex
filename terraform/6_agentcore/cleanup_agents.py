#!/usr/bin/env python3
"""
Clean up existing agent resources and parameters
"""

import boto3
import sys

def cleanup_agent_resources():
    """Clean up existing agent SSM parameters and prepare for fresh deployment"""
    
    region = "us-east-1"
    ssm = boto3.client('ssm', region_name=region)
    
    # List of agent parameters to clean up
    agent_names = ['planner', 'tagger', 'reporter', 'charter', 'retirement']
    
    print("🧹 Cleaning up existing agent resources...")
    
    for agent_name in agent_names:
        param_name = f"/agents/{agent_name}_agent_arn"
        try:
            # Try to get the parameter first
            response = ssm.get_parameter(Name=param_name)
            print(f"   Found parameter: {param_name}")
            
            # Delete the parameter
            ssm.delete_parameter(Name=param_name)
            print(f"   ✅ Deleted parameter: {param_name}")
            
        except ssm.exceptions.ParameterNotFound:
            print(f"   ℹ️  Parameter not found: {param_name}")
        except Exception as e:
            print(f"   ❌ Error with {param_name}: {e}")
    
    print("\n✅ Cleanup completed. You can now run terraform apply again.")
    print("\nNote: This cleanup only removes SSM parameters.")
    print("If there are still AgentCore conflicts, you may need to manually")
    print("clean up resources in the AWS Bedrock console.")

if __name__ == "__main__":
    cleanup_agent_resources()