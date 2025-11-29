FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

# Install Python package manager
RUN pip install uv

# Copy database package (required dependency)
# Build context should be from backend/ directory
COPY database ./database

# Copy common module (required for imports)
COPY common ./common

# Copy planner-specific files
COPY planner/pyproject.toml planner/uv.lock ./

# Update pyproject.toml to use ./database instead of ../database
RUN sed -i.bak 's|path = "../database"|path = "./database"|g' pyproject.toml && rm pyproject.toml.bak

# Verify the update
RUN echo "=== Updated path in pyproject.toml ===" && grep -A 1 "alex-database" pyproject.toml

# Install Python dependencies
# Don't use --frozen because the lock file has the old path
# This will regenerate the lock file with the correct path
RUN uv sync --no-install-project

# Copy planner application code
COPY planner/*.py ./

# Expose port
EXPOSE 8000

# Set environment variable for Cloud Run
ENV PORT=8000

# Run the application
CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]

