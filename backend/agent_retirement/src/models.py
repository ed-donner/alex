"""
Database models and query builders
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date
from decimal import Decimal
from .client import DataAPIClient
from .schemas import (
    InstrumentCreate, UserCreate, AccountCreate, 
    PositionCreate, JobCreate, JobUpdate
)


class BaseModel:
    """Base class for database models"""
    
    table_name = None
    
    def __init__(self, db: DataAPIClient):
        self.db = db
        if not self.table_name:
            raise ValueError("table_name must be defined")
    
    def find_by_id(self, id: Any) -> Optional[Dict]:
        """Find a record by ID"""
        sql = f"SELECT * FROM {self.table_name} WHERE id = :id::uuid"
        return self.db.query_one(sql, [{'name': 'id', 'value': {'stringValue': str(id)}}])
    
    def find_all(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Find all records with pagination"""
        sql = f"SELECT * FROM {self.table_name} LIMIT :limit OFFSET :offset"
        params = [
            {'name': 'limit', 'value': {'longValue': limit}},
            {'name': 'offset', 'value': {'longValue': offset}}
        ]
        return self.db.query(sql, params)
    
    def create(self, data: Dict, returning: str = 'id') -> str:
        """Create a new record"""
        return self.db.insert(self.table_name, data, returning=returning)
    
    def update(self, id: Any, data: Dict) -> int:
        """Update a record by ID"""
        return self.db.update(self.table_name, data, "id = :id::uuid", {'id': str(id)})
    
    def delete(self, id: Any) -> int:
        """Delete a record by ID"""
        return self.db.delete(self.table_name, "id = :id::uuid", {'id': str(id)})


class Users(BaseModel):
    """Users table operations"""
    table_name = 'users'
    
    def find_by_clerk_id(self, clerk_user_id: str) -> Optional[Dict]:
        """Find user by Clerk ID"""
        sql = f"SELECT * FROM {self.table_name} WHERE clerk_user_id = :clerk_id"
        params = [{'name': 'clerk_id', 'value': {'stringValue': clerk_user_id}}]
        return self.db.query_one(sql, params)
    
    def create_user(self, clerk_user_id: str, display_name: str = None, 
                   years_until_retirement: int = None,
                   target_retirement_income: Decimal = None) -> str:
        """Create a new user"""
        data = {
            'clerk_user_id': clerk_user_id,
            'display_name': display_name,
            'years_until_retirement': years_until_retirement,
            'target_retirement_income': target_retirement_income
        }
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        return self.db.insert(self.table_name, data, returning='clerk_user_id')


class Instruments(BaseModel):
    """Instruments table operations"""
    table_name = 'instruments'

    def find_all(self, limit: int = None, offset: int = 0) -> List[Dict]:
        """Find all instruments - no limit by default for autocomplete"""
        sql = f"SELECT * FROM {self.table_name} ORDER BY symbol"
        return self.db.query(sql, [])

    def find_by_symbol(self, symbol: str) -> Optional[Dict]:
        """Find instrument by symbol"""
        sql = f"SELECT * FROM {self.table_name} WHERE symbol = :symbol"
        params = [{'name': 'symbol', 'value': {'stringValue': symbol}}]
        return self.db.query_one(sql, params)
    
    def create_instrument(self, instrument: InstrumentCreate) -> str:
        """Create a new instrument with validation"""
        # Validate using Pydantic
        validated = instrument.model_dump()
        
        # Convert allocations to JSON strings for storage
        data = {
            'symbol': validated['symbol'],
            'name': validated['name'],
            'instrument_type': validated['instrument_type'],
            'allocation_regions': validated['allocation_regions'],
            'allocation_sectors': validated['allocation_sectors'],
            'allocation_asset_class': validated['allocation_asset_class']
        }
        
        return self.db.insert(self.table_name, data, returning='symbol')
    
    def find_by_type(self, instrument_type: str) -> List[Dict]:
        """Find all instruments of a specific type"""
        sql = f"SELECT * FROM {self.table_name} WHERE instrument_type = :type ORDER BY symbol"
        params = [{'name': 'type', 'value': {'stringValue': instrument_type}}]
        return self.db.query(sql, params)
    
    def search(self, query: str) -> List[Dict]:
        """Search instruments by symbol or name"""
        sql = f"""
            SELECT * FROM {self.table_name} 
            WHERE LOWER(symbol) LIKE LOWER(:query) 
               OR LOWER(name) LIKE LOWER(:query)
            ORDER BY symbol
            LIMIT 20
        """
        params = [{'name': 'query', 'value': {'stringValue': f'%{query}%'}}]
        return self.db.query(sql, params)


