FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

# Install Python package manager
RUN pip install uv

# Copy database package (required dependency)
# Build context should be from backend/ directory
COPY database ./database

# Copy shared modules
COPY common ./common

# Copy retirement-specific files
COPY retirement/pyproject.toml retirement/uv.lock ./

# Update pyproject.toml to use ./database instead of ../database
RUN sed -i.bak 's|path = "../database"|path = "./database"|g' pyproject.toml && rm pyproject.toml.bak

# Install Python dependencies
# Don't use --frozen because the lock file has the old path
# First install database package with all its dependencies (including pg8000)
# This ensures transitive dependencies from the local path dependency are installed
RUN cd database && uv pip install --system -e . && cd ..
# Then sync the main project dependencies
RUN uv sync --no-install-project

# Copy retirement application code
COPY retirement/*.py ./

# Expose port
EXPOSE 8000

# Set environment variable for Cloud Run
ENV PORT=8000

# Run the application
CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]

