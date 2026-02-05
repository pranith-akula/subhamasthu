FROM python:3.11-slim

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway assigns PORT dynamically)
EXPOSE ${PORT:-8000}

# Run the application with dynamic PORT from Railway
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
