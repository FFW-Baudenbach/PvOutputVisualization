# Use Raspberry Pi compatible slim image
FROM python:3.14-slim

WORKDIR /app

# Create non-root user
RUN useradd -ms /bin/bash appuser
USER appuser

# Copy requirements and install packages as user
COPY requirements.txt .
RUN python -m pip install --user --no-cache-dir -r requirements.txt

# Copy app code
COPY app.py .

# Make sure local pip binaries are in PATH
ENV PATH=/home/appuser/.local/bin:$PATH
ENV TMPDIR=/tmp

EXPOSE 5000

# Gunicorn: single worker with threads (shared in-memory cache)
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:5000", "app:app"]
