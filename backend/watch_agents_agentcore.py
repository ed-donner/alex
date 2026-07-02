#!/usr/bin/env python3
"""
Watch CloudWatch logs from all Alex agents in real-time.
Polls all 5 agent log groups simultaneously and displays output with color coding.
"""

import boto3
import time
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

# ANSI color codes for terminal output
COLORS = {
    'PLANNER': '\033[94m',    # Blue
    'TAGGER': '\033[93m',     # Yellow
    'REPORTER': '\033[92m',   # Green
    'CHARTER': '\033[96m',    # Cyan
    'RETIREMENT': '\033[95m', # Magenta
    'PLANNER_AGENTCORE': '\033[104m',    # Blue background
    'TAGGER_AGENTCORE': '\033[103m',     # Yellow background
    'REPORTER_AGENTCORE': '\033[102m',   # Green background
    'CHARTER_AGENTCORE': '\033[106m',    # Cyan background
    'RETIREMENT_AGENTCORE': '\033[105m', # Magenta background
    'ERROR': '\033[91m',      # Red
    'LANGFUSE': '\033[35m',   # Purple (for LangFuse-related logs)
    'RESET': '\033[0m',       # Reset to default
    'BOLD': '\033[1m',        # Bold text
}

# Agent log groups - will be populated dynamically from SSM
LOG_GROUPS = {}

def get_agent_log_groups(region: str = 'us-east-1') -> Dict[str, str]:
    """Get all agent log groups from SSM parameters."""
    ssm_client = boto3.client('ssm', region_name=region)
    log_groups = {}
    
    # Agent names to check
    agent_names = ['planner', 'tagger', 'reporter', 'charter', 'retirement']
    
    for agent_name in agent_names:
        try:
            # Get agent ARN from SSM
            parameter_name = f"/agents/{agent_name}_agent_arn"
            response = ssm_client.get_parameter(Name=parameter_name)
            agent_arn = response['Parameter']['Value']
            
            # Extract agent ID from ARN
            # ARN format: arn:aws:bedrock:us-east-1:123456789012:agent/AGENT_ID
            agent_id = agent_arn.split('/')[-1]
            
            # Construct log group name
            log_group_name = f"/aws/bedrock-agentcore/runtimes/{agent_id}-DEFAULT"
            
            # Add both Lambda and AgentCore log groups
            # log_groups[agent_name.upper()] = f"/aws/lambda/alex-{agent_name}"
            log_groups[f"{agent_name.upper()}_AGENTCORE"] = log_group_name
            
            print(f"Found {agent_name} agent: {agent_id}")
            # print(f"  Lambda logs: /aws/lambda/alex-{agent_name}")
            print(f"  AgentCore logs: {log_group_name}")
            
        except Exception as e:
            print(f"Warning: Could not get {agent_name} agent ARN from SSM: {e}")
            # Fallback to Lambda logs only
            log_groups[agent_name.upper()] = f"/aws/lambda/alex-{agent_name}"
    
    return log_groups


