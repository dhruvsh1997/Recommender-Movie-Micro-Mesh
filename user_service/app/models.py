"""
Models for the User Service.

Defines the core business entities: User profiles and Movie Ratings.
The Rating model is the "source of truth" — its data is synced to Redis
so that the ML Recommendation Service can access user vectors without
coupling to this database (Database-per-Service pattern).
"""

import logging
from django.db import models

logger = logging.getLogger("app.models")


class UserProfile(models.Model):
    """
    Represents a user in the system.

    In a production setup this would integrate with Django's auth system
    or an external identity provider. Kept simple for the POC.
    """

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"User({self.id}, {self.username})"


class Rating(models.Model):
    """
    A user's rating of a movie.

    Fields:
        user:     FK to UserProfile — who rated it
        movie_id: Integer ID from the movie catalog (owned by Catalog Service)
        score:    Float between 0.0 and 5.0
    
    On save, the post_save signal pushes the updated user vector to Redis.
    This implements the Feature Store / Eventual Consistency pattern.
    """

    user = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="ratings"
    )
    movie_id = models.IntegerField(
        help_text="Movie ID from the catalog service"
    )
    score = models.FloatField(
        help_text="Rating score between 0.0 and 5.0"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # A user can only rate a movie once
        unique_together = ("user", "movie_id")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Rating(user={self.user_id}, movie={self.movie_id}, score={self.score})"