class Accounts(BaseModel):
    """Accounts table operations"""
    table_name = 'accounts'
    
    def find_by_user(self, clerk_user_id: str) -> List[Dict]:
        """Find all accounts for a user"""
        sql = f"""
            SELECT * FROM {self.table_name} 
            WHERE clerk_user_id = :user_id 
            ORDER BY created_at DESC
        """
        params = [{'name': 'user_id', 'value': {'stringValue': clerk_user_id}}]
        return self.db.query(sql, params)
    
    def create_account(self, clerk_user_id: str, account_name: str,
                      account_purpose: str = None, cash_balance: Decimal = Decimal('0'),
                      cash_interest: Decimal = Decimal('0')) -> str:
        """Create a new account"""
        data = {
            'clerk_user_id': clerk_user_id,
            'account_name': account_name,
            'account_purpose': account_purpose,
            'cash_balance': cash_balance,
            'cash_interest': cash_interest
        }
        return self.db.insert(self.table_name, data, returning='id')


class Positions(BaseModel):
    """Positions table operations"""
    table_name = 'positions'
    
    def find_by_account(self, account_id: str) -> List[Dict]:
        """Find all positions in an account"""
        sql = f"""
            SELECT p.*, i.name as instrument_name, i.instrument_type, i.current_price
            FROM {self.table_name} p
            JOIN instruments i ON p.symbol = i.symbol
            WHERE p.account_id = :account_id::uuid
            ORDER BY p.symbol
        """
        params = [{'name': 'account_id', 'value': {'stringValue': account_id}}]
        return self.db.query(sql, params)
    
    def get_portfolio_value(self, account_id: str) -> Dict:
        """Calculate total portfolio value using current prices from instruments table"""
        sql = """
            SELECT 
                COUNT(DISTINCT p.symbol) as num_positions,
                SUM(p.quantity * i.current_price) as total_value,
                SUM(p.quantity) as total_shares
            FROM positions p
            JOIN instruments i ON p.symbol = i.symbol
            WHERE p.account_id = :account_id::uuid
        """
        params = [
            {'name': 'account_id', 'value': {'stringValue': account_id}}
        ]
        result = self.db.query_one(sql, params)
        if result:
            return {
                'num_positions': result.get('num_positions', 0),
                'total_value': float(result.get('total_value', 0)) if result.get('total_value') else 0,
                'total_shares': float(result.get('total_shares', 0)) if result.get('total_shares') else 0
            }
        return {'num_positions': 0, 'total_value': 0, 'total_shares': 0}
    
    def add_position(self, account_id: str, symbol: str, quantity: Decimal) -> str:
        """Add or update a position"""
        # Use UPSERT to handle existing positions
        sql = """
            INSERT INTO positions (account_id, symbol, quantity, as_of_date)
            VALUES (:account_id::uuid, :symbol, :quantity::numeric, :as_of_date::date)
            ON CONFLICT (account_id, symbol) 
            DO UPDATE SET 
                quantity = EXCLUDED.quantity,
                as_of_date = EXCLUDED.as_of_date,
                updated_at = NOW()
            RETURNING id
        """
        params = [
            {'name': 'account_id', 'value': {'stringValue': account_id}},
            {'name': 'symbol', 'value': {'stringValue': symbol}},
            {'name': 'quantity', 'value': {'stringValue': str(quantity)}},
            {'name': 'as_of_date', 'value': {'stringValue': date.today().isoformat()}}
        ]
        response = self.db.execute(sql, params)
        if response.get('records'):
            return response['records'][0][0].get('stringValue')
        return None


