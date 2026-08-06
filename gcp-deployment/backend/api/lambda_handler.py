"""Lambda handler for the FastAPI application."""

from mangum import Mangum
from api.main import app

# Create the Lambda handler
# API Gateway passes the full path including /api/ prefix
handler = Mangum(app, lifespan="off")