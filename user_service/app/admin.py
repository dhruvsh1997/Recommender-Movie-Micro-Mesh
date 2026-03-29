"""
Admin registration for User Service models.

Django's built-in admin panel provides a free management UI —
one of the reasons Django is chosen for business-domain services.
"""

from django.contrib import admin
from .models import UserProfile, Rating


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "created_at")
    search_fields = ("username", "email")


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "movie_id", "score", "created_at")
    list_filter = ("score",)
    search_fields = ("user__username",)
