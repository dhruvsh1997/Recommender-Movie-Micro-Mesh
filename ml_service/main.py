"""
Recommendation Service — FastAPI Application.

This is the ML Inference Microservice. It:
    1. Loads the recommendation model into memory on startup.
    2. Connects to Redis to read user feature vectors.
    3. Exposes a /recommend endpoint for real-time predictions.

Key architectural properties:
    - STATELESS: Holds no user data. Only the model weights live in memory.
    - INDEPENDENT: Can be scaled, restarted, or updated without affecting
      the User Service or any other component.
    - FAST: Built on FastAPI (ASGI) for high-concurrency, low-latency serving.
"""

import json
import logging
import os
import sys
from contextlib import asynccontextmanager

import redis
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from model import RecommendationModel
from movie_catalog import get_movie, get_all_movies

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ml_service")

# ---------------------------------------------------------------------------
# Configuration from Environment
# ---------------------------------------------------------------------------
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", 8001))

# ---------------------------------------------------------------------------
# Global State (loaded once on startup)
# ---------------------------------------------------------------------------
model: RecommendationModel | None = None
redis_client: redis.Redis | None = None


# ---------------------------------------------------------------------------
# Lifespan — Startup / Shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.
    
    Startup:
        - Load the recommendation model into memory.
        - Establish the Redis connection.
    Shutdown:
        - Close the Redis connection cleanly.
    """
    global model, redis_client

    # --- Startup ---
    logger.info("=" * 60)
    logger.info("Starting Recommendation Service")
    logger.info("=" * 60)

    # Load the ML model
    logger.info("Loading recommendation model...")
    model = RecommendationModel()
    logger.info("Model loaded successfully")

    # Connect to Redis (feature store)
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        redis_client.ping()
        logger.info("Connected to Redis at %s:%d", REDIS_HOST, REDIS_PORT)
    except redis.ConnectionError:
        logger.error(
            "Cannot connect to Redis at %s:%d — service will return "
            "fallback recommendations only",
            REDIS_HOST,
            REDIS_PORT,
        )
        redis_client = None

    yield

    # --- Shutdown ---
    logger.info("Shutting down Recommendation Service...")
    if redis_client:
        redis_client.close()
        logger.info("Redis connection closed")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Recommendation Service",
    description="ML inference microservice for movie recommendations",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Pydantic Schemas — Input/Output Validation
# ---------------------------------------------------------------------------
class RecommendRequest(BaseModel):
    """
    Request body for the /recommend endpoint.
    
    Pydantic enforces type validation at the API boundary,
    ensuring the model never receives malformed data.
    """
    user_id: int = Field(..., gt=0, description="User ID to get recommendations for")
    top_n: int = Field(default=5, ge=1, le=15, description="Number of recommendations")


class MovieRecommendation(BaseModel):
    """A single movie recommendation with score."""
    movie_id: int
    score: float
    title: str | None = None
    genre: list[str] | None = None
    year: int | None = None


class RecommendResponse(BaseModel):
    """Response body for the /recommend endpoint."""
    user_id: int
    recommendations: list[MovieRecommendation]
    source: str = "model"  # "model" or "fallback"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Reports the status of the model and Redis connection.
    Used by the API Gateway and Kubernetes liveness probes.
    """
    redis_ok = False
    if redis_client:
        try:
            redis_client.ping()
            redis_ok = True
        except redis.ConnectionError:
            pass

    return {
        "service": "recommendation-service",
        "status": "healthy",
        "model_loaded": model is not None,
        "redis_connected": redis_ok,
    }


@app.get("/movies")
async def list_movies():
    """
    List all movies in the catalog.
    
    Useful for debugging and for the frontend to display
    the available movie catalog.
    """
    logger.info("Listing all movies in catalog")
    return {"movies": get_all_movies(), "total": len(get_all_movies())}


@app.post("/recommend", response_model=RecommendResponse)
async def recommend(request: RecommendRequest):
    """
    Generate movie recommendations for a user.

    Flow:
    1. Read user's rating vector from Redis (Feature Store).
    2. Feed the vector into the ML model.
    3. Enrich results with movie metadata from the catalog.
    4. Return ranked recommendations.

    If Redis is down, returns a fallback list of popular movies
    (Circuit Breaker / Graceful Degradation pattern).
    """
    logger.info(
        "Recommendation request: user_id=%d, top_n=%d",
        request.user_id,
        request.top_n,
    )

    # --- Step 1: Fetch user vector from Redis ---
    user_ratings = {}
    source = "model"

    if redis_client:
        try:
            redis_key = f"user:{request.user_id}:vector"
            raw = redis_client.get(redis_key)

            if raw:
                user_ratings = json.loads(raw)
                logger.info(
                    "Fetched user %d vector from Redis: %d ratings",
                    request.user_id,
                    len(user_ratings),
                )
            else:
                logger.warning(
                    "No vector found in Redis for user %d — "
                    "user may not have rated any movies yet",
                    request.user_id,
                )
                source = "fallback"

        except redis.ConnectionError:
            logger.error("Redis connection lost during request — using fallback")
            source = "fallback"
    else:
        logger.warning("Redis not available — using fallback recommendations")
        source = "fallback"

    # --- Step 2: Run the ML model ---
    raw_recommendations = model.predict(user_ratings, top_n=request.top_n)

    # --- Step 3: Enrich with movie metadata ---
    enriched = []
    for rec in raw_recommendations:
        movie = get_movie(rec["movie_id"])
        enriched.append(
            MovieRecommendation(
                movie_id=rec["movie_id"],
                score=rec["score"],
                title=movie["title"] if movie else "Unknown",
                genre=movie["genre"] if movie else [],
                year=movie["year"] if movie else 0,
            )
        )

    logger.info(
        "Returning %d recommendations for user %d (source=%s)",
        len(enriched),
        request.user_id,
        source,
    )

    return RecommendResponse(
        user_id=request.user_id,
        recommendations=enriched,
        source=source,
    )


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting uvicorn on port %d", SERVICE_PORT)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=False,
        log_level="info",
    )
