# ============================================================
# Dockerfile — Recommendation Service (FastAPI)
#
# Lightweight image for the ML inference microservice.
# In production, use a GPU-enabled base image (nvidia/cuda)
# for deep learning models.
# ============================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8001

# Uvicorn with 2 workers — async, so fewer workers needed
# In production with GPU models, use 1 worker per GPU
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "2", \
     "--log-level", "info"]
