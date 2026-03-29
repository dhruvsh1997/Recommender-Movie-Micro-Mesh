"""
Serializers for the User Service REST API.

Uses Django REST Framework to validate and transform data between
JSON (API boundary) and Django model instances (database boundary).

This is analogous to Pydantic in FastAPI — enforcing type contracts
at the service boundary so invalid data never reaches the database.
"""

import logging
from rest_framework import serializers
from .models import UserProfile, Rating

logger = logging.getLogger("app.serializers")


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for UserProfile.

    Exposes: id, username, email, created_at.
    The 'id' and 'created_at' are read-only (auto-generated).
    """

    class Meta:
        model = UserProfile
        fields = ["id", "username", "email", "created_at"]
        read_only_fields = ["id", "created_at"]


class RatingSerializer(serializers.ModelSerializer):
    """
    Serializer for Rating.

    Validates:
    - score is between 0.0 and 5.0
    - movie_id is a positive integer
    - user exists
    
    On successful save, the post_save signal automatically syncs
    the user's vector to Redis.
    """

    class Meta:
        model = Rating
        fields = ["id", "user", "movie_id", "score", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_score(self, value):
        """Ensure score is within valid range."""
        if not (0.0 <= value <= 5.0):
            logger.warning("Invalid score received: %s", value)
            raise serializers.ValidationError(
                "Score must be between 0.0 and 5.0"
            )
        return value

    def validate_movie_id(self, value):
        """Ensure movie_id is positive."""
        if value <= 0:
            raise serializers.ValidationError(
                "movie_id must be a positive integer"
            )
        return value
