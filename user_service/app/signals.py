"""
Signals for the User Service.

Implements the Feature Store sync: whenever a Rating is saved or deleted,
the user's full rating vector is rebuilt and pushed to Redis.

This is the bridge between the "Business Data" (Django/SQL) and the
"ML Data" (Redis feature store). The Recommendation Service reads from
Redis, never from this database directly.

Pattern: Eventual Consistency
- The SQL database is the source of truth.
- Redis is a derived, eventually-consistent projection optimized for
  fast reads by the ML service.
"""

import json
import logging

import redis
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Rating

logger = logging.getLogger("app.signals")


def _get_redis_client():
    """
    Create a Redis client connection.

    Returns None if Redis is unavailable — the User Service should
    continue to function even if the feature store is down
    (graceful degradation).
    """
    try:
        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            socket_connect_timeout=2,
            decode_responses=True,
        )
        client.ping()
        return client
    except redis.ConnectionError:
        logger.warning(
            "Redis is unavailable at %s:%s — feature store sync skipped",
            settings.REDIS_HOST,
            settings.REDIS_PORT,
        )
        return None


def _sync_user_vector(user_id: int):
    """
    Rebuild and push the full user rating vector to Redis.

    Redis Key:   user:{user_id}:vector
    Redis Value: JSON dict mapping movie_id -> score
                 e.g. {"1": 5.0, "3": 4.5, "7": 3.0}

    This gives the Recommendation Service everything it needs to
    compute similarity scores without querying this database.
    """
    client = _get_redis_client()
    if client is None:
        return

    # Fetch all ratings for this user from the SQL database
    ratings = Rating.objects.filter(user_id=user_id).values_list(
        "movie_id", "score"
    )
    vector = {str(movie_id): float(score) for movie_id, score in ratings}

    redis_key = f"user:{user_id}:vector"

    if vector:
        client.set(redis_key, json.dumps(vector))
        logger.info(
            "Synced user %d vector to Redis: %d ratings",
            user_id,
            len(vector),
        )
    else:
        # User has no ratings left — clean up the key
        client.delete(redis_key)
        logger.info("Cleared Redis vector for user %d (no ratings)", user_id)


@receiver(post_save, sender=Rating)
def on_rating_saved(sender, instance, created, **kwargs):
    """
    Signal handler: triggered after a Rating is created or updated.
    Syncs the affected user's vector to the Redis feature store.
    """
    action = "created" if created else "updated"
    logger.info(
        "Rating %s for user %d, movie %d (score=%.1f) — syncing to Redis",
        action,
        instance.user_id,
        instance.movie_id,
        instance.score,
    )
    _sync_user_vector(instance.user_id)


@receiver(post_delete, sender=Rating)
def on_rating_deleted(sender, instance, **kwargs):
    """
    Signal handler: triggered after a Rating is deleted.
    Re-syncs the user's vector (with the deleted rating removed).
    """
    logger.info(
        "Rating deleted for user %d, movie %d — syncing to Redis",
        instance.user_id,
        instance.movie_id,
    )
    _sync_user_vector(instance.user_id)
