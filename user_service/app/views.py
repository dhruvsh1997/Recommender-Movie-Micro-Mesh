"""
Views (API endpoints) for the User Service.

Provides CRUD operations for Users and Ratings via Django REST Framework.
This service is the sole owner of user/rating data (Database-per-Service).
Other services must request data through these APIs or through the
Redis feature store.
"""

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import UserProfile, Rating
from .serializers import UserProfileSerializer, RatingSerializer

logger = logging.getLogger("app.views")


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing User Profiles.

    Endpoints:
        GET    /api/users/          — List all users
        POST   /api/users/          — Create a new user
        GET    /api/users/{id}/     — Retrieve a user
        PUT    /api/users/{id}/     — Update a user
        DELETE /api/users/{id}/     — Delete a user
        GET    /api/users/{id}/ratings/ — Get all ratings for a user
    """

    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer

    def list(self, request, *args, **kwargs):
        logger.info("Listing all users")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        logger.info("Creating new user: %s", request.data.get("username"))
        return super().create(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        logger.info("Retrieving user ID: %s", kwargs.get("pk"))
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def ratings(self, request, pk=None):
        """
        Custom action: GET /api/users/{pk}/ratings/
        
        Returns all movie ratings for a specific user.
        This endpoint is called by the API Gateway when aggregating
        data for the recommendation flow.
        """
        logger.info("Fetching ratings for user ID: %s", pk)
        try:
            user = self.get_object()
        except UserProfile.DoesNotExist:
            logger.warning("User %s not found", pk)
            return Response(
                {"error": f"User {pk} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        ratings = Rating.objects.filter(user=user)
        serializer = RatingSerializer(ratings, many=True)
        logger.info(
            "Returning %d ratings for user %s", len(serializer.data), pk
        )
        return Response(serializer.data)


class RatingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Ratings.

    Endpoints:
        GET    /api/ratings/     — List all ratings
        POST   /api/ratings/     — Create a new rating (triggers Redis sync)
        GET    /api/ratings/{id}/ — Retrieve a rating
        PUT    /api/ratings/{id}/ — Update a rating (triggers Redis sync)
        DELETE /api/ratings/{id}/ — Delete a rating (triggers Redis sync)

    Important: Every write operation triggers a Django signal that
    syncs the affected user's rating vector to Redis.
    """

    queryset = Rating.objects.all()
    serializer_class = RatingSerializer

    def create(self, request, *args, **kwargs):
        logger.info(
            "New rating: user=%s, movie=%s, score=%s",
            request.data.get("user"),
            request.data.get("movie_id"),
            request.data.get("score"),
        )
        return super().create(request, *args, **kwargs)
