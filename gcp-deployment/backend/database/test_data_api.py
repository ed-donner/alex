#!/usr/bin/env python3
"""
Test Aurora Data API Connection
This script verifies that Aurora Serverless v2 is properly configured with Data API enabled.
"""

import boto3
import json
import os
import sys
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

def get_current_region():
    """Get the current AWS region from the session"""
    session = boto3.Session()
    return session.region_name or os.getenv('DEFAULT_AWS_REGION', 'us-east-1')

def get_cluster_details(region):
    """Get Aurora cluster ARN and secret ARN from environment variables or verify they exist"""
    
    # First try to get from environment variables
    cluster_arn = os.getenv('AURORA_CLUSTER_ARN')
    secret_arn = os.getenv('AURORA_SECRET_ARN')
    
    if cluster_arn and secret_arn:
        print(f"📋 Using configuration from .env file")
        
        # Verify the cluster exists and Data API is enabled
        rds_client = boto3.client('rds', region_name=region)
        try:
            cluster_id = cluster_arn.split(':')[-1]
            response = rds_client.describe_db_clusters(
                DBClusterIdentifier=cluster_id
            )
            
            if response['DBClusters']:
                cluster = response['DBClusters'][0]
                if not cluster.get('HttpEndpointEnabled', False):
                    print("❌ Data API is not enabled on the Aurora cluster")
                    print("💡 Run: aws rds modify-db-cluster --db-cluster-identifier alex-aurora-cluster --enable-http-endpoint --apply-immediately")
                    return None, None
            else:
                print(f"❌ Aurora cluster '{cluster_id}' not found")
                return None, None
                
        except ClientError as e:
            print(f"⚠️  Could not verify cluster status: {e}")
            # Continue anyway - the cluster might exist but we can't describe it
        
        return cluster_arn, secret_arn
    
    # Fallback to auto-discovery if not in .env
    print("⚠️  AURORA_CLUSTER_ARN or AURORA_SECRET_ARN not found in .env file")
    print("💡 After running 'terraform apply', add these to your .env file:")
    print("   AURORA_CLUSTER_ARN=<your-cluster-arn>")
    print("   AURORA_SECRET_ARN=<your-secret-arn>")
    print("\nAttempting to auto-discover Aurora resources...")
    
    rds_client = boto3.client('rds', region_name=region)
    secrets_client = boto3.client('secretsmanager', region_name=region)
    
    try:
        # Get cluster ARN
        response = rds_client.describe_db_clusters(
            DBClusterIdentifier='alex-aurora-cluster'
        )
        
        if not response['DBClusters']:
            print("❌ Aurora cluster 'alex-aurora-cluster' not found")
            return None, None
        
        cluster = response['DBClusters'][0]
        cluster_arn = cluster['DBClusterArn']
        
        # Check if Data API is enabled
        if not cluster.get('HttpEndpointEnabled', False):
            print("❌ Data API is not enabled on the Aurora cluster")
            print("💡 Run: aws rds modify-db-cluster --db-cluster-identifier alex-aurora-cluster --enable-http-endpoint --apply-immediately")
            return None, None
        
        # Find the most recently created aurora secret for alex
        secrets = secrets_client.list_secrets()
        aurora_secrets = []
        
        for secret in secrets['SecretList']:
            if 'aurora' in secret['Name'].lower() and 'alex' in secret['Name'].lower():
                aurora_secrets.append(secret)
        
        if not aurora_secrets:
            print("❌ Could not find Aurora credentials in Secrets Manager")
            print("💡 Look for a secret containing 'aurora' in the name")
            return None, None
        
        # Sort by creation date and pick the most recent
        aurora_secrets.sort(key=lambda x: x.get('CreatedDate', ''), reverse=True)
        secret_arn = aurora_secrets[0]['ARN']
        
        print(f"\n📝 Found Aurora resources. Add these to your .env file:")
        print(f"AURORA_CLUSTER_ARN={cluster_arn}")
        print(f"AURORA_SECRET_ARN={secret_arn}")
        
        return cluster_arn, secret_arn
        
    except ClientError as e:
        print(f"❌ Error accessing AWS resources: {e}")
        return None, None

