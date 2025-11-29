import os
import json
from pathlib import Path
from google.cloud import pubsub_v1
from dotenv import load_dotenv

# Load .env file from project root (alex-gcp/.env)
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path, override=True)

# Get project ID from environment or gcloud config
project_id = os.getenv('GCP_PROJECT_ID') or os.getenv('PROJECT_ID')

if not project_id:
    # Try to get from gcloud config
    import subprocess
    try:
        result = subprocess.run(
            ['gcloud', 'config', 'get-value', 'project'],
            capture_output=True,
            text=True,
            check=True
        )
        project_id = result.stdout.strip()
        print(f"[WARNING] GCP_PROJECT_ID not set, using gcloud default: {project_id}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[ERROR] GCP_PROJECT_ID not set and gcloud not available")
        print("   Set GCP_PROJECT_ID in .env file or run: gcloud config set project YOUR_PROJECT_ID")
        exit(1)

topic_name = os.getenv('PUBSUB_TOPIC', 'alex-job-queue')

print(f"Using project: {project_id}")
print(f"Using topic: {topic_name}")

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(project_id, topic_name)

# Publish a test message
message_data = {
    'job_id': 'test-123',
    'clerk_user_id': 'test-user',
    'analysis_type': 'portfolio',
    'options': {}
}

try:
    future = publisher.publish(
        topic_path,
        json.dumps(message_data).encode('utf-8')
    )
    
    message_id = future.result()
    print(f"[SUCCESS] Published message: {message_id}")
    print(f"   Topic: {topic_path}")
    print(f"   Message: {message_data}")
except Exception as e:
    print(f"[ERROR] Error publishing message: {e}")
    print(f"\nTroubleshooting:")
    print(f"   1. Verify topic exists: gcloud pubsub topics list --project={project_id}")
    print(f"   2. Check IAM permissions: gcloud pubsub topics get-iam-policy {topic_name} --project={project_id}")
    print(f"   3. Verify GCP_PROJECT_ID in .env file: {project_id}")
    raise