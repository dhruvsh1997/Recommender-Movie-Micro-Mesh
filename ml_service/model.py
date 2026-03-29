"""
Recommendation Model — Content-Based Collaborative Filtering.

This module builds a movie-to-movie similarity matrix at startup using
genre-based features and cosine similarity. When asked for recommendations,
it looks at what the user has rated highly, finds similar movies, and
returns the top-N candidates the user hasn't seen yet.

Architecture notes:
    - This model is loaded ONCE into memory on service startup (stateless service).
    - User data is fetched from Redis on each request (Feature Store pattern).
    - The model has ZERO access to the User Service database.

In a production system, this would be a trained collaborative filtering
model (matrix factorization, neural CF, etc.) loaded from a model registry.
"""

import logging
from collections import defaultdict

import numpy as np
from movie_catalog import MOVIE_CATALOG

logger = logging.getLogger("ml_service.model")


class RecommendationModel:
    """
    Content-based recommendation engine using genre similarity.

    On init, it:
    1. Extracts all unique genres across the catalog.
    2. Builds a binary feature vector for each movie (genre membership).
    3. Computes a pairwise cosine similarity matrix.

    On predict, it:
    1. Takes a user's rating vector {movie_id: score}.
    2. For each rated movie, weights similar movies by (similarity * user_score).
    3. Filters out already-rated movies.
    4. Returns top-N recommendations.
    """

    def __init__(self):
        """Build the similarity matrix from the movie catalog."""
        logger.info("Initializing RecommendationModel...")

        self.movie_ids = sorted(MOVIE_CATALOG.keys())
        self.id_to_idx = {mid: idx for idx, mid in enumerate(self.movie_ids)}
        self.n_movies = len(self.movie_ids)

        # Step 1: Collect all unique genres
        all_genres = set()
        for movie in MOVIE_CATALOG.values():
            all_genres.update(movie["genre"])
        self.genres = sorted(all_genres)
        self.n_genres = len(self.genres)
        genre_to_idx = {g: i for i, g in enumerate(self.genres)}

        logger.info(
            "Catalog: %d movies, %d unique genres", self.n_movies, self.n_genres
        )

        # Step 2: Build feature matrix (n_movies x n_genres)
        self.feature_matrix = np.zeros(
            (self.n_movies, self.n_genres), dtype=np.float32
        )
        for movie_id in self.movie_ids:
            idx = self.id_to_idx[movie_id]
            for genre in MOVIE_CATALOG[movie_id]["genre"]:
                self.feature_matrix[idx, genre_to_idx[genre]] = 1.0

        # Step 3: Compute cosine similarity matrix
        # cosine_sim(A, B) = dot(A, B) / (||A|| * ||B||)
        norms = np.linalg.norm(self.feature_matrix, axis=1, keepdims=True)
        # Avoid division by zero
        norms = np.where(norms == 0, 1, norms)
        normalized = self.feature_matrix / norms
        self.similarity_matrix = normalized @ normalized.T

        logger.info(
            "Similarity matrix computed: shape=%s", self.similarity_matrix.shape
        )

    def predict(
        self,
        user_ratings: dict[str, float],
        top_n: int = 5,
    ) -> list[dict]:
        """
        Generate movie recommendations for a user.

        Args:
            user_ratings: Dict mapping movie_id (str) -> rating score (float).
                          This comes directly from the Redis feature store.
            top_n: Number of recommendations to return.

        Returns:
            List of dicts: [{"movie_id": int, "score": float}, ...]
            Sorted by predicted relevance score (descending).
        """
        if not user_ratings:
            logger.warning("Empty user ratings — returning popular movies")
            return self._fallback_popular(top_n)

        logger.info(
            "Generating predictions from %d rated movies", len(user_ratings)
        )

        # Accumulate weighted similarity scores for all candidate movies
        scores = defaultdict(float)
        rated_ids = set()

        for movie_id_str, user_score in user_ratings.items():
            movie_id = int(movie_id_str)
            rated_ids.add(movie_id)

            if movie_id not in self.id_to_idx:
                logger.warning("Movie ID %d not in catalog, skipping", movie_id)
                continue

            movie_idx = self.id_to_idx[movie_id]
            similarities = self.similarity_matrix[movie_idx]

            # Weight each similar movie's score by user rating * similarity
            for other_id in self.movie_ids:
                other_idx = self.id_to_idx[other_id]
                if other_id not in rated_ids:
                    scores[other_id] += float(similarities[other_idx]) * user_score

        if not scores:
            logger.warning("No candidate scores generated — returning fallback")
            return self._fallback_popular(top_n)

        # Sort by aggregated score, return top N
        sorted_candidates = sorted(
            scores.items(), key=lambda x: x[1], reverse=True
        )
        results = [
            {"movie_id": mid, "score": round(sc, 4)}
            for mid, sc in sorted_candidates[:top_n]
        ]

        logger.info("Top %d recommendations: %s", top_n, results)
        return results

    def _fallback_popular(self, top_n: int) -> list[dict]:
        """
        Fallback: return the first N movies as 'popular' defaults.

        In production, this would be based on global popularity metrics.
        """
        return [
            {"movie_id": mid, "score": 0.0}
            for mid in self.movie_ids[:top_n]
        ]
