#!/usr/bin/env python3
"""
Simple migration runner that executes statements one by one
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Ensure we can import the shared Cloud SQL client
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
import sys
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cloudsql_client import CloudSQLClient

# Load environment variables
load_dotenv(override=True)

# Initialize Cloud SQL client (reads env vars for host/instance/user/password)
client = CloudSQLClient(
    instance_connection_name=os.environ.get("INSTANCE_CONNECTION_NAME"),
    database=os.environ.get("DATABASE_NAME", "alex"),
    user=os.environ.get("DATABASE_USER", "alex_app"),
    password=os.environ.get("DB_PASSWORD"),
    host=os.environ.get("DB_HOST"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

# Read migration file
with open("migrations/001_schema.sql") as f:
    sql = f.read()

# Define statements in order (since splitting is complex)
statements = [
    # Extension
    'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"',
    # Tables
    """CREATE TABLE IF NOT EXISTS users (
        clerk_user_id VARCHAR(255) PRIMARY KEY,
        display_name VARCHAR(255),
        years_until_retirement INTEGER,
        target_retirement_income DECIMAL(12,2),
        asset_class_targets JSONB DEFAULT '{"equity": 70, "fixed_income": 30}',
        region_targets JSONB DEFAULT '{"north_america": 50, "international": 50}',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS instruments (
        symbol VARCHAR(20) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        instrument_type VARCHAR(50),
        current_price DECIMAL(12,4),
        allocation_regions JSONB DEFAULT '{}',
        allocation_sectors JSONB DEFAULT '{}',
        allocation_asset_class JSONB DEFAULT '{}',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS accounts (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        clerk_user_id VARCHAR(255) REFERENCES users(clerk_user_id) ON DELETE CASCADE,
        account_name VARCHAR(255) NOT NULL,
        account_purpose TEXT,
        cash_balance DECIMAL(12,2) DEFAULT 0,
        cash_interest DECIMAL(5,4) DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS positions (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
        symbol VARCHAR(20) REFERENCES instruments(symbol),
        quantity DECIMAL(20,8) NOT NULL,
        as_of_date DATE DEFAULT CURRENT_DATE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(account_id, symbol)
    )""",
    """CREATE TABLE IF NOT EXISTS jobs (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        clerk_user_id VARCHAR(255) REFERENCES users(clerk_user_id) ON DELETE CASCADE,
        job_type VARCHAR(50) NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        request_payload JSONB,
        report_payload JSONB,
        charts_payload JSONB,
        retirement_payload JSONB,
        summary_payload JSONB,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    # Indexes
    "CREATE INDEX IF NOT EXISTS idx_accounts_user ON accounts(clerk_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_positions_account ON positions(account_id)",
    "CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(clerk_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
    # Function for timestamps
    """CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql""",
    # Triggers
    """CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()""",
    """CREATE TRIGGER update_instruments_updated_at BEFORE UPDATE ON instruments
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()""",
    """CREATE TRIGGER update_accounts_updated_at BEFORE UPDATE ON accounts
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()""",
    """CREATE TRIGGER update_positions_updated_at BEFORE UPDATE ON positions
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()""",
    """CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()""",
]

print("🚀 Running database migrations...")
print("=" * 50)

success_count = 0
error_count = 0

for i, stmt in enumerate(statements, 1):
    # Get a description of what we're creating
    stmt_type = "statement"
    if "CREATE TABLE" in stmt.upper():
        stmt_type = "table"
    elif "CREATE INDEX" in stmt.upper():
        stmt_type = "index"
    elif "CREATE TRIGGER" in stmt.upper():
        stmt_type = "trigger"
    elif "CREATE FUNCTION" in stmt.upper():
        stmt_type = "function"
    elif "CREATE EXTENSION" in stmt.upper():
        stmt_type = "extension"

    # First non-empty line for display
    first_line = next(l for l in stmt.split("\n") if l.strip())[:60]
    print(f"\n[{i}/{len(statements)}] Creating {stmt_type}...")
    print(f"    {first_line}...")

    try:
        client.execute(sql=stmt)
        print(f"    ✅ Success")
        success_count += 1

    except Exception as e:
        error_msg = str(e)
        if "already exists" in error_msg.lower():
            print(f"    ⚠️  Already exists (skipping)")
            success_count += 1
        else:
            print(f"    ❌ Error: {error_msg[:100]}")
            error_count += 1

print("\n" + "=" * 50)
print(f"Migration complete: {success_count} successful, {error_count} errors")

if error_count == 0:
    print("\n✅ All migrations completed successfully!")
    print("\n📝 Next steps:")
    print("1. Load seed data: uv run seed_data.py")
    print("2. Test database operations: uv run test_db.py")
else:
    print(f"\n⚠️  Some statements failed. Check errors above.")
