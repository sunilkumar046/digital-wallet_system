
import os
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient


# Safety guard: tests must never run against the development database.
database_url = os.environ.get("DATABASE_URL", "")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL is missing. Select digital_wallet_test_db "
        "before running pytest."
    )

database_name = urlsplit(database_url).path.lstrip("/")
if database_name != "digital_wallet_test_db":
    raise RuntimeError(
        f"Refusing to run tests against database: {database_name!r}"
    )

# Import the application only after the database safety check.
from main import app
from app.database.database import engine
from sqlalchemy import text


@pytest.fixture
def client():
    # Reset only the dedicated test database.
    with engine.begin() as connection:
        connection.execute(
    text(
        """
        TRUNCATE TABLE
            suspicious_activities,
            transactions,
            wallets,
            refresh_tokens,
            users,
            roles
        RESTART IDENTITY CASCADE
        """
    )
)

    # Application lifespan seeds the required roles.
    with TestClient(app) as test_client:
        yield test_client
