"""
Movie Catalog for the Recommendation Service.

In a full microservices architecture, this data would live in a separate
Catalog Service (possibly backed by MongoDB). For this POC, the catalog
is embedded as a Python dictionary to keep the focus on the ML and
inter-service communication patterns.

Each movie has:
    - id:     Unique integer identifier
    - title:  Display name
    - genre:  List of genre tags (used for content-based similarity)
    - year:   Release year
"""

import logging

logger = logging.getLogger("ml_service.catalog")

MOVIE_CATALOG = {
    1: {
        "id": 1,
        "title": "The Matrix",
        "genre": ["sci-fi", "action", "cyberpunk"],
        "year": 1999,
    },
    2: {
        "id": 2,
        "title": "Inception",
        "genre": ["sci-fi", "thriller", "mind-bending"],
        "year": 2010,
    },
    3: {
        "id": 3,
        "title": "Interstellar",
        "genre": ["sci-fi", "drama", "space"],
        "year": 2014,
    },
    4: {
        "id": 4,
        "title": "The Dark Knight",
        "genre": ["action", "thriller", "superhero"],
        "year": 2008,
    },
    5: {
        "id": 5,
        "title": "Pulp Fiction",
        "genre": ["crime", "drama", "dark-comedy"],
        "year": 1994,
    },
    6: {
        "id": 6,
        "title": "Fight Club",
        "genre": ["drama", "thriller", "psychological"],
        "year": 1999,
    },
    7: {
        "id": 7,
        "title": "Forrest Gump",
        "genre": ["drama", "comedy", "romance"],
        "year": 1994,
    },
    8: {
        "id": 8,
        "title": "The Shawshank Redemption",
        "genre": ["drama", "crime", "prison"],
        "year": 1994,
    },
    9: {
        "id": 9,
        "title": "The Godfather",
        "genre": ["crime", "drama", "mafia"],
        "year": 1972,
    },
    10: {
        "id": 10,
        "title": "Goodfellas",
        "genre": ["crime", "drama", "mafia"],
        "year": 1990,
    },
    11: {
        "id": 11,
        "title": "Parasite",
        "genre": ["thriller", "drama", "dark-comedy"],
        "year": 2019,
    },
    12: {
        "id": 12,
        "title": "Spirited Away",
        "genre": ["animation", "fantasy", "adventure"],
        "year": 2001,
    },
    13: {
        "id": 13,
        "title": "Your Name",
        "genre": ["animation", "romance", "fantasy"],
        "year": 2016,
    },
    14: {
        "id": 14,
        "title": "Akira",
        "genre": ["animation", "sci-fi", "cyberpunk"],
        "year": 1988,
    },
    15: {
        "id": 15,
        "title": "Blade Runner 2049",
        "genre": ["sci-fi", "thriller", "cyberpunk"],
        "year": 2017,
    },
}


def get_movie(movie_id: int) -> dict | None:
    """Look up a movie by ID. Returns None if not found."""
    return MOVIE_CATALOG.get(movie_id)


def get_all_movies() -> list[dict]:
    """Return all movies in the catalog."""
    return list(MOVIE_CATALOG.values())


def get_movie_ids() -> list[int]:
    """Return all valid movie IDs."""
    return list(MOVIE_CATALOG.keys())
