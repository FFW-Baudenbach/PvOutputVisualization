FROM python:3.14-slim

# Create a non-root user
RUN useradd -ms /bin/bash appuser

# Install curl and clean up
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies first (better cache)
COPY requirements.txt .

# Install Python packages (for non-root user)
RUN python -m pip install --user --no-cache-dir -r requirements.txt

# Switch to non-root user
USER appuser

# Copy app code
COPY app.py .
COPY static/ ./static/

# Make sure local pip binaries are in PATH
ENV PATH=/home/appuser/.local/bin:$PATH

EXPOSE 5000

# Run Flask app
CMD ["python", "app.py", "--host=0.0.0.0"]
