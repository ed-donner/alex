"""
Test script for searching S3 Vectors.
This demonstrates how to search the indexed documents.
"""

import os
import json
import boto3
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

def list_all_vectors():
    """List all vectors in the index."""
    print(f"Listing vectors in bucket: {VECTOR_BUCKET}, index: {INDEX_NAME}")
    print("=" * 60)
    
    try:
        # S3 Vectors doesn't have a direct list operation, so we'll do a broad search
        # Search for a common term to get some results
        test_embedding = get_embedding("company")
        
        response = s3_vectors.query_vectors(
            vectorBucketName=VECTOR_BUCKET,
            indexName=INDEX_NAME,
            queryVector={"float32": test_embedding},
            topK=10,
            returnDistance=True,
            returnMetadata=True
        )
        
        vectors = response.get('vectors', [])
        print(f"\nFound {len(vectors)} vectors in the index:\n")
        
        for i, vector in enumerate(vectors, 1):
            metadata = vector.get('metadata', {})
            text_preview = metadata.get('text', '')[:100] + '...' if len(metadata.get('text', '')) > 100 else metadata.get('text', '')
            
            print(f"{i}. Vector ID: {vector['key']}")
            if metadata.get('ticker'):
                print(f"   Ticker: {metadata['ticker']}")
            if metadata.get('company_name'):
                print(f"   Company: {metadata['company_name']}")
            if metadata.get('sector'):
                print(f"   Sector: {metadata['sector']}")
            print(f"   Text: {text_preview}")
            print()
            
    except Exception as e:
        print(f"Error listing vectors: {e}")

def search_vectors(query_text, k=5):
    """Search for vectors by query text."""
    print(f"\nSearching for: '{query_text}'")
    print("-" * 40)
    
    try:
        # Get embedding for query
        query_embedding = get_embedding(query_text)
        
        # Search S3 Vectors
        response = s3_vectors.query_vectors(
            vectorBucketName=VECTOR_BUCKET,
            indexName=INDEX_NAME,
            queryVector={"float32": query_embedding},
            topK=k,
            returnDistance=True,
            returnMetadata=True
        )
        
        vectors = response.get('vectors', [])
        print(f"Found {len(vectors)} results:\n")
        
        for vector in vectors:
            metadata = vector.get('metadata', {})
            distance = vector.get('distance', 0)
            
            print(f"Score: {1 - distance:.3f}")  # Convert distance to similarity score
            if metadata.get('company_name'):
                print(f"Company: {metadata['company_name']} ({metadata.get('ticker', 'N/A')})")
            print(f"Text: {metadata.get('text', '')[:200]}...")
            print()
            
    except Exception as e:
        print(f"Error searching: {e}")

def main():
    """Explore the S3 Vectors database."""
    print("=" * 60)
    print("Alex S3 Vectors Database Explorer")
    print("=" * 60)
    print(f"Bucket: {VECTOR_BUCKET}")
    print(f"Index: {INDEX_NAME}")
    print()
    
    # List all vectors
    list_all_vectors()
    
    # Example searches
    print("=" * 60)
    print("Example Semantic Searches")
    print("=" * 60)
    
    # Search for specific concepts
    search_queries = [
        "electric vehicles and sustainable transportation",
        "cloud computing and AWS services",
        "artificial intelligence and GPU computing"
    ]
    
    for query in search_queries:
        search_vectors(query, k=3)
    
    print("\n✨ S3 Vectors provides semantic search - notice how it finds")
    print("   conceptually related documents even with different wording!")

if __name__ == "__main__":
    main()