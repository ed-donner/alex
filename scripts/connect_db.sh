#!/usr/bin/env bash
# ==============================================================================
# Alex Financial Advisor - Database Helper & Tunnel Script
# Connects to Aurora PostgreSQL via psql or opens a local tunnel
# ==============================================================================

set -e

REGION="us-west-2"
CLUSTER_ID="alex-aurora-cluster"

echo "🔍 Fetching Aurora PostgreSQL details from AWS Secrets Manager ($REGION)..."

# Find secret ARN matching alex-aurora-credentials
SECRET_ARN=$(aws secretsmanager list-secrets \
  --region "$REGION" \
  --query "SecretList[?contains(Name, 'alex-aurora-credentials')].ARN | [0]" \
  --output text)

if [ -z "$SECRET_ARN" ] || [ "$SECRET_ARN" == "None" ]; then
  echo "❌ Error: Database credentials secret not found in Secrets Manager ($REGION)."
  exit 1
fi

# Fetch credentials payload
SECRET_JSON=$(aws secretsmanager get-secret-value \
  --region "$REGION" \
  --secret-id "$SECRET_ARN" \
  --query SecretString \
  --output text)

DB_USER=$(echo "$SECRET_JSON" | jq -r .username)
DB_PASS=$(echo "$SECRET_JSON" | jq -r .password)

# Fetch Aurora Writer Endpoint
DB_HOST=$(aws rds describe-db-clusters \
  --region "$REGION" \
  --db-cluster-identifier "$CLUSTER_ID" \
  --query "DBClusters[0].Endpoint" \
  --output text)

if [ -z "$DB_HOST" ] || [ "$DB_HOST" == "None" ]; then
  echo "❌ Error: Could not determine Aurora cluster endpoint."
  exit 1
fi

echo "=================================================="
echo "✅ Database Credentials Retrieved!"
echo "   Host:     $DB_HOST"
echo "   Port:     5432"
echo "   Database: alex"
echo "   User:     $DB_USER"
echo "=================================================="

# Check if user wants to open an EC2 Instance Connect Endpoint tunnel
if [ "$1" == "--tunnel" ] || [ "$1" == "--eice" ]; then
  EICE_ID=$(aws ec2 describe-instance-connect-endpoints \
    --region "$REGION" \
    --query "InstanceConnectEndpoints[?VpcId=='vpc-0c2611c0821789bca'].InstanceConnectEndpointId | [0]" \
    --output text 2>/dev/null || echo "")

  if [ -z "$EICE_ID" ] || [ "$EICE_ID" == "None" ]; then
    echo "⚠️  No EC2 Instance Connect Endpoint found."
    echo "   Using direct port 5432 connection to host $DB_HOST..."
  else
    echo "🚀 Opening EC2 Instance Connect Tunnel on localhost:5432..."
    echo "   Connect your DBeaver/psql to localhost:5432"
    echo "   Press Ctrl+C to close the tunnel."
    exec aws ec2-instance-connect open-tunnel \
      --region "$REGION" \
      --instance-connect-endpoint-id "$EICE_ID" \
      --private-ip "$DB_HOST" \
      --remote-port 5432 \
      --local-port 5432
  fi
fi

# Default behavior: Launch interactive psql CLI session
if ! command -v psql &> /dev/null; then
  echo "⚠️  psql command not found on your laptop."
  echo "   Install via Homebrew: brew install postgresql@15"
  echo ""
  echo "📋 DBeaver Connection Details:"
  echo "   Host:     $DB_HOST"
  echo "   Port:     5432"
  echo "   Database: alex"
  echo "   User:     $DB_USER"
  echo "   Password: $DB_PASS"
  echo "   SSL Mode: require"
  exit 0
fi

echo "🚀 Launching psql CLI session..."
export PGHOST="$DB_HOST"
export PGPORT="5432"
export PGDATABASE="alex"
export PGUSER="$DB_USER"
export PGPASSWORD="$DB_PASS"
export PGSSLMODE="require"

exec psql
