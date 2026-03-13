FROM python:3.14-slim

WORKDIR /app

# Non-root user
RUN useradd -ms /bin/bash appuser
USER appuser

# Copy requirements and install packages in user local
COPY requirements.txt .
RUN python -m pip install --user --no-cache-dir -r requirements.txt

# Copy app code
COPY app.py .

# Add local pip binaries to PATH
ENV PATH=/home/appuser/.local/bin:$PATH

EXPOSE 5000

# Gunicorn single worker, 4 threads
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:5000", "app:app"]
