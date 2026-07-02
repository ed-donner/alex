import sys
import os
import boto3
import json
import time

# Add backend directory to Python path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from utils import configureruntime, create_agentcore_role, save_env_to_ssm


def deploy_agent(agent_name):
    """Deploy a single agent using the bedrock agentcore toolkit"""
    
    # Validate agent name
    valid_agents = ['planner', 'tagger', 'reporter', 'charter', 'retirement']
    if agent_name not in valid_agents:
        raise ValueError(f"Invalid agent name: {agent_name}. Must be one of: {valid_agents}")
    

    # Get AWS region from environment
    region = os.getenv("DEFAULT_AWS_REGION", "us-east-1")
    print(f"Deploying agent '{agent_name}' in region '{region}'")
    
    # Set working directory to the specific agent directory
    agent_dir = os.path.join(backend_path, f"agent_{agent_name}")
    if not os.path.exists(agent_dir):
        raise FileNotFoundError(f"Agent directory not found: {agent_dir}")
    
    # Check for agent.py file
    agent_file = os.path.join(agent_dir, "agent.py")
    if not os.path.exists(agent_file):
        raise FileNotFoundError(f"agent.py not found in: {agent_dir}")
    
    # Copy required files to agent directory
    print(f"Copying required files to agent directory...")
    
    # Copy database src directory
    database_src_dir = os.path.join(backend_path, "database", "src")
    agent_src_dir = os.path.join(agent_dir, "src")
    
    if os.path.exists(database_src_dir):
        import shutil
        if os.path.exists(agent_src_dir):
            shutil.rmtree(agent_src_dir)  # Remove existing src directory
        shutil.copytree(database_src_dir, agent_src_dir)
        print(f"  ✓ Copied database/src to {agent_name}/src")
    else:
        print(f"  ⚠ Database src directory not found: {database_src_dir}")
    
    # Copy utils.py file
    utils_source = os.path.join(backend_path, "utils.py")
    utils_dest = os.path.join(agent_dir, "utils.py")
    
    if os.path.exists(utils_source):
        import shutil
        shutil.copy2(utils_source, utils_dest)
        print(f"  ✓ Copied utils.py to {agent_name} directory")
    else:
        print(f"  ⚠ utils.py not found: {utils_source}")

    # Change to agent directory for deployment
    original_cwd = os.getcwd()
    try:
        os.chdir(agent_dir)
        print(f"Changed to directory: {agent_dir}")
        
        # Create IAM role for the agent
        print(f"Creating IAM role for agent: {agent_name}")
        agent_iam_role = create_agentcore_role(agent_name=agent_name, region=region)
        agent_role_arn = agent_iam_role['Role']['Arn']
        agent_role_name = agent_iam_role['Role']['RoleName']
        print(f"Created IAM role: {agent_role_name}")
        print(f"Role ARN: {agent_role_arn}")
        
        # Configure runtime (this looks for pyproject.toml or requirements.txt automatically)
        print(f"Configuring runtime for agent: {agent_name}")
        

        _, agent_runtime = configureruntime(agent_name, agent_role_arn, "agent.py")
        
        # Launch the agent
        print(f"Launching agent: {agent_name}")
        launch_result = agent_runtime.launch(auto_update_on_conflict=True)
        agent_id = launch_result.agent_id
        agent_arn = launch_result.agent_arn
        
        print(f"Agent deployed successfully!")
        print(f"Agent ID: {agent_id}")
        print(f"Agent ARN: {agent_arn}")
        
        # Save ARN to parameter store for future reference
        ssm = boto3.client('ssm', region_name=region)
        ssm.put_parameter(
            Name=f'/agents/{agent_name}_agent_arn',
            Value=agent_arn,
            Type='String',
            Overwrite=True
        )
        print(f"Saved agent ARN to SSM parameter: /agents/{agent_name}_agent_arn")
        
        return agent_arn
        
    finally:
        # Always return to original directory
        os.chdir(original_cwd)

if __name__ == "__main__":
 
    if len(sys.argv) != 2:
        print("Usage: python deploy_agents.py <agent_name>")
        print("Valid agent names: planner, tagger, reporter, charter, retirement,all")
        sys.exit(1)
    
    agent_name = sys.argv[1]
    if agent_name == "all":
        agents_to_deploy = ['planner', 'tagger', 'reporter', 'charter', 'retirement']
    else:
        agents_to_deploy = [agent_name]

    try:
        for agent_name in agents_to_deploy:
            agent_arn = deploy_agent(agent_name)
            print(f"\n✅ Successfully deployed agent: {agent_name}")
            print(f"Agent ARN: {agent_arn}")
    except Exception as e:
            print(f"\n❌ Failed to deploy agent: {agent_name}")
            print(f"Error: {str(e)}")
            sys.exit(1)