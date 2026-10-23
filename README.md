# Digital Wallet System

A REST API for managing digital wallets and financial transactions, built with Python, FastAPI, SQLAlchemy, and PostgreSQL.

## Features

- User registration and authentication
- JWT-based access authentication and refresh-token support
- Role-based access control
- Wallet creation and wallet management
- Deposits, withdrawals, and wallet transfers
- Transaction history and idempotency handling
- Transaction validation and balance-limit checks
- Audit logging
- Suspicious-activity tracking
- PostgreSQL database migrations using Alembic
- Automated API tests using pytest

## Technology Stack

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Psycopg
- Alembic
- Pydantic Settings
- PyJWT
- pytest and HTTPX

## Project Structure

```text
digital_wallet_system/
├── alembic/
│   └── versions/
├── app/
│   ├── api/
│   │   └── routes/
│   ├── core/
│   ├── database/
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   └── utils/
├── docs/
├── tests/
├── .env.example
├── .gitignore
├── alembic.ini
├── main.py
├── requirements.txt
└── README.md
```

## Prerequisites

- Python installed
- PostgreSQL installed and running
- A PostgreSQL database and user configured for the application

## Installation

Clone the repository and enter the project directory.

```powershell
git clone YOUR_GITHUB_REPOSITORY_URL
cd digital_wallet_system
```

Create and activate a virtual environment on Windows PowerShell.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install dependencies.

```powershell
python -m pip install -r requirements.txt
```

## Environment Configuration

Create a local `.env` file using `.env.example` as a reference.

Configure the required database connection string and authentication settings according to `app/core/config.py`.

Example database URL format:

```text
postgresql+psycopg://USERNAME:PASSWORD@localhost:5432/DATABASE_NAME
```

Use your own local credentials. Never commit `.env`, database passwords, or JWT secrets to GitHub.

## Database Migrations

Apply the available migrations.

```powershell
python -m alembic upgrade head
```

Check the current migration revision.

```powershell
python -m alembic current
```

## Run the Application

Start the development server.

```powershell
python -m uvicorn main:app --reload
```

Open the interactive API documentation:

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health check: http://127.0.0.1:8000/

Use the Swagger UI to register or authenticate a user, authorize requests with the appropriate access token, and test the available endpoints.

## Run Automated Tests

Configure `DATABASE_URL` to point to a dedicated test database before running tests.

```powershell
python -m pytest tests -v
```

Do not run destructive test setup against a database containing important data.

## API Modules

| Module | Purpose |
|---|---|
| Authentication | Registration, login, and token handling |
| Wallets | Wallet creation and wallet operations |
| Transactions | Deposits, withdrawals, transfers, and transaction history |
| Audit Logs | Reviewing recorded system actions |
| Suspicious Activities | Reviewing suspicious activity records |

For the exact endpoint paths, request schemas, and response formats, refer to Swagger UI at `/docs`.

## Security Notes

- Keep secrets in environment variables or a local `.env` file.
- Use a dedicated test database for automated tests.
- Use HTTPS and secure secret management in production.
- Apply least-privilege access controls to administrative endpoints.
- Review transaction concurrency, idempotency, and balance consistency before production deployment.

## Project Status

The current automated test suite passes in the development environment. Run the tests and database migrations in your own environment before deployment.
