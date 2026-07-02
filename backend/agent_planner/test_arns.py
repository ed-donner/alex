#!/usr/bin/env python3
"""
Test agent ARN resolution
"""

import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Load SSM environment variables
from utils import load_env_from_ssm
load_env_from_ssm()

from tools import get_agent_arn

def test_agent_arns():
    """Test if we can resolve agent ARNs"""
    agents = ['reporter', 'charter', 'retirement', 'tagger']
    
    for agent_name in agents:
        arn = get_agent_arn(agent_name)
        if arn:
            print(f"✅ {agent_name}: {arn}")
        else:
            print(f"❌ {agent_name}: No ARN found")

if __name__ == "__main__":
    test_agent_arns()