"""
API Gateway — Request Aggregation & Routing Service.

This is the single entry point for external clients. It implements the
API Gateway pattern, which:
    1. Routes requests to the appropriate internal microservice.
    2. Aggregates responses from multiple services into a single response.
    3. Implements the Circuit Breaker pattern for fault tolerance.

In this POC:
    GET /recommendations/{user_id}
        → Calls the Recommendation Service for movie IDs
        → Enriches with movie metadata (already included in ML response)
        → Falls back to "Popular Movies" if the ML service is down

In production, this role is often handled by Kong, Traefik, or
AWS API Gateway, but building it manually teaches the pattern.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("gateway")

# ---------------------------------------------------------------------------
# Service URLs — resolved via Docker Compose DNS (Service Discovery)
# ---------------------------------------------------------------------------
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://localhost:8000")
ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://localhost:8001")
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", 8002))

# ---------------------------------------------------------------------------
# Fallback data — shown when the Recommendation Service is unavailable
# (Circuit Breaker pattern: graceful degradation)
# ---------------------------------------------------------------------------
FALLBACK_POPULAR_MOVIES = [
    {"movie_id": 8, "title": "The Shawshank Redemption", "genre": ["drama", "crime", "prison"], "year": 1994, "score": 0.0},
    {"movie_id": 9, "title": "The Godfather", "genre": ["crime", "drama", "mafia"], "year": 1972, "score": 0.0},
    {"movie_id": 4, "title": "The Dark Knight", "genre": ["action", "thriller", "superhero"], "year": 2008, "score": 0.0},
    {"movie_id": 1, "title": "The Matrix", "genre": ["sci-fi", "action", "cyberpunk"], "year": 1999, "score": 0.0},
    {"movie_id": 11, "title": "Parasite", "genre": ["thriller", "drama", "dark-comedy"], "year": 2019, "score": 0.0},
]

# ---------------------------------------------------------------------------
# HTTP Client (shared across requests for connection pooling)
# ---------------------------------------------------------------------------
http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the shared HTTP client lifecycle."""
    global http_client

    logger.info("=" * 60)
    logger.info("Starting API Gateway")
    logger.info("  User Service:  %s", USER_SERVICE_URL)
    logger.info("  ML Service:    %s", ML_SERVICE_URL)
    logger.info("=" * 60)

    # Create a shared async HTTP client with connection pooling
    http_client = httpx.AsyncClient(timeout=10.0)
    yield
    await http_client.aclose()
    logger.info("API Gateway shut down")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="API Gateway",
    description="Single entry point for the Recommender Micro-Mesh",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """
    Aggregate health check across all backend services.

    Reports the status of each downstream service so operators
    can quickly identify which component is degraded.
    """
    logger.info("Running aggregate health check")

    services = {}

    # Check User Service
    try:
        resp = await http_client.get(f"{USER_SERVICE_URL}/api/users/")
        services["user_service"] = {
            "status": "healthy" if resp.status_code == 200 else "degraded",
            "url": USER_SERVICE_URL,
            "status_code": resp.status_code,
        }
    except httpx.RequestError as exc:
        logger.error("User Service unreachable: %s", exc)
        services["user_service"] = {
            "status": "unreachable",
            "url": USER_SERVICE_URL,
            "error": str(exc),
        }

    # Check Recommendation Service
    try:
        resp = await http_client.get(f"{ML_SERVICE_URL}/health")
        services["recommendation_service"] = {
            "status": "healthy" if resp.status_code == 200 else "degraded",
            "url": ML_SERVICE_URL,
            "status_code": resp.status_code,
        }
    except httpx.RequestError as exc:
        logger.error("Recommendation Service unreachable: %s", exc)
        services["recommendation_service"] = {
            "status": "unreachable",
            "url": ML_SERVICE_URL,
            "error": str(exc),
        }

    # Overall status
    all_healthy = all(s["status"] == "healthy" for s in services.values())
    return {
        "service": "api-gateway",
        "status": "healthy" if all_healthy else "degraded",
        "downstream": services,
    }


@app.get("/recommendations/{user_id}")
async def get_recommendations(user_id: int, top_n: int = 5):
    """
    Get personalized movie recommendations for a user.

    This is the primary aggregation endpoint. Flow:

    1. Call the Recommendation Service with the user_id.
       (The ML service internally reads from Redis, not from the User DB.)
    2. Return the enriched recommendations to the client.
    3. If the ML service is down → return fallback popular movies
       (Circuit Breaker pattern).

    In a full system, the Gateway would also call the Catalog Service
    to hydrate movie IDs with full metadata (posters, descriptions).
    """
    logger.info(
        "Gateway: recommendation request for user_id=%d, top_n=%d",
        user_id,
        top_n,
    )

    # --- Call the Recommendation Service ---
    try:
        response = await http_client.post(
            f"{ML_SERVICE_URL}/recommend",
            json={"user_id": user_id, "top_n": top_n},
        )

        if response.status_code == 200:
            data = response.json()
            logger.info(
                "ML service returned %d recommendations for user %d",
                len(data.get("recommendations", [])),
                user_id,
            )
            return {
                "user_id": user_id,
                "recommendations": data["recommendations"],
                "source": data.get("source", "model"),
                "service_status": "online",
            }
        else:
            logger.error(
                "ML service returned status %d: %s",
                response.status_code,
                response.text,
            )
            # Fall through to circuit breaker

    except httpx.RequestError as exc:
        logger.error(
            "ML service unreachable: %s — activating circuit breaker", exc
        )

    # --- Circuit Breaker: Graceful Degradation ---
    # The ML service is down, but we don't crash. Instead, we return
    # a curated list of popular movies so the user experience continues.
    logger.warning(
        "Circuit breaker OPEN: returning fallback popular movies for user %d",
        user_id,
    )
    return {
        "user_id": user_id,
        "recommendations": FALLBACK_POPULAR_MOVIES[:top_n],
        "source": "fallback_popular",
        "service_status": "degraded",
    }


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """
    Proxy: fetch user profile from the User Service.
    
    Demonstrates the Gateway's routing capability — clients
    don't need to know the internal service topology.
    """
    logger.info("Gateway: proxying user request for user_id=%d", user_id)
    try:
        response = await http_client.get(
            f"{USER_SERVICE_URL}/api/users/{user_id}/"
        )
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="User not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail="Upstream error from User Service",
            )
    except httpx.RequestError as exc:
        logger.error("User Service unreachable: %s", exc)
        raise HTTPException(
            status_code=503, detail="User Service is unavailable"
        )


@app.get("/users/{user_id}/ratings")
async def get_user_ratings(user_id: int):
    """Proxy: fetch user ratings from the User Service."""
    logger.info("Gateway: proxying ratings request for user_id=%d", user_id)
    try:
        response = await http_client.get(
            f"{USER_SERVICE_URL}/api/users/{user_id}/ratings/"
        )
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail="Upstream error from User Service",
            )
    except httpx.RequestError as exc:
        logger.error("User Service unreachable: %s", exc)
        raise HTTPException(
            status_code=503, detail="User Service is unavailable"
        )


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting Gateway on port %d", SERVICE_PORT)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=False,
        log_level="info",
    )
