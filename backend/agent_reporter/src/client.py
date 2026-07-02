"""
Aurora Data API Client Wrapper
Provides a simple interface for database operations
"""

import boto3
import json
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime
from decimal import Decimal
from botocore.exceptions import ClientError
import logging

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    pass  # dotenv not installed, continue without it

logger = logging.getLogger(__name__)


class DataAPIClient:
    """Wrapper for AWS RDS Data API to simplify database operations"""

    def __init__(
        self,
        cluster_arn: str = None,
        secret_arn: str = None,
        database: str = None,
        region: str = None,
    ):
        """
        Initialize Data API client

        Args:
            cluster_arn: Aurora cluster ARN (or from env AURORA_CLUSTER_ARN)
            secret_arn: Secrets Manager ARN (or from env AURORA_SECRET_ARN)
            database: Database name (or from env AURORA_DATABASE)
            region: AWS region (or from env AWS_REGION)
        """
        self.cluster_arn = cluster_arn or os.environ.get("AURORA_CLUSTER_ARN")
        self.secret_arn = secret_arn or os.environ.get("AURORA_SECRET_ARN")
        self.database = database or os.environ.get("AURORA_DATABASE", "alex")

        if not self.cluster_arn or not self.secret_arn:
            raise ValueError(
                "Missing required Aurora configuration. "
                "Set AURORA_CLUSTER_ARN and AURORA_SECRET_ARN environment variables."
            )

        self.region = os.environ.get("DEFAULT_AWS_REGION", "us-east-1")
        self.client = boto3.client("rds-data", region_name=self.region)

    def execute(self, sql: str, parameters: List[Dict] = None) -> Dict:
        """
        Execute a SQL statement

        Args:
            sql: SQL statement to execute
            parameters: Optional list of parameters for prepared statement

        Returns:
            Response from Data API
        """
        try:
            kwargs = {
                "resourceArn": self.cluster_arn,
                "secretArn": self.secret_arn,
                "database": self.database,
                "sql": sql,
                "includeResultMetadata": True,  # Include column names
            }

            if parameters:
                kwargs["parameters"] = parameters

            response = self.client.execute_statement(**kwargs)
            return response

        except ClientError as e:
            logger.error(f"Database error: {e}")
            raise

    def query(self, sql: str, parameters: List[Dict] = None) -> List[Dict]:
        """
        Execute a SELECT query and return results as list of dicts

        Args:
            sql: SELECT statement
            parameters: Optional parameters

        Returns:
            List of dictionaries with column names as keys
        """
        response = self.execute(sql, parameters)

        if "records" not in response:
            return []

        # Extract column names
        columns = [col["name"] for col in response.get("columnMetadata", [])]

        # Convert records to dictionaries
        results = []
        for record in response["records"]:
            row = {}
            for i, col in enumerate(columns):
                value = self._extract_value(record[i])
                row[col] = value
            results.append(row)

        return results

    def query_one(self, sql: str, parameters: List[Dict] = None) -> Optional[Dict]:
        """
        Execute a SELECT query and return first result

        Args:
            sql: SELECT statement
            parameters: Optional parameters

        Returns:
            Dictionary with column names as keys, or None if no results
        """
        results = self.query(sql, parameters)
        return results[0] if results else None

    def insert(self, table: str, data: Dict, returning: str = None) -> str:
        """
        Insert a record into a table

        Args:
            table: Table name
            data: Dictionary of column names and values
            returning: Column to return (e.g., 'id', 'clerk_user_id')

        Returns:
            Value of returning column if specified
        """
        columns = list(data.keys())
        placeholders = []

        # Check if columns need type casting
        for col in columns:
            if isinstance(data[col], (dict, list)):
                placeholders.append(f":{col}::jsonb")
            elif isinstance(data[col], Decimal):
                placeholders.append(f":{col}::numeric")
            elif isinstance(data[col], date) and not isinstance(data[col], datetime):
                placeholders.append(f":{col}::date")
            elif isinstance(data[col], datetime):
                placeholders.append(f":{col}::timestamp")
            else:
                placeholders.append(f":{col}")

        sql = f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({", ".join(placeholders)})
        """

        # Add RETURNING clause if specified
        if returning:
            sql += f" RETURNING {returning}"

        parameters = self._build_parameters(data)
        response = self.execute(sql, parameters)

        # Return value if RETURNING was used
        if returning and response.get("records"):
            return self._extract_value(response["records"][0][0])
        return None

    def update(self, table: str, data: Dict, where: str, where_params: Dict = None) -> int:
        """
        Update records in a table

        Args:
            table: Table name
            data: Dictionary of columns to update
            where: WHERE clause (without WHERE keyword)
            where_params: Parameters for WHERE clause

        Returns:
            Number of affected rows
        """
        # Build SET clause with type casting where needed
        set_parts = []
        for col, val in data.items():
            if isinstance(val, (dict, list)):
                set_parts.append(f"{col} = :{col}::jsonb")
            elif isinstance(val, Decimal):
                set_parts.append(f"{col} = :{col}::numeric")
            elif isinstance(val, date) and not isinstance(val, datetime):
                set_parts.append(f"{col} = :{col}::date")
            elif isinstance(val, datetime):
                set_parts.append(f"{col} = :{col}::timestamp")
            else:
                set_parts.append(f"{col} = :{col}")

        set_clause = ", ".join(set_parts)

        sql = f"""
            UPDATE {table}
            SET {set_clause}
            WHERE {where}
        """

        # Combine data and where parameters
        all_params = {**data, **(where_params or {})}
        parameters = self._build_parameters(all_params)

        response = self.execute(sql, parameters)
        return response.get("numberOfRecordsUpdated", 0)

    def delete(self, table: str, where: str, where_params: Dict = None) -> int:
        """
        Delete records from a table

        Args:
            table: Table name
            where: WHERE clause (without WHERE keyword)
            where_params: Parameters for WHERE clause

        Returns:
            Number of deleted rows
        """
        sql = f"DELETE FROM {table} WHERE {where}"
        parameters = self._build_parameters(where_params) if where_params else None

        response = self.execute(sql, parameters)
        return response.get("numberOfRecordsUpdated", 0)

    def begin_transaction(self) -> str:
        """Begin a database transaction"""
        response = self.client.begin_transaction(
            resourceArn=self.cluster_arn, secretArn=self.secret_arn, database=self.database
        )
        return response["transactionId"]

    def commit_transaction(self, transaction_id: str):
        """Commit a database transaction"""
        self.client.commit_transaction(
            resourceArn=self.cluster_arn, secretArn=self.secret_arn, transactionId=transaction_id
        )

    def rollback_transaction(self, transaction_id: str):
        """Rollback a database transaction"""
        self.client.rollback_transaction(
            resourceArn=self.cluster_arn, secretArn=self.secret_arn, transactionId=transaction_id
        )

    def _build_parameters(self, data: Dict) -> List[Dict]:
        """Convert dictionary to Data API parameter format"""
        if not data:
            return []

        parameters = []
        for key, value in data.items():
            param = {"name": key}

            if value is None:
                param["value"] = {"isNull": True}
            elif isinstance(value, bool):
                param["value"] = {"booleanValue": value}
            elif isinstance(value, int):
                param["value"] = {"longValue": value}
            elif isinstance(value, float):
                param["value"] = {"doubleValue": value}
            elif isinstance(value, Decimal):
                param["value"] = {"stringValue": str(value)}
            elif isinstance(value, (date, datetime)):
                param["value"] = {"stringValue": value.isoformat()}
            elif isinstance(value, dict):
                param["value"] = {"stringValue": json.dumps(value)}
            elif isinstance(value, list):
                param["value"] = {"stringValue": json.dumps(value)}
            else:
                param["value"] = {"stringValue": str(value)}

            parameters.append(param)

        return parameters

    def _extract_value(self, field: Dict) -> Any:
        """Extract value from Data API field response"""
        if field.get("isNull"):
            return None
        elif "booleanValue" in field:
            return field["booleanValue"]
        elif "longValue" in field:
            return field["longValue"]
        elif "doubleValue" in field:
            return field["doubleValue"]
        elif "stringValue" in field:
            value = field["stringValue"]
            # Try to parse JSON if it looks like JSON
            if value and value[0] in ["{", "["]:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            return value
        elif "blobValue" in field:
            return field["blobValue"]
        else:
            return None
