#!/usr/bin/env python3
"""
Simple migration runner that executes statements one by one
"""

import os
import sys
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from loguru import logger

def load_migration_statements(migrations_dir: Path = None) -> list:
    """
    Dynamically reads and parses all SQL statements from .sql files in migrations directory.
    Handles PL/pgSQL dollar-quoted blocks ($$ ... $$) and semicolons.
    """
    if migrations_dir is None:
        migrations_dir = Path(__file__).parent / "migrations"

    statements = []
    if not migrations_dir.exists():
        return statements

    sql_files = sorted(migrations_dir.glob("*.sql"))

    for sql_file in sql_files:
        with open(sql_file, encoding="utf-8") as f:
            content = f.read()

        # Remove single-line comments (-- ...)
        lines = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            lines.append(line)
        cleaned_content = "\n".join(lines)

        # Parse statements handling $$ blocks
        current_parts = []
        for part in cleaned_content.split(";"):
            if not part.strip() and not current_parts:
                continue

            current_parts.append(part)
            combined = ";".join(current_parts)

            # Count $$ occurrences to prevent splitting inside PL/pgSQL function bodies
            if combined.count("$$") % 2 != 0:
                continue

            statement_text = combined.strip()
            if statement_text:
                statements.append(statement_text)
            current_parts = []

    return statements


# Fallback/dynamic STATEMENTS loading
STATEMENTS = load_migration_statements()
statements = STATEMENTS

# Load environment variables once at module import
load_dotenv(override=True)


def run_migrations(custom_statements: list = None):
    """
    Executes database migration statements from .sql files against Aurora Serverless v2 PostgreSQL.
    """
    # Get config from environment
    cluster_arn = os.environ.get("AURORA_CLUSTER_ARN")
    secret_arn = os.environ.get("AURORA_SECRET_ARN")
    database = os.environ.get("AURORA_DATABASE", "alex")
    region = os.environ.get("DEFAULT_AWS_REGION", "us-east-1")

    if not cluster_arn or not secret_arn:
        raise ValueError("Missing AURORA_CLUSTER_ARN or AURORA_SECRET_ARN in environment variables")

    client = boto3.client("rds-data", region_name=region)

    target_statements = custom_statements if custom_statements is not None else load_migration_statements()

    logger.info("Applying database schema statements...")

    success_count = 0
    error_count = 0

    for i, stmt in enumerate(target_statements, 1):
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
        logger.info(f"[{i}/{len(target_statements)}] Creating {stmt_type}: {first_line}...")

        try:
            client.execute_statement(
                resourceArn=cluster_arn, secretArn=secret_arn, database=database, sql=stmt
            )
            logger.info(f"Successfully applied {stmt_type}")
            success_count += 1

        except ClientError as e:
            error_msg = e.response.get("Error", {}).get("Message", "")
            if "already exists" in error_msg.lower():
                logger.warning(f"Statement already exists, skipping: {first_line}")
                success_count += 1
            else:
                logger.error(f"Error executing statement: {error_msg[:100]}")
                error_count += 1

    logger.info(f"Schema setup complete: {success_count} successful, {error_count} errors")

    if error_count == 0:
        logger.info("All schema statements completed successfully!")
    else:
        logger.warning("Some schema statements failed. Check log output above.")

    return success_count, error_count


if __name__ == "__main__":
    run_migrations()

