FROM python:3.14-slim

# Create a non-root user
RUN useradd -ms /bin/bash appuser

# Install curl and clean up
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python packages globally (as root)
RUN python -m pip install --no-cache-dir -r requirements.txt

# Switch to non-root user
USER appuser

# Copy app code and static folder
COPY app.py .
COPY static/ ./static/

EXPOSE 5000

# Run Flask app
CMD ["python", "app.py", "--host=0.0.0.0"]
