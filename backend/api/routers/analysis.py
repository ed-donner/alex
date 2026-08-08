"""
Analysis & Jobs router handling portfolio analysis triggering and job status lookups.
"""

import json
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

import deps
from deps import get_current_user_id, logger

router = APIRouter(prefix="/api", tags=["Analysis & Jobs"])


class AnalyzeRequest(BaseModel):
    analysis_type: str = Field(default="portfolio", description="Type of analysis to perform")
    options: Dict[str, Any] = Field(default_factory=dict, description="Analysis options")


class AnalyzeResponse(BaseModel):
    job_id: str
    message: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def trigger_analysis(
    request: AnalyzeRequest,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Trigger portfolio analysis"""
    try:
        user = deps.db.users.find_by_clerk_id(clerk_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        job_id = deps.db.jobs.create_job(
            clerk_user_id=clerk_user_id,
            job_type="portfolio_analysis",
            request_payload=request.model_dump(),
        )

        if deps.SQS_QUEUE_URL:
            message = {
                "job_id": str(job_id),
                "clerk_user_id": clerk_user_id,
                "analysis_type": request.analysis_type,
                "options": request.options,
            }
            deps.sqs_client.send_message(
                QueueUrl=deps.SQS_QUEUE_URL,
                MessageBody=json.dumps(message),
            )
            logger.info(f"Sent analysis job to SQS: {job_id}")
        else:
            logger.warning("SQS_QUEUE_URL not configured, job created but not queued")

        return AnalyzeResponse(
            job_id=str(job_id),
            message="Analysis started. Check job status for results.",
        )

    except Exception as e:
        logger.error(f"Error triggering analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Get job status and results"""
    try:
        job = deps.db.jobs.find_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        return job

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs")
async def list_jobs(clerk_user_id: str = Depends(get_current_user_id)):
    """List user's analysis jobs"""
    try:
        user_jobs = deps.db.jobs.find_by_user(clerk_user_id, limit=100)
        user_jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"jobs": user_jobs}

    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
