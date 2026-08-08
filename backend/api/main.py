"""
FastAPI backend for Alex Financial Advisor.
App initialization, middleware, error handlers, and controller router inclusions.
"""

import os
import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from mangum import Mangum

from deps import db, sqs_client, SQS_QUEUE_URL, clerk_config, clerk_guard, get_current_user_id, logger
from routers import (
    user_router,
    accounts_router,
    positions_router,
    instruments_router,
    test_data_router,
    analysis_router,
)

# Initialize FastAPI app
app = FastAPI(
    title="Alex Financial Advisor API",
    description="Backend API for AI-powered financial planning",
    version="1.0.0",
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid input data. Please check your request and try again."},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    user_friendly_messages = {
        401: "Your session has expired. Please sign in again.",
        403: "You don't have permission to access this resource.",
        404: "The requested resource was not found.",
        429: "Too many requests. Please slow down and try again later.",
        500: "An internal error occurred. Please try again later.",
        503: "The service is temporarily unavailable. Please try again later.",
    }
    message = user_friendly_messages.get(exc.status_code, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": message})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Our team has been notified."},
    )


# Include Controller Routers
app.include_router(user_router)
app.include_router(accounts_router)
app.include_router(positions_router)
app.include_router(instruments_router)
app.include_router(test_data_router)
app.include_router(analysis_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# Lambda Handler
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)