class AgentLogWatcher:
    """Watches CloudWatch logs for all agents."""

    def __init__(self, region: str = 'us-east-1', lookback_minutes: int = 5):
        """Initialize the log watcher."""
        self.logs_client = boto3.client('logs', region_name=region)
        self.lookback_minutes = lookback_minutes
        
        # Get log groups dynamically from SSM
        print("Getting agent log groups from SSM parameters...")
        global LOG_GROUPS
        LOG_GROUPS = get_agent_log_groups(region)
        
        if not LOG_GROUPS:
            print("No log groups found! Check your SSM parameters.")
            sys.exit(1)
            
        self.last_timestamps = {agent: 0 for agent in LOG_GROUPS}
        
        print(f"\nWatching {len(LOG_GROUPS)} log groups:")
        for agent, log_group in LOG_GROUPS.items():
            color = COLORS.get(agent, '')
            reset = COLORS['RESET']
            print(f"  {color}{agent:20}{reset} -> {log_group}")
        print()

    def get_log_events(self, agent: str, start_time: int) -> List[Dict]:
        """Get log events for a specific agent."""
        log_group = LOG_GROUPS[agent]

        try:
            # Get all log streams in the log group
            response = self.logs_client.describe_log_streams(
                logGroupName=log_group,
                orderBy='LastEventTime',
                descending=True,
                limit=5  # Get the 5 most recent streams
            )

            if not response.get('logStreams'):
                return []

            # Collect events from all recent streams
            all_events = []
            for stream in response['logStreams']:
                stream_name = stream['logStreamName']

                # Get events from this stream
                try:
                    events_response = self.logs_client.filter_log_events(
                        logGroupName=log_group,
                        logStreamNames=[stream_name],
                        startTime=start_time,
                        limit=100
                    )

                    events = events_response.get('events', [])
                    all_events.extend(events)

                except Exception as e:
                    # Stream might have been deleted or have no events
                    continue

            # Sort events by timestamp
            all_events.sort(key=lambda x: x['timestamp'])

            # Update last timestamp for this agent
            if all_events:
                self.last_timestamps[agent] = all_events[-1]['timestamp'] + 1

            return all_events

        except self.logs_client.exceptions.ResourceNotFoundException:
            print(f"{COLORS['ERROR']}Log group {log_group} not found{COLORS['RESET']}")
            return []
        except Exception as e:
            print(f"{COLORS['ERROR']}Error fetching logs for {agent}: {e}{COLORS['RESET']}")
            return []

    def format_message(self, agent: str, event: Dict) -> str:
        """Format a log message with color coding."""
        timestamp = datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%H:%M:%S.%f')[:-3]
        message = event['message'].rstrip()

        # Color the agent name
        agent_color = COLORS.get(agent, COLORS['RESET'])
        
        # Make AgentCore logs more distinctive
        if '_AGENTCORE' in agent:
            agent_label = f"{agent_color}[{agent:20}]{COLORS['RESET']}"
        else:
            agent_label = f"{agent_color}[{agent:15}]{COLORS['RESET']}"

        # Highlight specific message types
        if 'ERROR' in message or 'Exception' in message or 'Failed' in message:
            message_color = COLORS['ERROR']
        elif 'LangFuse' in message or 'Observability' in message:
            message_color = COLORS['LANGFUSE']
        elif 'DEBUG:' in message:
            message_color = COLORS.get(agent, '')
        else:
            message_color = ''

        if message_color:
            message = f"{message_color}{message}{COLORS['RESET']}"

        return f"{timestamp} {agent_label} {message}"

    def poll_agent(self, agent: str, start_time: int) -> List[str]:
        """Poll a single agent for new log events."""
        events = self.get_log_events(agent, start_time)
        formatted_messages = []

        for event in events:
            formatted_messages.append(self.format_message(agent, event))

        return formatted_messages

    def watch(self, poll_interval: int = 2):
        """Watch all agent logs continuously."""
        print(f"{COLORS['BOLD']}Watching CloudWatch logs for all Alex agents...{COLORS['RESET']}")
        print(f"Looking back {self.lookback_minutes} minutes initially")
        print(f"Polling every {poll_interval} seconds")
        print(f"Press Ctrl+C to stop\n")

        # Initial start time (lookback period)
        initial_start = int((datetime.now() - timedelta(minutes=self.lookback_minutes)).timestamp() * 1000)

        # Set initial timestamps
        for agent in LOG_GROUPS:
            self.last_timestamps[agent] = initial_start

        try:
            while True:
                # Poll all agents in parallel
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = {
                        executor.submit(self.poll_agent, agent, self.last_timestamps[agent]): agent
                        for agent in LOG_GROUPS
                    }

                    # Collect and display results
                    all_messages = []
                    for future in as_completed(futures):
                        messages = future.result()
                        all_messages.extend(messages)

                    # Sort messages by timestamp and display
                    all_messages.sort()
                    for message in all_messages:
                        print(message)

                # Wait before next poll
                time.sleep(poll_interval)

        except KeyboardInterrupt:
            print(f"\n{COLORS['BOLD']}Stopped watching logs{COLORS['RESET']}")
            sys.exit(0)
        except Exception as e:
            print(f"{COLORS['ERROR']}Error: {e}{COLORS['RESET']}")
            sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Watch CloudWatch logs from all Alex agents')
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    parser.add_argument(
        '--lookback',
        type=int,
        default=5,
        help='Minutes to look back initially (default: 5)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=2,
        help='Polling interval in seconds (default: 2)'
    )

    args = parser.parse_args()

    watcher = AgentLogWatcher(region=args.region, lookback_minutes=args.lookback)
    watcher.watch(poll_interval=args.interval)


if __name__ == "__main__":
    main()