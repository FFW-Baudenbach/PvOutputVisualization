FROM python:3.14-slim

# Create a non-root user and home directory
RUN useradd -ms /bin/bash appuser

# Install curl and clean up
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install as non-root
COPY requirements.txt .

# Switch to non-root user
USER appuser

# Install Python packages for this user
RUN python -m pip install --user --no-cache-dir -r requirements.txt

# Make sure local pip binaries are in PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy app code
COPY --chown=appuser:appuser app/ .

EXPOSE 5000

# Run Flask in threaded mode
CMD ["python", "app.py", "--host=0.0.0.0"]
