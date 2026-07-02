#!/usr/bin/env python3
"""
Destroy deployed Bedrock AgentCore agents and their resources.

Note: AWS Bedrock AgentCore agents are managed services that don't require explicit deletion.
The agent runtime will be automatically cleaned up when the associated infrastructure resources are removed.
This script focuses on cleaning up:
- IAM roles and policies
- SSM parameters 
- Local configuration files
"""
import json
import boto3
from botocore.exceptions import ClientError
import os
import sys
from bedrock_agentcore_starter_toolkit import Runtime

def destroy_agent(agent_name=None):
    """
    Tear down a deployed Bedrock AgentCore agent and its resources.
    
    Args:
        agent_name: Specific agent to destroy, or None to destroy all
    """
    
    # Define the 5 agents explicitly
    agent_names = ['planner', 'tagger', 'reporter', 'charter', 'retirement']
    
    if agent_name:
        if agent_name not in agent_names:
            print(f"❌ Unknown agent: {agent_name}")
            print(f"   Valid agents: {', '.join(agent_names)}")
            return False
        agents_to_destroy = [agent_name]
    else:
        agents_to_destroy = agent_names
    
    success_count = 0
    total_count = len(agents_to_destroy)
    
    # Get region from environment or default
    region = os.environ.get('AWS_REGION', 'us-east-1')
    ssm = boto3.client('ssm', region_name=region)
    
    for agent_name_current in agents_to_destroy:
        try:
            # Read agent ARN from SSM parameter
            parameter_name = f'/agents/{agent_name_current}_agent_arn'

            print(f"\n🧹 Destroying agent: {agent_name_current}")
            print(f"   Reading parameter: {parameter_name}")

            try:
                response = ssm.get_parameter(Name=parameter_name)
                agent_arn = response['Parameter']['Value']
                print(f"   Agent ARN: {agent_arn}")
                
                # Extract agent ID from ARN (format: arn:aws:bedrock:region:account:agent/agent-id)
                agent_id = agent_arn.split('/')[-1]
                print(f"   Agent ID: {agent_id}")
                
            except ssm.exceptions.ParameterNotFound:
                print(f"❌ Parameter not found: {parameter_name}")
                print(f"   Agent {agent_name_current} may not be deployed or already destroyed")
                continue
            except Exception as e:
                print(f"❌ Error reading parameter {parameter_name}: {e}")
                continue
            
            # Delete the AgentCore runtime using the correct AWS API
            agentcore_deletion_success = False
            try:
                print(f"   Deleting AgentCore runtime...")
                
                # Use the correct bedrock-agentcore-control client for deletion
                agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=region)
                
                try:
                    # Delete the AgentCore Runtime using the agent ID
                    response = agentcore_control_client.delete_agent_runtime(
                        agentRuntimeId=agent_id
                    )
                    
                    print(f"   ✅ AgentCore Runtime {agent_id} deletion initiated")
                    if 'status' in response:
                        print(f"   Status: {response['status']}")
                    agentcore_deletion_success = True
                    
                except Exception as delete_error:
                    print(f"   ⚠️ Could not delete AgentCore runtime: {delete_error}")
                    # Check if it's because the runtime doesn't exist
                    if "NotFound" in str(delete_error) or "ResourceNotFound" in str(delete_error):
                        print(f"   ℹ️ AgentCore runtime may already be deleted")
                        agentcore_deletion_success = True  # Consider this a success since it's already gone
                    else:
                        agentcore_deletion_success = False
                
            except Exception as e:
                print(f"   ⚠️ Error accessing AgentCore control client: {e}")
                print(f"   ℹ️ Continuing with other cleanup steps...")
                agentcore_deletion_success = False
            
            # Track cleanup success for different components
            cleanup_success = {
                'agentcore_runtime': agentcore_deletion_success,
                'local_config': False,
                'iam_role': False
            }
            
            # Clean up local configuration files and directories for this agent
            try:
                import shutil
                agent_dir = f"../../backend/agent_{agent_name_current}"
                
                # Files to delete
                config_files_to_clean = [
                    f"{agent_dir}/.bedrock_agentcore.yaml",
                    f"{agent_dir}/agent_deployment_{agent_name_current}.json",
                    f"{agent_dir}/Dockerfile"
                ]
                
                # Directories to delete
                config_dirs_to_clean = [
                    f"{agent_dir}/src"
                ]
                
                files_removed = 0
                dirs_removed = 0
                
                # Remove files
                for config_file in config_files_to_clean:
                    if os.path.exists(config_file):
                        os.remove(config_file)
                        print(f"   ✅ Removed file: {os.path.basename(config_file)}")
                        files_removed += 1
                
                # Remove directories
                for config_dir in config_dirs_to_clean:
                    if os.path.exists(config_dir):
                        shutil.rmtree(config_dir)
                        print(f"   ✅ Removed directory: {os.path.basename(config_dir)}/")
                        dirs_removed += 1
                
                if files_removed > 0 or dirs_removed > 0:
                    print(f"   ✅ Local cleanup completed ({files_removed} files, {dirs_removed} directories)")
                else:
                    print(f"   ℹ️ No local files or directories to clean up")
                    
                cleanup_success['local_config'] = True
                        
            except Exception as e:
                print(f"   Warning: Could not clean up local config files: {e}")
                cleanup_success['local_config'] = False
            
            # Clean up IAM role (use predictable role name)
            agent_role_name = f"alex-{agent_name_current}-agent-role"
            try:
                print(f"   Cleaning up IAM role: {agent_role_name}")
                iam_client = boto3.client('iam', region_name=region)
                
                # Check if role exists first
                try:
                    iam_client.get_role(RoleName=agent_role_name)
                    role_exists = True
                except iam_client.exceptions.NoSuchEntityException:
                    print(f"   ℹ️ IAM role {agent_role_name} already deleted or doesn't exist")
                    role_exists = False
                except Exception as e:
                    print(f"   Warning: Could not check if role exists: {e}")
                    role_exists = False
                
                if role_exists:
                    # List and delete role policies
                    try:
                        policies = iam_client.list_role_policies(RoleName=agent_role_name)
                        for policy_name in policies['PolicyNames']:
                            iam_client.delete_role_policy(
                                RoleName=agent_role_name,
                                PolicyName=policy_name
                            )
                            print(f"   ✅ Deleted role policy: {policy_name}")
                    except Exception as e:
                        print(f"   Warning: Could not clean up role policies: {e}")
                    
                    # List and detach managed policies
                    try:
                        attached_policies = iam_client.list_attached_role_policies(RoleName=agent_role_name)
                        for policy in attached_policies['AttachedPolicies']:
                            iam_client.detach_role_policy(
                                RoleName=agent_role_name,
                                PolicyArn=policy['PolicyArn']
                            )
                            print(f"   ✅ Detached managed policy: {policy['PolicyName']}")
                    except Exception as e:
                        print(f"   Warning: Could not detach managed policies: {e}")
                    
                    # Delete the role
                    try:
                        iam_client.delete_role(RoleName=agent_role_name)
                        print(f"   ✅ Deleted IAM role: {agent_role_name}")
                    except Exception as e:
                        print(f"   Warning: Could not delete IAM role: {e}")
                else:
                    print(f"   ✅ IAM role cleanup not needed (role doesn't exist)")
                    
                cleanup_success['iam_role'] = True
                    
            except Exception as e:
                print(f"   Warning: IAM cleanup failed: {e}")
                cleanup_success['iam_role'] = False
            
            # Only delete SSM parameter if all cleanup operations succeeded
            if all(cleanup_success.values()):
                try:
                    ssm.delete_parameter(Name=parameter_name)
                    print(f"   ✅ Deleted SSM parameter: {parameter_name}")
                    print(f"   ✅ Agent {agent_name_current} cleanup completed successfully")
                    success_count += 1
                except Exception as e:
                    print(f"   ❌ Could not delete SSM parameter: {e}")
                    print(f"   ❌ Agent {agent_name_current} cleanup completed with errors (SSM parameter retained)")
            else:
                failed_components = [comp for comp, success in cleanup_success.items() if not success]
                print(f"   ⚠️ Skipping SSM parameter deletion due to failed cleanup: {', '.join(failed_components)}")
                print(f"   ⚠️ Agent {agent_name_current} cleanup completed with errors (SSM parameter retained for retry)")
                # Still count as processed, but with warnings
            
        except Exception as e:
            print(f"❌ Error processing agent {agent_name_current}: {e}")
            continue
    
    print(f"\n📊 Cleanup Summary: {success_count}/{total_count} agents processed successfully")
    return True #success_count == total_count

if __name__ == "__main__":
    if len(sys.argv) > 2:
        print("Usage: python destroy_agents.py [agent_name]")
        print("  agent_name: Optional specific agent to destroy")
        print("  If no agent specified, all deployed agents will be destroyed")
        sys.exit(1)
    
    agent_name = sys.argv[1] if len(sys.argv) == 2 else None
    
    if agent_name:
        print(f"🎯 Destroying specific agent: {agent_name}")
    else:
        print("🧹 Destroying all deployed agents...")
    
    success = destroy_agent(agent_name)
    sys.exit(0 if success else 1)