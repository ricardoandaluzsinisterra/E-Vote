# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install system dependencies and Python dependencies
RUN apt-get update && apt-get install -y libpq-dev gcc && apt-get clean && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
# Install shared models package so services can import models consistently
RUN pip install --no-cache-dir ./models

# Expose port 8000
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
