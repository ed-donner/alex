"""
Tagger Agent - Cloud Run HTTP Server
Classifies financial instruments and updates the database
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, UTC

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# Add parent directories to Python path for imports
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from src import Database
from src.schemas import InstrumentCreate
from agent import tag_instruments, classification_to_db_format
from observability import observe

# Load .env file from project root
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path, override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Alex Tagger Service",
    description="Instrument classification agent",
    version="1.0.0"
)

# Initialize database
db = Database()


async def process_instruments(instruments: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Process and classify instruments asynchronously.
    
    Args:
        instruments: List of instruments to classify
        
    Returns:
        Processing results
    """
    # Run the classification
    logger.info(f"Classifying {len(instruments)} instruments")
    classifications = await tag_instruments(instruments)
    
    # Update database with classifications
    updated = []
    errors = []
    
    for classification in classifications:
        try:
            # Convert to database format
            db_instrument = classification_to_db_format(classification)
            
            # Check if instrument exists
            existing = db.instruments.find_by_symbol(classification.symbol)
            
            if existing:
                # Update existing instrument
                update_data = db_instrument.model_dump()
                # Remove symbol as it's the key
                del update_data['symbol']
                
                rows = db.client.update(
                    'instruments',
                    update_data,
                    "symbol = :symbol",
                    {'symbol': classification.symbol}
                )
                logger.info(f"Updated {classification.symbol} in database ({rows} rows)")
            else:
                # Create new instrument
                db.instruments.create_instrument(db_instrument)
                logger.info(f"Created {classification.symbol} in database")
            
            updated.append(classification.symbol)
            
        except Exception as e:
            logger.error(f"Error updating {classification.symbol}: {e}")
            errors.append({
                'symbol': classification.symbol,
                'error': str(e)
            })
    
    # Prepare response (convert Pydantic models to dicts)
    return {
        'tagged': len(classifications),
        'updated': updated,
        'errors': errors,
        'classifications': [
            {
                'symbol': c.symbol,
                'name': c.name,
                'type': c.instrument_type,
                'current_price': c.current_price,
                'asset_class': c.allocation_asset_class.model_dump(),
                'regions': c.allocation_regions.model_dump(),
                'sectors': c.allocation_sectors.model_dump()
            }
            for c in classifications
        ]
    }


# Request/Response models
class InstrumentsRequest(BaseModel):
    """Request to classify instruments"""
    instruments: List[Dict[str, str]]


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Alex Tagger",
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/health")
async def health():
    """Health check endpoint (alternative)"""
    return {"status": "healthy"}


@app.post("/")
async def handle_classification(request: InstrumentsRequest):
    """
    Handle instrument classification request.
    
    Request body:
    {
        "instruments": [
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF"},
            ...
        ]
    }
    """
    try:
        logger.info(f"Tagger: Received classification request for {len(request.instruments)} instruments")
        
        with observe():
            result = await process_instruments(request.instruments)
        
        return result
        
    except Exception as e:
        logger.error(f"Tagger: Error processing instruments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

