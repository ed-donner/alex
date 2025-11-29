FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy shared modules (from backend/ directory)
COPY database ./database
COPY common ./common

# Copy API dependencies
COPY api/pyproject.toml ./

# Fix path in pyproject.toml for alex-database (change from workspace to path dependency)
RUN sed -i.bak 's|workspace = true|path = "./database"|g' pyproject.toml && \
    sed -i.bak 's|path = "../database"|path = "./database"|g' pyproject.toml && \
    rm pyproject.toml.bak || true

# Install dependencies
RUN uv sync

# Copy API code
COPY api/*.py ./

# Expose port
EXPOSE 8080

# Run server
CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]

