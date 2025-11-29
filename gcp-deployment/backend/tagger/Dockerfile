FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

# Install Python package manager
RUN pip install uv

# Copy database package (required dependency)
# Build context should be from backend/ directory
COPY database ./database


# Copy shared modules
COPY common ./common
# Copy tagger-specific files
COPY tagger/pyproject.toml tagger/uv.lock ./

# Update pyproject.toml to use ./database instead of ../database
RUN sed -i.bak 's|path = "../database"|path = "./database"|g' pyproject.toml && rm pyproject.toml.bak

# Install Python dependencies
# Don't use --frozen because the lock file has the old path
RUN uv sync --no-install-project

# Copy tagger application code
COPY tagger/*.py ./

# Expose port
EXPOSE 8000

# Set environment variable for Cloud Run
ENV PORT=8000

# Run the application
CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]

