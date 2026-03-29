# 🎬 Recommender Micro-Mesh

A **Microservices-based Movie Recommendation System** POC demonstrating the architectural principles of decomposing an ML application into independently deployable services.

## Architecture Overview

```
┌──────────┐      ┌──────────────┐      ┌───────────────────┐
│  Client  │─────▶│  API Gateway │─────▶│  User Service     │
│ (curl /  │      │  (FastAPI)   │      │  (Django + SQLite) │
│  browser)│      │  Port: 8002  │      │  Port: 8000       │
└──────────┘      └──────┬───────┘      └────────┬──────────┘
                         │                       │ writes user vectors
                         │                       ▼
                         │               ┌───────────────┐
                         │               │    Redis      │
                         │               │  Port: 6379   │
                         │               └───────┬───────┘
                         │                       │ reads user vectors
                         ▼                       │
                  ┌──────────────────┐           │
                  │ Recommendation   │◀──────────┘
                  │ Service (FastAPI)│
                  │ Port: 8001      │
                  └─────────────────┘
```

### Services

| Service | Tech Stack | Port | Responsibility |
|---------|-----------|------|----------------|
| **User Service** | Django + DRF | 8000 | User auth, profiles, movie ratings |
| **Recommendation Service** | FastAPI | 8001 | ML inference (collaborative filtering) |
| **API Gateway** | FastAPI | 8002 | Request routing, response aggregation |
| **Redis** | Redis 7 Alpine | 6379 | Feature store (user vectors) |

## Prerequisites

- Docker & Docker Compose (v2+)
- Python 3.11+ (for local development)
- `curl` or Postman (for testing)

## Quick Start (Docker)

```bash
# Clone and enter the project
cd recommender-micro-mesh

# Build and start all services
docker compose up --build

# In another terminal, seed the database with sample data
docker compose exec user-service python manage.py seed_data
```

## Quick Start (Local Development)

```bash
# 1. Start Redis Service
docker run -d --name redis-dev -p 6379:6379 redis:7-alpine

# 2. Start User Service
cd user_service
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver 0.0.0.0:8000

# 3. Start Recommendation Service (new terminal)
cd ml_service
pip install -r requirements.txt
python main.py

# 4. Start API Gateway (new terminal)
cd gateway
pip install -r requirements.txt
python main.py
```

## API Endpoints

### User Service (port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/` | List all users |
| POST | `/api/users/` | Create a user |
| GET | `/api/users/{id}/` | Get user detail |
| GET | `/api/users/{id}/ratings/` | Get user's ratings |
| POST | `/api/ratings/` | Submit a rating (syncs to Redis) |

### Recommendation Service (port 8001)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/recommend` | Get recommendations `{"user_id": 1}` |
| GET | `/health` | Health check |
| GET | `/movies` | List all movies in the catalog |

### API Gateway (port 8002)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/recommendations/{user_id}` | Aggregated recommendations with movie details |
| GET | `/health` | Health check for all services |

## Testing the Full Flow

```bash
# 1. Check overall health
curl http://localhost:8002/health | python -m json.tool

# 2. Create a user
curl -X POST http://localhost:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com"}'

# 3. Rate some movies
curl -X POST http://localhost:8000/api/ratings/ \
  -H "Content-Type: application/json" \
  -d '{"user": 1, "movie_id": 1, "score": 5.0}'

curl -X POST http://localhost:8000/api/ratings/ \
  -H "Content-Type: application/json" \
  -d '{"user": 1, "movie_id": 3, "score": 4.5}'

# 4. Get recommendations via the Gateway
curl http://localhost:8002/recommendations/1 | python -m json.tool
```

## Key Concepts Demonstrated

1. **Database-per-Service**: User Service owns SQLite; Recommendation Service has no DB
2. **Feature Store Pattern**: Redis bridges the gap between services
3. **Eventual Consistency**: Ratings sync to Redis asynchronously on save
4. **Stateless Inference**: ML service holds only the model, fetches data on demand
5. **Service Discovery**: Docker Compose DNS-based discovery by hostname
6. **Circuit Breaker**: Gateway returns fallback "Popular Movies" if ML service is down
7. **API Gateway Pattern**: Single entry point aggregates data from multiple services

## Project Structure

```
recommender-micro-mesh/
├── docker-compose.yml
├── README.md
├── .gitignore
├── user_service/               # Django - User Management
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── manage.py
│   ├── user_service/           # Django project config
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   └── app/                    # Django app
│       ├── models.py
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       ├── signals.py
│       └── management/commands/seed_data.py
├── ml_service/                 # FastAPI - Recommendation Engine
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── model.py
│   └── movie_catalog.py
├── gateway/                    # FastAPI - API Gateway
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
└── scripts/
    └── test_flow.sh            # End-to-end test script
```

## License

MIT - Educational POC for learning microservices with ML.
