# ============================================================
# Dockerfile — API Gateway (FastAPI)
#
# Thin routing/aggregation layer. No ML dependencies needed.
# ============================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8002

# Single worker is fine — this is I/O-bound, not compute-bound
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8002", \
     "--workers", "1", \
     "--log-level", "info"]
