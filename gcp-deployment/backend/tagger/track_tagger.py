#!/usr/bin/env python3
"""
Track and display Tagger Lambda logs in real-time
"""

import time
import boto3
import signal
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

class TaggerLogTracker:
    """Continuously poll and display Tagger Lambda logs"""

    def __init__(self):
        self.logs_client = boto3.client('logs', region_name='us-east-1')
        self.log_group_name = '/aws/lambda/alex-tagger'
        self.running = True
        self.last_timestamp = None

        # Set up signal handler for graceful exit
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully"""
        print("\n\n⏹  Stopping log tracking...")
        self.running = False
        sys.exit(0)

    def get_logs(self, start_time):
        """Fetch logs from CloudWatch"""
        try:
            params = {
                'logGroupName': self.log_group_name,
                'startTime': start_time,
                'limit': 100
            }

            response = self.logs_client.filter_log_events(**params)
            return response.get('events', [])

        except Exception as e:
            if 'ResourceNotFoundException' in str(e):
                print(f"⚠️  Log group {self.log_group_name} not found")
            else:
                print(f"❌ Error fetching logs: {e}")
            return []

    def format_log_message(self, event):
        """Format a log event for display"""
        # Extract timestamp
        timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
        time_str = timestamp.strftime('%H:%M:%S.%f')[:-3]

        # Get the message
        message = event['message'].strip()

        # Color code based on content
        if 'ERROR' in message or 'Failed' in message:
            color = '\033[91m'  # Red
        elif 'WARNING' in message or 'WARN' in message:
            color = '\033[93m'  # Yellow
        elif 'LangFuse' in message or 'observability' in message:
            color = '\033[92m'  # Green
        elif 'OpenAI Agents trace' in message:
            color = '\033[96m'  # Cyan
        elif 'Successfully classified' in message:
            color = '\033[94m'  # Blue
        elif 'START RequestId' in message or 'END RequestId' in message:
            color = '\033[95m'  # Magenta
        elif 'INIT_START' in message:
            color = '\033[93m'  # Yellow
        else:
            color = '\033[0m'   # Default

        reset = '\033[0m'

        # Format based on message type
        if 'REPORT RequestId' in message:
            # Parse Lambda report
            parts = message.split('\t')
            if len(parts) >= 3:
                request_id = parts[0].split(' ')[2]
                duration = parts[1] if len(parts) > 1 else ""
                memory = parts[3] if len(parts) > 3 else ""
                return f"{time_str} 📊 {color}Lambda Report: {duration}, {memory}{reset}"
        elif 'START RequestId' in message:
            request_id = message.split(' ')[2]
            return f"{time_str} 🚀 {color}Lambda Start: {request_id[:8]}...{reset}"
        elif 'END RequestId' in message:
            request_id = message.split(' ')[2]
            return f"{time_str} 🏁 {color}Lambda End: {request_id[:8]}...{reset}"
        elif message.startswith('[INFO]') or message.startswith('[ERROR]') or message.startswith('[WARNING]'):
            # Standard Python logging
            parts = message.split('\t', 2)
            if len(parts) >= 3:
                level = parts[0].strip('[]')
                msg = parts[2] if len(parts) > 2 else parts[1]
                level_icon = {'INFO': 'ℹ️ ', 'ERROR': '❌', 'WARNING': '⚠️ '}.get(level, '  ')
                return f"{time_str} {level_icon} {color}{msg}{reset}"
        elif 'OpenAI Agents trace' in message:
            return f"{time_str} 🤖 {color}{message}{reset}"
        elif 'Agent run:' in message:
            return f"{time_str}    ↳ {color}{message.strip()}{reset}"
        elif 'Chat completion' in message:
            return f"{time_str}      ↳ {color}{message.strip()}{reset}"
        else:
            # Default formatting
            if message and not message.isspace():
                return f"{time_str}    {color}{message}{reset}"

        return None

    def track(self):
        """Main tracking loop"""
        print("=" * 60)
        print("📡 Tracking Tagger Lambda Logs")
        print("=" * 60)
        print(f"Log group: {self.log_group_name}")
        print("Press Ctrl+C to stop\n")

        # Start from 1 minute ago
        start_time = int((time.time() - 60) * 1000)
        seen_ids = set()

        while self.running:
            try:
                # Get logs
                events = self.get_logs(start_time)

                # Process new events
                new_events = []
                for event in events:
                    event_id = event.get('eventId')
                    if event_id not in seen_ids:
                        seen_ids.add(event_id)
                        new_events.append(event)

                # Display new events
                for event in new_events:
                    formatted = self.format_log_message(event)
                    if formatted:
                        print(formatted)

                    # Update start time for next poll
                    start_time = max(start_time, event['timestamp'] + 1)

                # If we got events, show a separator for clarity
                if new_events and len(new_events) > 5:
                    print("-" * 40)

                # Sleep before next poll (shorter if we just got events)
                sleep_time = 1 if new_events else 2
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error in tracking loop: {e}")
                time.sleep(5)

        print("\n✅ Log tracking stopped")

def main():
    """Main entry point"""
    tracker = TaggerLogTracker()

    print("\n🔍 Looking for recent Langfuse-related logs...")
    print("-" * 40)

    # First show any recent Langfuse logs
    recent_logs = tracker.get_logs(int((time.time() - 300) * 1000))  # Last 5 minutes
    langfuse_found = False

    for event in recent_logs[-20:]:  # Last 20 events
        message = event['message']
        if any(term in message for term in ['LangFuse', 'langfuse', 'observability', 'OPENAI_API_KEY', 'setup_observability']):
            formatted = tracker.format_log_message(event)
            if formatted:
                print(formatted)
                langfuse_found = True

    if not langfuse_found:
        print("  No recent Langfuse-related logs found")

    print("-" * 40)
    print("\nStarting continuous tracking...\n")

    # Start continuous tracking
    tracker.track()

if __name__ == "__main__":
    main()