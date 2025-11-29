"""
Lambda function for searching S3 Vectors.
"""

import json
import os
import boto3

# Environment variables
VECTOR_BUCKET = os.environ.get('VECTOR_BUCKET', 'alex-vectors')
SAGEMAKER_ENDPOINT = os.environ.get('SAGEMAKER_ENDPOINT')
INDEX_NAME = os.environ.get('INDEX_NAME', 'financial-research')

# Initialize AWS clients
sagemaker_runtime = boto3.client('sagemaker-runtime')
s3_vectors = boto3.client('s3vectors')


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


def lambda_handler(event, context):
    """
    Search handler.
    Expects JSON body with:
    {
        "query": "Search query text",
        "k": 5  # Optional, defaults to 5
    }
    """
    # Parse the request body
    if isinstance(event.get('body'), str):
        body = json.loads(event['body'])
    else:
        body = event.get('body', {})
    
    query_text = body.get('query')
    k = body.get('k', 5)
    
    if not query_text:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing required field: query'})
        }
    
    # Get embedding for query
    print(f"Getting embedding for query: {query_text}")
    query_embedding = get_embedding(query_text)
    
    # Search S3 Vectors
    print(f"Searching in bucket: {VECTOR_BUCKET}, index: {INDEX_NAME}")
    response = s3_vectors.query_vectors(
        vectorBucketName=VECTOR_BUCKET,
        indexName=INDEX_NAME,
        queryVector={"float32": query_embedding},
        topK=k,
        returnDistance=True,
        returnMetadata=True
    )
    
    # Format results
    results = []
    for vector in response.get('vectors', []):
        results.append({
            'id': vector['key'],
            'score': vector.get('distance', 0),
            'text': vector.get('metadata', {}).get('text', ''),
            'metadata': vector.get('metadata', {})
        })
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'results': results,
            'count': len(results)
        })
    }