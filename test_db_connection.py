
from sqlalchemy import text

from app.database.database import engine


try:
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT current_database(), current_user")
        )
        database_name, username = result.fetchone()

        print("Database connection successful!")
        print(f"Database: {database_name}")
        print(f"User: {username}")

except Exception as exc:
    print("Database connection failed.")
    print(f"Error: {exc}")

finally:
    engine.dispose()
