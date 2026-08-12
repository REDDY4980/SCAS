# SCAS — Local Tooling Requirements (Claude Kickoff B.4)

The AI developer environment should use:

## Backend / ML
- Python 3.11+
- FastAPI
- SQLAlchemy
- Alembic
- PaddleOCR
- OpenCV preprocessing
- XGBoost
- Optuna
- scikit-learn
- Joblib
- pytest

## Database / infrastructure
- PostgreSQL
- Docker
- Docker Compose

## Flutter
- Flutter SDK
- Dart
- Riverpod
- Dio
- flutter_secure_storage
- flutter_test

## Secrets/config
Use environment variables.
Never hardcode:
- JWT secret
- database credentials
- API keys
- model paths
- upload directories
- production origins

## Development principle
Install/configure only what the current phase requires. Local PostgreSQL should run through Docker for development. Cloud services are deferred until deployment is selected.
