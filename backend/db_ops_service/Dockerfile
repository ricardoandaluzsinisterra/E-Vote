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
# Install shared models package so services can import models consistently
RUN pip install --no-cache-dir ./models

# Expose port for db_ops service
EXPOSE 8001

# Run the db_ops FastAPI app (module path matches backend/db_ops_service/main.py)
CMD ["uvicorn", "db_ops_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
