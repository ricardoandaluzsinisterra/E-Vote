# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .

RUN apt-get update && apt-get install -y libpq-dev gcc && apt-get clean && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code (build context is ./backend)
COPY . .

# Expose port for auth service
EXPOSE 8000

# Run the auth FastAPI app (module path matches backend/auth_service/main.py)
CMD [\"uvicorn\", \"auth_service.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]
