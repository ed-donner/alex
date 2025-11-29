"""
Cloud SQL PostgreSQL Client Wrapper
Provides a simple interface for database operations compatible with DataAPIClient
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import date, datetime
from decimal import Decimal

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Try to import PostgreSQL libraries
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 not available, falling back to pg8000")
    try:
        import pg8000
        PG8000_AVAILABLE = True
    except ImportError:
        PG8000_AVAILABLE = False
        logger.error("Neither psycopg2 nor pg8000 available. Install one: uv add psycopg2-binary")

# For Cloud Run, use Cloud SQL connector
try:
    from google.cloud.sql.connector import Connector
    CLOUD_SQL_CONNECTOR_AVAILABLE = True
except ImportError:
    try:
        # Try alternative import path
        from cloud_sql_python_connector import Connector
        CLOUD_SQL_CONNECTOR_AVAILABLE = True
    except ImportError:
        CLOUD_SQL_CONNECTOR_AVAILABLE = False


class CloudSQLClient:
    """Wrapper for Cloud SQL PostgreSQL to simplify database operations"""

    def __init__(
        self,
        instance_connection_name: str = None,
        database: str = None,
        user: str = None,
        password: str = None,
        host: str = None,
        port: int = None,
    ):
        """
        Initialize Cloud SQL client

        Args:
            instance_connection_name: Cloud SQL connection name (for Cloud Run)
            database: Database name (or from env DATABASE_NAME)
            user: Database user (or from env DATABASE_USER)
            password: Database password (or from env, or from Secret Manager)
            host: Database host (for local development via proxy)
            port: Database port (for local development via proxy)
        """
        # Get configuration from environment or parameters
        self.instance_connection_name = instance_connection_name or os.environ.get("INSTANCE_CONNECTION_NAME")
        self.database = database or os.environ.get("DATABASE_NAME", "alex")
        self.user = user or os.environ.get("DATABASE_USER", "alex_app")
        
        # Get password from Secret Manager if secret ID is provided
        password_secret_id = os.environ.get("DB_PASSWORD_SECRET_ID")
        if password_secret_id and not password:
            try:
                from google.cloud import secretmanager
                client = secretmanager.SecretManagerServiceClient()
                project_id = os.environ.get("GCP_PROJECT_ID")
                name = f"projects/{project_id}/secrets/{password_secret_id}/versions/latest"
                response = client.access_secret_version(request={"name": name})
                password = response.payload.data.decode("UTF-8")
            except Exception as e:
                logger.warning(f"Could not get password from Secret Manager: {e}")
        
        self.password = password or os.environ.get("DB_PASSWORD")
        
        # For local development via Cloud SQL Proxy
        # Only use DB_HOST if explicitly set (for local dev with proxy)
        # In Cloud Run, DB_HOST should NOT be set, allowing Cloud SQL connector to be used
        db_host_env = os.environ.get("DB_HOST")
        if host:
            self.host = host
        elif db_host_env:
            self.host = db_host_env
        else:
            self.host = None  # No host set = use Cloud SQL connector
        
        if self.host:
            self.port = port or int(os.environ.get("DB_PORT", "5432"))
        else:
            self.port = None  # Port not needed for Cloud SQL connector
        
        # Determine connection mode
        # Use Cloud SQL connector if:
        # 1. Connector is available
        # 2. Instance connection name is set
        # 3. Host is NOT explicitly set (meaning we're in Cloud Run, not local dev)
        self.use_cloud_sql_connector = (
            CLOUD_SQL_CONNECTOR_AVAILABLE and 
            self.instance_connection_name and 
            not self.host  # If host is explicitly set, use direct connection (local dev)
        )
        
        # Initialize connection pool
        self._connection = None
        self._connector = None
        
        if not self.password:
            raise ValueError(
                "Missing required database password. "
                "Set DB_PASSWORD environment variable or DB_PASSWORD_SECRET_ID for Secret Manager."
            )

    def _get_connection(self):
        """Get database connection"""
        if self._connection:
            try:
                # Test if connection is still alive
                if hasattr(self._connection, 'closed') and not self._connection.closed:
                    return self._connection
            except:
                pass
        
        if self.use_cloud_sql_connector:
            # Use Cloud SQL connector for Cloud Run
            if not self._connector:
                self._connector = Connector()
            
            import pg8000
            conn = self._connector.connect(
                self.instance_connection_name,
                "pg8000",
                user=self.user,
                password=self.password,
                db=self.database,
            )
            self._connection = conn
            return conn
        else:
            # Use direct connection (local development via proxy or private IP)
            if PSYCOPG2_AVAILABLE:
                conn = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                )
                self._connection = conn
                return conn
            elif PG8000_AVAILABLE:
                conn = pg8000.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                )
                self._connection = conn
                return conn
            else:
                raise ImportError("Neither psycopg2 nor pg8000 is available. Install one: uv add psycopg2-binary")

    def execute(self, sql: str, parameters: List[Dict] = None) -> Dict:
        """
        Execute a SQL statement

        Args:
            sql: SQL statement to execute
            parameters: Optional list of parameters (DataAPIClient format)

        Returns:
            Response dict with 'records' and 'columnMetadata' (compatible with DataAPIClient)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Convert DataAPIClient parameter format to PostgreSQL format
            if parameters:
                # Extract parameter values and names
                param_dict = {}
                param_order = []  # Track parameter order for positional params
                for param in parameters:
                    name = param.get('name', '')
                    value_obj = param.get('value', {})
                    value = self._extract_param_value(value_obj)
                    # Remove : prefix if present
                    param_name = name.lstrip(':')
                    param_dict[param_name] = value
                    param_order.append(param_name)
                
                # Determine which driver is being used
                # If using Cloud SQL connector, it uses pg8000 which only supports %s
                # If using direct connection, check if psycopg2 is available
                use_pg8000 = self.use_cloud_sql_connector or not PSYCOPG2_AVAILABLE
                
                if use_pg8000:
                    # pg8000 only supports %s positional parameters
                    # Convert :param_name to %s and build positional parameter list
                    sql_adapted = sql
                    param_list = []
                    for param_name in param_order:
                        # Replace :param_name with %s
                        sql_adapted = sql_adapted.replace(f":{param_name}", "%s", 1)
                        param_list.append(param_dict[param_name])
                    cursor.execute(sql_adapted, param_list)
                else:
                    # psycopg2 supports named parameters %(name)s
                    sql_adapted = sql
                    for param_name in param_dict.keys():
                        sql_adapted = sql_adapted.replace(f":{param_name}", f"%({param_name})s")
                    cursor.execute(sql_adapted, param_dict)
            else:
                cursor.execute(sql)
            
            # Get results
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                records = cursor.fetchall()
                
                # Convert to DataAPIClient format
                result_records = []
                for record in records:
                    row = []
                    for i, col in enumerate(columns):
                        value = record[i]
                        # Convert to DataAPIClient field format
                        field = self._value_to_field(value)
                        row.append(field)
                    result_records.append(row)
                
                column_metadata = [{'name': col} for col in columns]
                
                return {
                    'records': result_records,
                    'columnMetadata': column_metadata,
                    'numberOfRecordsUpdated': cursor.rowcount if cursor.rowcount else 0
                }
            else:
                # No results (INSERT, UPDATE, DELETE)
                return {
                    'records': [],
                    'columnMetadata': [],
                    'numberOfRecordsUpdated': cursor.rowcount if cursor.rowcount else 0
                }
        except Exception as e:
            # Rollback on error to clear failed transaction state
            try:
                conn.rollback()
            except:
                pass
            raise
        finally:
            cursor.close()
            # Only commit if no exception occurred
            try:
                conn.commit()
            except Exception as e:
                # If commit fails (e.g., already rolled back), that's okay
                logger.warning(f"Commit failed (may have been rolled back): {e}")

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
        
        # Build placeholders with type casting where needed
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
                set_parts.append(f"{col} = :{val}::numeric")
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
        """Begin a database transaction (returns transaction ID for compatibility)"""
        conn = self._get_connection()
        # For PostgreSQL, we use savepoints or just track the connection
        # Return a dummy ID for compatibility
        return "txn_1"

    def commit_transaction(self, transaction_id: str):
        """Commit a database transaction"""
        conn = self._get_connection()
        conn.commit()

    def rollback_transaction(self, transaction_id: str):
        """Rollback a database transaction"""
        conn = self._get_connection()
        conn.rollback()

    def _build_parameters(self, data: Dict) -> List[Dict]:
        """Convert dictionary to DataAPIClient parameter format"""
        if not data:
            return []
        
        parameters = []
        for key, value in data.items():
            param = {"name": key}
            param["value"] = self._value_to_field(value)
            parameters.append(param)
        
        return parameters

    def _value_to_field(self, value: Any) -> Dict:
        """Convert Python value to DataAPIClient field format"""
        if value is None:
            return {"isNull": True}
        elif isinstance(value, bool):
            return {"booleanValue": value}
        elif isinstance(value, int):
            return {"longValue": value}
        elif isinstance(value, float):
            return {"doubleValue": value}
        elif isinstance(value, Decimal):
            return {"stringValue": str(value)}
        elif isinstance(value, (date, datetime)):
            return {"stringValue": value.isoformat()}
        elif isinstance(value, dict):
            return {"stringValue": json.dumps(value)}
        elif isinstance(value, list):
            return {"stringValue": json.dumps(value)}
        else:
            return {"stringValue": str(value)}

    def _extract_param_value(self, value_obj: Dict) -> Any:
        """Extract Python value from DataAPIClient parameter format"""
        if value_obj.get("skip_json_decode"):
            return value_obj.get("stringValue")
        if value_obj.get("isNull"):
            return None
        elif "booleanValue" in value_obj:
            return value_obj["booleanValue"]
        elif "longValue" in value_obj:
            return value_obj["longValue"]
        elif "doubleValue" in value_obj:
            return value_obj["doubleValue"]
        elif "stringValue" in value_obj:
            value = value_obj["stringValue"]
            # Try to parse JSON if it looks like JSON
            if value and value[0] in ["{", "["]:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            return value
        else:
            return None

    def _extract_value(self, field: Dict) -> Any:
        """Extract value from DataAPIClient field response"""
        return self._extract_param_value(field)