class Jobs(BaseModel):
    """Jobs table operations"""
    table_name = 'jobs'
    
    def create_job(self, clerk_user_id: str, job_type: str, 
                  request_payload: Dict = None) -> str:
        """Create a new job"""
        data = {
            'clerk_user_id': clerk_user_id,
            'job_type': job_type,
            'status': 'pending',
            'request_payload': request_payload
        }
        return self.db.insert(self.table_name, data, returning='id')
    
    def update_status(self, job_id: str, status: str, error_message: str = None) -> int:
        """Update job status"""
        data = {'status': status}
        
        if status == 'running':
            data['started_at'] = datetime.utcnow()
        elif status in ['completed', 'failed', 'max_tokens_exceeded']:
            data['completed_at'] = datetime.utcnow()
        
        if error_message:
            data['error_message'] = error_message
        
        return self.db.update(self.table_name, data, "id = :id::uuid", {'id': job_id})
    
    def update_report(self, job_id: str, report_payload: Dict) -> int:
        """Update job with Reporter agent's analysis"""
        data = {'report_payload': report_payload}
        return self.db.update(self.table_name, data, "id = :id::uuid", {'id': job_id})
    
    def update_charts(self, job_id: str, charts_payload: Dict) -> int:
        """Update job with Charter agent's visualization data"""
        data = {'charts_payload': charts_payload}
        return self.db.update(self.table_name, data, "id = :id::uuid", {'id': job_id})
    
    def update_retirement(self, job_id: str, retirement_payload: Dict) -> int:
        """Update job with Retirement agent's projections"""
        data = {'retirement_payload': retirement_payload}
        return self.db.update(self.table_name, data, "id = :id::uuid", {'id': job_id})
    
    def update_summary(self, job_id: str, summary_payload: Dict) -> int:
        """Update job with Planner's final summary"""
        data = {'summary_payload': summary_payload}
        return self.db.update(self.table_name, data, "id = :id::uuid", {'id': job_id})
    
    def find_by_user(self, clerk_user_id: str, status: str = None, 
                    limit: int = 20) -> List[Dict]:
        """Find jobs for a user"""
        if status:
            sql = f"""
                SELECT * FROM {self.table_name}
                WHERE clerk_user_id = :user_id AND status = :status
                ORDER BY created_at DESC
                LIMIT :limit
            """
            params = [
                {'name': 'user_id', 'value': {'stringValue': clerk_user_id}},
                {'name': 'status', 'value': {'stringValue': status}},
                {'name': 'limit', 'value': {'longValue': limit}}
            ]
        else:
            sql = f"""
                SELECT * FROM {self.table_name}
                WHERE clerk_user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
            """
            params = [
                {'name': 'user_id', 'value': {'stringValue': clerk_user_id}},
                {'name': 'limit', 'value': {'longValue': limit}}
            ]
        
        return self.db.query(sql, params)


class Database:
    """Main database interface providing access to all models"""
    
    def __init__(self, cluster_arn: str = None, secret_arn: str = None,
                 database: str = None, region: str = None):
        """Initialize database with all model classes"""
        self.client = DataAPIClient(cluster_arn, secret_arn, database, region)
        
        # Initialize all models
        self.users = Users(self.client)
        self.instruments = Instruments(self.client)
        self.accounts = Accounts(self.client)
        self.positions = Positions(self.client)
        self.jobs = Jobs(self.client)
    
    def execute_raw(self, sql: str, parameters: List[Dict] = None) -> Dict:
        """Execute raw SQL for complex queries"""
        return self.client.execute(sql, parameters)
    
    def query_raw(self, sql: str, parameters: List[Dict] = None) -> List[Dict]:
        """Execute raw SELECT query"""
        return self.client.query(sql, parameters)