FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install OS packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python packages globally
RUN python -m pip install --no-cache-dir -r requirements.txt

# Create non-root user and switch
RUN useradd -ms /bin/bash appuser
USER appuser

# Copy app code with proper ownership
COPY --chown=appuser:appuser app/ .

EXPOSE 5000

# Run Flask
CMD ["python", "app.py"]
