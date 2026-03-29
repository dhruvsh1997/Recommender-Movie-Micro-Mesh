"""
URL routing for the User Service app.

Uses DRF's DefaultRouter to auto-generate RESTful URL patterns
for the User and Rating ViewSets.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, RatingViewSet

# The router automatically creates:
#   /api/users/           (list, create)
#   /api/users/{pk}/      (retrieve, update, delete)
#   /api/users/{pk}/ratings/  (custom action)
#   /api/ratings/         (list, create)
#   /api/ratings/{pk}/    (retrieve, update, delete)
router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"ratings", RatingViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
