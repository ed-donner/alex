"""
FastAPI backend for Alex Financial Advisor
Handles all API routes with Clerk JWT authentication
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
import uuid

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from mangum import Mangum
from dotenv import load_dotenv
from pathlib import Path
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials

from src import Database
from src.schemas import (
    UserCreate,
    AccountCreate,
    PositionCreate,
    JobCreate, JobUpdate,
    JobType, JobStatus
)

# Load .env file from project root (alex-gcp/.env)
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path, override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Alex Financial Advisor API",
    description="Backend API for AI-powered financial planning",
    version="1.0.0"
)

# CORS configuration
# Get frontend URL and additional origins
frontend_url = os.getenv("FRONTEND_URL", "")
cors_origins = []
if frontend_url:
    cors_origins.append(frontend_url)
# Add additional origins from env var
additional_origins = os.getenv("CORS_ORIGINS", "").split(",")
cors_origins.extend([origin.strip() for origin in additional_origins if origin.strip()])
# Fallback to localhost for development
if not cors_origins:
    cors_origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handlers for better error messages
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors with user-friendly messages"""
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid input data. Please check your request and try again."}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with improved messages"""
    # Map technical errors to user-friendly messages
    user_friendly_messages = {
        401: "Your session has expired. Please sign in again.",
        403: "You don't have permission to access this resource.",
        404: "The requested resource was not found.",
        429: "Too many requests. Please slow down and try again later.",
        500: "An internal error occurred. Please try again later.",
        503: "The service is temporarily unavailable. Please try again later."
    }

    message = user_friendly_messages.get(exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": message}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors gracefully"""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Our team has been notified."}
    )

# Initialize services
db = Database()

# Pub/Sub client for job queueing
from google.cloud import pubsub_v1

publisher = pubsub_v1.PublisherClient()

