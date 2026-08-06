"""
Test script for ingesting documents directly to S3 Vectors.
This bypasses API Gateway and tests the S3 Vectors service directly.
"""

import os
import json
import boto3
import uuid
import datetime
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from project root
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path, override=True)

# Get configuration
VECTOR_BUCKET = os.getenv('VECTOR_BUCKET')
SAGEMAKER_ENDPOINT = os.getenv('SAGEMAKER_ENDPOINT', 'alex-embedding-endpoint')
INDEX_NAME = 'financial-research'

if not VECTOR_BUCKET:
    print("Error: Please run Guide 3 Step 4 to save VECTOR_BUCKET to .env")
    exit(1)

# Initialize AWS clients
s3_vectors = boto3.client('s3vectors')
sagemaker_runtime = boto3.client('sagemaker-runtime')

def get_embedding(text):
    """Get embedding vector from SageMaker endpoint."""
    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT,
        ContentType='application/json',
        Body=json.dumps({'inputs': text})
    )
    
    result = json.loads(response['Body'].read().decode())
    # HuggingFace returns nested array [[[embedding]]], extract the actual embedding
    if isinstance(result, list) and len(result) > 0:
        if isinstance(result[0], list) and len(result[0]) > 0:
            if isinstance(result[0][0], list):
                return result[0][0]  # Extract from [[[embedding]]]
            return result[0]  # Extract from [[embedding]]
    return result  # Return as-is if not nested

def ingest_document(text, metadata=None):
    """Ingest a document directly to S3 Vectors."""
    # Get embedding from SageMaker
    print(f"Getting embedding for text: {text[:100]}...")
    embedding = get_embedding(text)
    
    # Generate unique ID for the vector
    vector_id = str(uuid.uuid4())
    
    # Store in S3 Vectors
    print(f"Storing vector in bucket: {VECTOR_BUCKET}, index: {INDEX_NAME}")
    s3_vectors.put_vectors(
        vectorBucketName=VECTOR_BUCKET,
        indexName=INDEX_NAME,
        vectors=[{
            "key": vector_id,
            "data": {"float32": embedding},
            "metadata": {
                "text": text,
                "timestamp": datetime.datetime.utcnow().isoformat(),
                **(metadata or {})  # Include any additional metadata
            }
        }]
    )
    
    return vector_id

def main():
    """Test direct ingestion to S3 Vectors."""
    
    print("Testing S3 Vectors Direct Ingestion")
    print("=" * 60)
    print(f"Bucket: {VECTOR_BUCKET}")
    print(f"Index: {INDEX_NAME}")
    print(f"Embedding Model: {SAGEMAKER_ENDPOINT}")
    print()
    
    # Test documents
    test_docs = [
        {
            'text': "Tesla Inc. (TSLA) is an electric vehicle and clean energy company. It designs, manufactures, and sells electric vehicles, energy storage systems, and solar panels.",
            'metadata': {
                'ticker': 'TSLA',
                'company_name': 'Tesla Inc.',
                'sector': 'Automotive/Energy',
                'source': 'portfolio'
            }
        },
        {
            'text': "Amazon.com Inc. (AMZN) is a multinational technology company focusing on e-commerce, cloud computing (AWS), digital streaming, and artificial intelligence.",
            'metadata': {
                'ticker': 'AMZN',
                'company_name': 'Amazon.com Inc.',
                'sector': 'Technology/Retail',
                'source': 'portfolio'
            }
        },
        {
            'text': "NVIDIA Corporation (NVDA) designs graphics processing units (GPUs) for gaming and professional markets, as well as system on chip units for mobile computing and automotive.",
            'metadata': {
                'ticker': 'NVDA',
                'company_name': 'NVIDIA Corporation',
                'sector': 'Technology/Semiconductors',
                'source': 'portfolio'
            }
        }
    ]
    
    # Ingest each document
    for i, doc in enumerate(test_docs, 1):
        print(f"Ingesting document {i}: {doc['metadata'].get('ticker', 'Unknown')}")
        try:
            doc_id = ingest_document(doc['text'], doc['metadata'])
            print(f"  ✓ Success! Document ID: {doc_id}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
        print()
    
    print("Testing complete!")
    print("\nYour S3 Vectors knowledge base now contains information about:")
    for doc in test_docs:
        print(f"  - {doc['metadata']['company_name']} ({doc['metadata']['ticker']})")
    
    print("\n⏱️  Note: S3 Vectors updates are available immediately.")
    print("   You can run test_search_s3vectors.py right away to search!")

if __name__ == "__main__":
    main()