FROM python:3.14-slim

WORKDIR /app

# Non-root user
RUN useradd -ms /bin/bash appuser
USER appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

# Gunicorn single worker with 4 threads
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:5000", "app:app"]