# Get project ID from environment or gcloud config
PROJECT_ID = os.getenv('GCP_PROJECT_ID') or os.getenv('PROJECT_ID')
if not PROJECT_ID:
    # Try to get from gcloud config as fallback
    try:
        import subprocess
        result = subprocess.run(
            ['gcloud', 'config', 'get-value', 'project'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        PROJECT_ID = result.stdout.strip()
        logger.info(f"Using gcloud default project: {PROJECT_ID}")
    except Exception:
        logger.warning("GCP_PROJECT_ID not set and could not get from gcloud config")

PUBSUB_TOPIC = os.getenv('PUBSUB_TOPIC', 'alex-job-queue')

# Clerk authentication setup (exactly like saas reference)
clerk_config = ClerkConfig(jwks_url=os.getenv("CLERK_JWKS_URL"))
clerk_guard = ClerkHTTPBearer(clerk_config)

async def get_current_user_id(creds: HTTPAuthorizationCredentials = Depends(clerk_guard)) -> str:
    """Extract user ID from validated Clerk token"""
    # The clerk_guard dependency already validated the token
    # creds.decoded contains the JWT payload
    user_id = creds.decoded["sub"]
    logger.info(f"Authenticated user: {user_id}")
    return user_id

# Request/Response models
class UserResponse(BaseModel):
    user: Dict[str, Any]
    created: bool

class UserUpdate(BaseModel):
    """Update user settings"""
    display_name: Optional[str] = None
    years_until_retirement: Optional[int] = None
    target_retirement_income: Optional[float] = None
    asset_class_targets: Optional[Dict[str, float]] = None
    region_targets: Optional[Dict[str, float]] = None

class AccountUpdate(BaseModel):
    """Update account"""
    account_name: Optional[str] = None
    account_purpose: Optional[str] = None
    cash_balance: Optional[float] = None

class PositionUpdate(BaseModel):
    """Update position"""
    quantity: Optional[float] = None

class AnalyzeRequest(BaseModel):
    analysis_type: str = Field(default="portfolio", description="Type of analysis to perform")
    options: Dict[str, Any] = Field(default_factory=dict, description="Analysis options")

class AnalyzeResponse(BaseModel):
    job_id: str
    message: str

# API Routes

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/user", response_model=UserResponse)
async def get_or_create_user(
    clerk_user_id: str = Depends(get_current_user_id),
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard)
):
    """Get user or create if first time"""

    try:
        # Check if user exists
        user = db.users.find_by_clerk_id(clerk_user_id)

        if user:
            return UserResponse(user=user, created=False)

        # Create new user with defaults from JWT token
        token_data = creds.decoded
        display_name = token_data.get('name') or token_data.get('email', '').split('@')[0] or "New User"

        # Create user with ALL defaults in one operation
        user_data = {
            'clerk_user_id': clerk_user_id,
            'display_name': display_name,
            'years_until_retirement': 20,
            'target_retirement_income': 60000,
            'asset_class_targets': {"equity": 70, "fixed_income": 30},
            'region_targets': {"north_america": 50, "international": 50}
        }

        # Insert directly with all data
        created_clerk_id = db.users.db.insert('users', user_data, returning='clerk_user_id')

        # Fetch the created user
        created_user = db.users.find_by_clerk_id(clerk_user_id)
        logger.info(f"Created new user: {clerk_user_id}")

        return UserResponse(user=created_user, created=True)

    except Exception as e:
        logger.error(f"Error in get_or_create_user: {e}")
        raise HTTPException(status_code=500, detail="Failed to load user profile")

@app.put("/api/user")
async def update_user(user_update: UserUpdate, clerk_user_id: str = Depends(get_current_user_id)):
    """Update user settings"""

    try:
        # Get user
        user = db.users.find_by_clerk_id(clerk_user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update user - users table uses clerk_user_id as primary key
        update_data = user_update.model_dump(exclude_unset=True)

        # Use the database client directly since users table has clerk_user_id as PK
        db.users.db.update(
            'users',
            update_data,
            "clerk_user_id = :clerk_user_id",
            {'clerk_user_id': clerk_user_id}
        )

        # Return updated user
        updated_user = db.users.find_by_clerk_id(clerk_user_id)
        return updated_user

    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/accounts")
async def list_accounts(clerk_user_id: str = Depends(get_current_user_id)):
    """List user's accounts"""

    try:
        # Get accounts for user
        accounts = db.accounts.find_by_user(clerk_user_id)
        return accounts

    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/accounts")
async def create_account(account: AccountCreate, clerk_user_id: str = Depends(get_current_user_id)):
    """Create new account"""

    try:
        # Verify user exists
        user = db.users.find_by_clerk_id(clerk_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Create account
        account_id = db.accounts.create_account(
            clerk_user_id=clerk_user_id,
            account_name=account.account_name,
            account_purpose=account.account_purpose,
            cash_balance=getattr(account, 'cash_balance', Decimal('0'))
        )

        # Return created account
        created_account = db.accounts.find_by_id(account_id)
        return created_account

    except Exception as e:
        logger.error(f"Error creating account: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/accounts/{account_id}")
async def update_account(account_id: str, account_update: AccountUpdate, clerk_user_id: str = Depends(get_current_user_id)):
    """Update account"""

    try:
        # Verify account belongs to user
        account = db.accounts.find_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Verify ownership - accounts table stores clerk_user_id directly
        if account.get('clerk_user_id') != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        # Update account
        update_data = account_update.model_dump(exclude_unset=True)
        db.accounts.update(account_id, update_data)

        # Return updated account
        updated_account = db.accounts.find_by_id(account_id)
        return updated_account

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating account: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: str, clerk_user_id: str = Depends(get_current_user_id)):
    """Delete an account and all its positions"""

    try:
        # Verify account belongs to user
        account = db.accounts.find_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Verify ownership - accounts table stores clerk_user_id directly
        if account.get('clerk_user_id') != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        # Delete all positions first (due to foreign key constraint)
        positions = db.positions.find_by_account(account_id)
        for position in positions:
            db.positions.delete(position['id'])

        # Delete the account
        db.accounts.delete(account_id)

        return {"message": "Account deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/accounts/{account_id}/positions")
async def list_positions(account_id: str, clerk_user_id: str = Depends(get_current_user_id)):
    """Get positions for account"""

    try:
        # Verify account belongs to user
        account = db.accounts.find_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Verify ownership - accounts table stores clerk_user_id directly
        if account.get('clerk_user_id') != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        positions = db.positions.find_by_account(account_id)

        # Format positions with instrument data for frontend
        formatted_positions = []
        for pos in positions:
            # Get full instrument data
            instrument = db.instruments.find_by_symbol(pos['symbol'])
            formatted_positions.append({
                **pos,
                'instrument': instrument
            })

        return {"positions": formatted_positions}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/positions")
async def create_position(position: PositionCreate, clerk_user_id: str = Depends(get_current_user_id)):
    """Create position"""

    try:
        # Verify account belongs to user
        account = db.accounts.find_by_id(position.account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Verify ownership - accounts table stores clerk_user_id directly
        if account.get('clerk_user_id') != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        # Check if instrument exists, if not create it
        instrument = db.instruments.find_by_symbol(position.symbol.upper())
        if not instrument:
            logger.info(f"Creating new instrument: {position.symbol.upper()}")
            # Create a basic instrument entry with default allocations
            # Import the schema from database
            from src.schemas import InstrumentCreate

            # Determine type based on common patterns
            symbol_upper = position.symbol.upper()
            if len(symbol_upper) <= 5 and symbol_upper.isalpha():
                instrument_type = "stock"
            else:
                instrument_type = "etf"

            # Create instrument with basic default allocations
            # These can be updated later by the tagger agent
            new_instrument = InstrumentCreate(
                symbol=symbol_upper,
                name=f"{symbol_upper} - User Added",  # Basic name, can be updated later
                instrument_type=instrument_type,
                current_price=Decimal("0.00"),  # Price will be updated by background processes
                allocation_regions={"north_america": 100.0},  # Default to 100% NA
                allocation_sectors={"other": 100.0},  # Default to 100% other
                allocation_asset_class={"equity": 100.0} if instrument_type == "stock" else {"fixed_income": 100.0}
            )

            db.instruments.create_instrument(new_instrument)

        # Add position
        position_id = db.positions.add_position(
            account_id=position.account_id,
            symbol=position.symbol.upper(),
            quantity=position.quantity
        )

        # Return created position
        created_position = db.positions.find_by_id(position_id)
        return created_position

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating position: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/positions/{position_id}")
async def update_position(position_id: str, position_update: PositionUpdate, clerk_user_id: str = Depends(get_current_user_id)):
    """Update position"""

    try:
        # Get position and verify ownership
        position = db.positions.find_by_id(position_id)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")

        account = db.accounts.find_by_id(position['account_id'])
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Verify ownership - accounts table stores clerk_user_id directly
        if account.get('clerk_user_id') != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        # Update position
        update_data = position_update.model_dump(exclude_unset=True)
        db.positions.update(position_id, update_data)

        # Return updated position
        updated_position = db.positions.find_by_id(position_id)
        return updated_position

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating position: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/positions/{position_id}")
async def delete_position(position_id: str, clerk_user_id: str = Depends(get_current_user_id)):
    """Delete position"""

    try:
        # Get position and verify ownership
        position = db.positions.find_by_id(position_id)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")

        account = db.accounts.find_by_id(position['account_id'])
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Verify ownership - accounts table stores clerk_user_id directly
        if account.get('clerk_user_id') != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        db.positions.delete(position_id)
        return {"message": "Position deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting position: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/instruments")
async def list_instruments(clerk_user_id: str = Depends(get_current_user_id)):
    """Get all available instruments for autocomplete"""

    try:
        instruments = db.instruments.find_all()
        # Return simplified list for autocomplete
        return [
            {
                "symbol": inst["symbol"],
                "name": inst["name"],
                "instrument_type": inst["instrument_type"],
                "current_price": float(inst["current_price"]) if inst.get("current_price") else None
            }
            for inst in instruments
        ]
    except Exception as e:
        logger.error(f"Error fetching instruments: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze", response_model=AnalyzeResponse)
async def trigger_analysis(request: AnalyzeRequest, clerk_user_id: str = Depends(get_current_user_id)):
    """Trigger portfolio analysis"""

    try:
        # Get user
        user = db.users.find_by_clerk_id(clerk_user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Create job
        job_id = db.jobs.create_job(
            clerk_user_id=clerk_user_id,
            job_type="portfolio_analysis",
            request_payload=request.model_dump()
        )

        # Get the created job
        job = db.jobs.find_by_id(job_id)

        # Send to Pub/Sub
        if PROJECT_ID and PUBSUB_TOPIC:
            message_data = {
                'job_id': str(job_id),
                'clerk_user_id': clerk_user_id,
                'analysis_type': request.analysis_type,
                'options': request.options
            }

            try:
                topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC)
                future = publisher.publish(
                    topic_path,
                    json.dumps(message_data).encode('utf-8')
                )
                message_id = future.result()  # Wait for publish to complete
                logger.info(f"Sent analysis job to Pub/Sub: {job_id} (message_id: {message_id})")
            except Exception as e:
                logger.error(f"Error publishing to Pub/Sub: {e}")
                # Don't fail the request, job is already created in DB
                logger.warning(f"Job {job_id} created but not queued to Pub/Sub")
        else:
            logger.warning("GCP_PROJECT_ID or PUBSUB_TOPIC not configured, job created but not queued")

        return AnalyzeResponse(
            job_id=str(job_id),
            message="Analysis started. Check job status for results."
        )

    except Exception as e:
        logger.error(f"Error triggering analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str, clerk_user_id: str = Depends(get_current_user_id)):
    """Get job status and results"""

    try:
        # Get job
        job = db.jobs.find_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Verify job belongs to user - jobs table stores clerk_user_id directly
        if job.get('clerk_user_id') != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        return job

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs")
async def list_jobs(clerk_user_id: str = Depends(get_current_user_id)):
    """List user's analysis jobs"""

    try:
        # Get jobs for this user (with higher limit to avoid missing recent jobs)
        user_jobs = db.jobs.find_by_user(clerk_user_id, limit=100)
        # Sort by created_at descending (most recent first)
        user_jobs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return {"jobs": user_jobs}

    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/reset-accounts")
async def reset_accounts(clerk_user_id: str = Depends(get_current_user_id)):
    """Delete all accounts for the current user"""

    try:
        # Get user
        user = db.users.find_by_clerk_id(clerk_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get all accounts for user
        accounts = db.accounts.find_by_user(clerk_user_id)

        # Delete each account (positions will cascade delete)
        deleted_count = 0
        for account in accounts:
            try:
                # Positions are deleted automatically via CASCADE
                db.accounts.delete(account['id'])
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Could not delete account {account['id']}: {e}")

        return {
            "message": f"Deleted {deleted_count} account(s)",
            "accounts_deleted": deleted_count
        }

    except Exception as e:
        logger.error(f"Error resetting accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/populate-test-data")
async def populate_test_data(clerk_user_id: str = Depends(get_current_user_id)):
    """Populate test data for the current user"""

    try:
        # Get user
        user = db.users.find_by_clerk_id(clerk_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Define missing instruments that might not be in the database
        missing_instruments = {
            "AAPL": {
                "name": "Apple Inc.",
                "type": "stock",
                "current_price": 195.89,
                "allocation_regions": {"north_america": 100},
                "allocation_sectors": {"technology": 100},
                "allocation_asset_class": {"equity": 100}
            },
            "AMZN": {
                "name": "Amazon.com Inc.",
                "type": "stock",
                "current_price": 178.35,
                "allocation_regions": {"north_america": 100},
                "allocation_sectors": {"consumer_discretionary": 100},
                "allocation_asset_class": {"equity": 100}
            },
            "NVDA": {
                "name": "NVIDIA Corporation",
                "type": "stock",
                "current_price": 522.74,
                "allocation_regions": {"north_america": 100},
                "allocation_sectors": {"technology": 100},
                "allocation_asset_class": {"equity": 100}
            },
            "MSFT": {
                "name": "Microsoft Corporation",
                "type": "stock",
                "current_price": 430.82,
                "allocation_regions": {"north_america": 100},
                "allocation_sectors": {"technology": 100},
                "allocation_asset_class": {"equity": 100}
            },
            "GOOGL": {
                "name": "Alphabet Inc. Class A",
                "type": "stock",
                "current_price": 173.69,
                "allocation_regions": {"north_america": 100},
                "allocation_sectors": {"technology": 100},
                "allocation_asset_class": {"equity": 100}
            },
        }

        # Check and add missing instruments
        for symbol, info in missing_instruments.items():
            existing = db.instruments.find_by_symbol(symbol)
            if not existing:
                try:
                    from src.schemas import InstrumentCreate

                    instrument_data = InstrumentCreate(
                        symbol=symbol,
                        name=info["name"],
                        instrument_type=info["type"],
                        current_price=Decimal(str(info["current_price"])),
                        allocation_regions=info["allocation_regions"],
                        allocation_sectors=info["allocation_sectors"],
                        allocation_asset_class=info["allocation_asset_class"]
                    )
                    db.instruments.create_instrument(instrument_data)
                    logger.info(f"Added missing instrument: {symbol}")
                except Exception as e:
                    logger.warning(f"Could not add instrument {symbol}: {e}")

        # Create accounts with test data
        accounts_data = [
            {
                "name": "401k Long-term",
                "purpose": "Primary retirement savings account with employer match",
                "cash": 5000.00,
                "positions": [
                    ("SPY", 150),   # S&P 500 ETF
                    ("VTI", 100),   # Total Stock Market ETF
                    ("BND", 200),   # Bond ETF
                    ("QQQ", 75),    # Nasdaq ETF
                    ("IWM", 50),    # Small Cap ETF
                ]
            },
            {
                "name": "Roth IRA",
                "purpose": "Tax-free retirement growth account",
                "cash": 2500.00,
                "positions": [
                    ("VTI", 80),    # Total Stock Market ETF
                    ("VXUS", 60),   # International Stock ETF
                    ("VNQ", 40),    # Real Estate ETF
                    ("GLD", 25),    # Gold ETF
                    ("TLT", 30),    # Long-term Treasury ETF
                    ("VIG", 45),    # Dividend Growth ETF
                ]
            },
            {
                "name": "Brokerage Account",
                "purpose": "Taxable investment account for individual stocks",
                "cash": 10000.00,
                "positions": [
                    ("TSLA", 15),   # Tesla
                    ("AAPL", 50),   # Apple
                    ("AMZN", 10),   # Amazon
                    ("NVDA", 25),   # Nvidia
                    ("MSFT", 30),   # Microsoft
                    ("GOOGL", 20),  # Google
                ]
            }
        ]

        created_accounts = []
        for account_data in accounts_data:
            # Create account
            account_id = db.accounts.create_account(
                clerk_user_id=clerk_user_id,
                account_name=account_data["name"],
                account_purpose=account_data["purpose"],
                cash_balance=Decimal(str(account_data["cash"]))
            )

            # Add positions
            for symbol, quantity in account_data["positions"]:
                try:
                    db.positions.add_position(
                        account_id=account_id,
                        symbol=symbol,
                        quantity=Decimal(str(quantity))
                    )
                except Exception as e:
                    logger.warning(f"Could not add position {symbol}: {e}")

            created_accounts.append(account_id)

        # Get all accounts with their positions for summary
        all_accounts = []
        for account_id in created_accounts:
            account = db.accounts.find_by_id(account_id)
            positions = db.positions.find_by_account(account_id)
            account['positions'] = positions
            all_accounts.append(account)

        return {
            "message": "Test data populated successfully",
            "accounts_created": len(created_accounts),
            "accounts": all_accounts
        }

    except Exception as e:
        logger.error(f"Error populating test data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Lambda handler
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)