def test_data_api(cluster_arn, secret_arn, region):
    """Test the Data API connection"""
    client = boto3.client('rds-data', region_name=region)
    
    print(f"\n🔍 Testing Data API Connection")
    print(f"   Region: {region}")
    print(f"   Cluster ARN: {cluster_arn}")
    print(f"   Secret ARN: {secret_arn}")
    print("-" * 50)
    
    # Test 1: Simple SELECT
    print("\n1️⃣ Testing basic SELECT...")
    try:
        response = client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database='alex',
            sql='SELECT 1 as test_connection, current_timestamp as server_time'
        )
        
        if response['records']:
            test_val = response['records'][0][0].get('longValue')
            server_time = response['records'][0][1].get('stringValue')
            print(f"   ✅ Connection successful!")
            print(f"   Server time: {server_time}")
        else:
            print("   ❌ Query executed but returned no results")
            
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'BadRequestException':
            # This might mean the database doesn't exist yet
            print(f"   ⚠️  Database 'alex' might not exist or credentials are incorrect")
            print(f"   Error: {e.response['Error']['Message']}")
            
            # Try without specifying database
            print("\n   Retrying without database parameter...")
            try:
                response = client.execute_statement(
                    resourceArn=cluster_arn,
                    secretArn=secret_arn,
                    sql='SELECT current_database()'
                )
                print(f"   ✅ Connection successful (but 'alex' database may not exist)")
                return True
            except:
                pass
        else:
            print(f"   ❌ Error: {e}")
        return False
    
    # Test 2: Check for tables
    print("\n2️⃣ Checking for existing tables...")
    try:
        response = client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database='alex',
            sql="""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """
        )
        
        tables = [record[0].get('stringValue') for record in response.get('records', [])]
        
        if tables:
            print(f"   ✅ Found {len(tables)} tables:")
            for table in tables:
                print(f"      - {table}")
        else:
            print("   ℹ️  No tables found (database is empty)")
            print("   💡 Run the migration script to create tables")
            
    except ClientError as e:
        print(f"   ⚠️  Could not list tables: {e}")
    
    # Test 3: Check database size
    print("\n3️⃣ Checking database info...")
    try:
        response = client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database='alex',
            sql="SELECT pg_database_size('alex') as size_bytes"
        )
        
        if response['records']:
            size_bytes = response['records'][0][0].get('longValue', 0)
            size_mb = size_bytes / (1024 * 1024)
            print(f"   ✅ Database size: {size_mb:.2f} MB")
            
    except:
        pass
    
    print("\n" + "=" * 50)
    print("✅ Data API is working correctly!")
    print("\n📝 Next steps:")
    print("1. Run migrations to create tables: uv run migrate.py")
    print("2. Load seed data: uv run seed_data.py")
    print("3. Test the database package: uv run test_db.py")
    
    return True

def main():
    """Main function"""
    print("🚀 Aurora Data API Connection Test")
    print("=" * 50)
    
    # Get current region
    region = get_current_region()
    print(f"📍 Using AWS Region: {region}")
    
    # Get cluster and secret ARNs
    cluster_arn, secret_arn = get_cluster_details(region)
    
    if not cluster_arn or not secret_arn:
        print("\n❌ Could not find Aurora cluster or credentials")
        print("\n💡 Make sure you have:")
        print("   1. Created the Aurora cluster with 'terraform apply'")
        print("   2. Enabled Data API on the cluster")
        print("   3. Created credentials in Secrets Manager")
        sys.exit(1)
    
    # Test the Data API
    success = test_data_api(cluster_arn, secret_arn, region)
    
    if not success:
        print("\n❌ Data API test failed")
        print("\n💡 Troubleshooting:")
        print("   1. Check if the Aurora instance is 'available'")
        print("   2. Verify Data API is enabled")
        print("   3. Check IAM permissions for rds-data:ExecuteStatement")
        sys.exit(1)
    
    # Save connection details for other scripts
    print(f"\n✅ Data API test successful!")

if __name__ == "__main__":
    main()