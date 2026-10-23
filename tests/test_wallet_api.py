
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

def unique_email():
    return f"user_{uuid4().hex[:12]}@example.com"


def register_user(client, email=None, password="WalletPass123!"):
    email = email or unique_email()

    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Wallet Test User",
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    return email, password, response.json()


def login_user(client, email, password="WalletPass123!"):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_wallet(client, token, name="Test Wallet", currency="INR"):
    response = client.post(
        "/api/wallets",
        headers=auth_headers(token),
        json={"name": name, "currency": currency},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_register_and_login(client):
    email, password, user = register_user(client)

    assert user["email"] == email
    assert user["is_active"] is True

    token = login_user(client, email, password)
    assert isinstance(token, str)
    assert len(token) > 20

    me = client.get(
        "/api/auth/me",
        headers=auth_headers(token),
    )
    assert me.status_code == 200, me.text
    assert me.json()["email"] == email


def test_duplicate_registration_is_rejected(client):
    email, _, _ = register_user(client)

    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Duplicate User",
            "email": email,
            "password": "WalletPass123!",
        },
    )

    assert response.status_code == 409


def test_login_rejects_wrong_password(client):
    email, _, _ = register_user(client)

    response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401


def test_wallet_requires_authentication(client):
    response = client.get("/api/wallets")
    assert response.status_code in (401, 403)


def test_create_and_list_wallets(client):
    email, password, _ = register_user(client)
    token = login_user(client, email, password)

    wallet = create_wallet(client, token, "Primary Wallet")

    assert wallet["name"] == "Primary Wallet"
    assert wallet["currency"] == "INR"
    assert wallet["status"] == "ACTIVE"
    assert float(wallet["available_balance"]) == 0

    response = client.get(
        "/api/wallets",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    assert any(item["id"] == wallet["id"] for item in response.json())


def test_user_cannot_access_another_users_wallet(client):
    email_a, password_a, _ = register_user(client)
    token_a = login_user(client, email_a, password_a)
    wallet_a = create_wallet(client, token_a)

    email_b, password_b, _ = register_user(client)
    token_b = login_user(client, email_b, password_b)

    response = client.get(
        f"/api/wallets/{wallet_a['id']}",
        headers=auth_headers(token_b),
    )

    assert response.status_code == 404


def test_deposit_withdraw_and_idempotency(client):
    email, password, _ = register_user(client)
    token = login_user(client, email, password)
    wallet = create_wallet(client, token)

    deposit_payload = {
        "wallet_id": wallet["id"],
        "amount": "100.00",
        "idempotency_key": f"deposit-{uuid4().hex[:16]}",
        "description": "Test deposit",
    }

    first = client.post(
        "/api/transactions/deposit",
        headers=auth_headers(token),
        json=deposit_payload,
    )
    assert first.status_code == 201, first.text
    assert first.json()["transaction_type"] == "DEPOSIT"

    # Repeat the same request with the same idempotency key.
    second = client.post(
        "/api/transactions/deposit",
        headers=auth_headers(token),
        json=deposit_payload,
    )
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first.json()["id"]

    wallet_response = client.get(
        f"/api/wallets/{wallet['id']}",
        headers=auth_headers(token),
    )
    assert wallet_response.status_code == 200
    assert float(wallet_response.json()["available_balance"]) == 100.00

    withdrawal = client.post(
        "/api/transactions/withdraw",
        headers=auth_headers(token),
        json={
            "wallet_id": wallet["id"],
            "amount": "30.00",
            "idempotency_key": f"withdraw-{uuid4().hex[:16]}",
            "description": "Test withdrawal",
        },
    )
    assert withdrawal.status_code == 201, withdrawal.text
    assert withdrawal.json()["transaction_type"] == "WITHDRAWAL"

    wallet_response = client.get(
        f"/api/wallets/{wallet['id']}",
        headers=auth_headers(token),
    )
    assert float(wallet_response.json()["available_balance"]) == 70.00


def test_withdrawal_exceeding_balance_is_rejected(client):
    email, password, _ = register_user(client)
    token = login_user(client, email, password)
    wallet = create_wallet(client, token)

    response = client.post(
        "/api/transactions/withdraw",
        headers=auth_headers(token),
        json={
            "wallet_id": wallet["id"],
            "amount": "10.00",
            "idempotency_key": f"withdraw-{uuid4().hex[:16]}",
        },
    )

    assert response.status_code >= 400


def test_transfer_between_two_users(client):
    email_a, password_a, _ = register_user(client)
    token_a = login_user(client, email_a, password_a)
    wallet_a = create_wallet(client, token_a, "Sender")

    email_b, password_b, _ = register_user(client)
    token_b = login_user(client, email_b, password_b)
    wallet_b = create_wallet(client, token_b, "Receiver")

    deposit = client.post(
        "/api/transactions/deposit",
        headers=auth_headers(token_a),
        json={
            "wallet_id": wallet_a["id"],
            "amount": "200.00",
            "idempotency_key": f"deposit-{uuid4().hex[:16]}",
        },
    )
    assert deposit.status_code == 201, deposit.text

    transfer = client.post(
        "/api/transactions/transfer",
        headers=auth_headers(token_a),
        json={
            "source_wallet_id": wallet_a["id"],
            "destination_wallet_id": wallet_b["id"],
            "amount": "50.00",
            "idempotency_key": f"transfer-{uuid4().hex[:16]}",
            "description": "Test transfer",
        },
    )
    assert transfer.status_code == 201, transfer.text
    assert transfer.json()["transaction_type"] == "TRANSFER_OUT"

    sender_wallet = client.get(
        f"/api/wallets/{wallet_a['id']}",
        headers=auth_headers(token_a),
    ).json()

    receiver_wallet = client.get(
        f"/api/wallets/{wallet_b['id']}",
        headers=auth_headers(token_b),
    ).json()

    assert float(sender_wallet["available_balance"]) == 150.00
    assert float(receiver_wallet["available_balance"]) == 50.00


def test_transaction_history(client):
    email, password, _ = register_user(client)
    token = login_user(client, email, password)
    wallet = create_wallet(client, token)

    deposit = client.post(
        "/api/transactions/deposit",
        headers=auth_headers(token),
        json={
            "wallet_id": wallet["id"],
            "amount": "25.00",
            "idempotency_key": f"deposit-{uuid4().hex[:16]}",
        },
    )
    assert deposit.status_code == 201, deposit.text

    history = client.get(
        f"/api/transactions/wallet/{wallet['id']}",
        headers=auth_headers(token),
    )

    assert history.status_code == 200, history.text
    assert any(
        item["id"] == deposit.json()["id"]
        for item in history.json()
    )


    
def test_negative_deposit_amount_is_rejected(client):
    email, password, _ = register_user(client)
    token = login_user(client, email, password)
    wallet = create_wallet(client, token)

    response = client.post(
        "/api/transactions/deposit",
        headers=auth_headers(token),
        json={
            "wallet_id": wallet["id"],
            "amount": "-10.00",
            "idempotency_key": f"negative-{uuid4().hex[:16]}",
        },
    )

    assert response.status_code == 422, response.text


def test_frozen_wallet_rejects_deposit(client):
    email, password, _ = register_user(client)
    token = login_user(client, email, password)
    wallet = create_wallet(client, token)

    freeze_response = client.post(
        f"/api/wallets/{wallet['id']}/freeze",
        headers=auth_headers(token),
    )
    assert freeze_response.status_code == 200, freeze_response.text

    deposit_response = client.post(
        "/api/transactions/deposit",
        headers=auth_headers(token),
        json={
            "wallet_id": wallet["id"],
            "amount": "50.00",
            "idempotency_key": f"frozen-{uuid4().hex[:16]}",
        },
    )

    assert deposit_response.status_code in (400, 409), deposit_response.text

    wallet_response = client.get(
        f"/api/wallets/{wallet['id']}",
        headers=auth_headers(token),
    )
    assert wallet_response.status_code == 200
    assert float(wallet_response.json()["available_balance"]) == 0.0


def test_idempotency_key_cannot_be_reused_for_different_amount(client):
    email, password, _ = register_user(client)
    token = login_user(client, email, password)
    wallet = create_wallet(client, token)
    key = f"same-key-{uuid4().hex[:16]}"

    payload = {
        "wallet_id": wallet["id"],
        "amount": "100.00",
        "idempotency_key": key,
    }

    first = client.post(
        "/api/transactions/deposit",
        headers=auth_headers(token),
        json=payload,
    )
    assert first.status_code == 201, first.text

    changed_payload = {
        **payload,
        "amount": "200.00",
    }
    second = client.post(
        "/api/transactions/deposit",
        headers=auth_headers(token),
        json=changed_payload,
    )

    assert second.status_code == 409, second.text

    wallet_response = client.get(
        f"/api/wallets/{wallet['id']}",
        headers=auth_headers(token),
    )
    assert wallet_response.status_code == 200
    assert float(wallet_response.json()["available_balance"]) == 100.0


def test_transfer_rejects_different_currencies(client):
    email_a, password_a, _ = register_user(client)
    token_a = login_user(client, email_a, password_a)
    wallet_a = create_wallet(client, token_a, "INR Wallet", "INR")

    email_b, password_b, _ = register_user(client)
    token_b = login_user(client, email_b, password_b)
    wallet_b = create_wallet(client, token_b, "USD Wallet", "USD")

    deposit = client.post(
        "/api/transactions/deposit",
        headers=auth_headers(token_a),
        json={
            "wallet_id": wallet_a["id"],
            "amount": "100.00",
            "idempotency_key": f"fund-{uuid4().hex[:16]}",
        },
    )
    assert deposit.status_code == 201, deposit.text

    transfer = client.post(
        "/api/transactions/transfer",
        headers=auth_headers(token_a),
        json={
            "source_wallet_id": wallet_a["id"],
            "destination_wallet_id": wallet_b["id"],
            "amount": "25.00",
            "idempotency_key": f"currency-{uuid4().hex[:16]}",
        },
    )

    assert transfer.status_code in (400, 409), transfer.text

    sender = client.get(
        f"/api/wallets/{wallet_a['id']}",
        headers=auth_headers(token_a),
    )
    receiver = client.get(
        f"/api/wallets/{wallet_b['id']}",
        headers=auth_headers(token_b),
    )

    assert float(sender.json()["available_balance"]) == 100.0
    assert float(receiver.json()["available_balance"]) == 0.0




def test_concurrent_withdrawals_cannot_overspend(client):
    email, password, _ = register_user(client)
    token = login_user(client, email, password)
    wallet = create_wallet(client, token)

    # Fund the wallet with 100.00
    deposit = client.post(
        "/api/transactions/deposit",
        headers=auth_headers(token),
        json={
            "wallet_id": wallet["id"],
            "amount": "100.00",
            "idempotency_key": f"fund-{uuid4().hex[:16]}",
        },
    )
    assert deposit.status_code == 201, deposit.text

    # Both requests start together and attempt to withdraw 80.00.
    barrier = Barrier(2)

    def withdraw(key):
        payload = {
            "wallet_id": wallet["id"],
            "amount": "80.00",
            "idempotency_key": key,
            "description": "Concurrent withdrawal test",
        }

        barrier.wait(timeout=10)

        return client.post(
            "/api/transactions/withdraw",
            headers=auth_headers(token),
            json=payload,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_one = executor.submit(
            withdraw, f"withdraw-{uuid4().hex[:16]}"
        )
        future_two = executor.submit(
            withdraw, f"withdraw-{uuid4().hex[:16]}"
        )

        response_one = future_one.result(timeout=30)
        response_two = future_two.result(timeout=30)

    statuses = [response_one.status_code, response_two.status_code]

    # Only one withdrawal should succeed.
    assert statuses.count(201) == 1, (
        f"Expected one successful withdrawal, got {statuses}. "
        f"Responses: {response_one.text} | {response_two.text}"
    )

    # The other request should fail due to insufficient funds.
    assert sum(status >= 400 for status in statuses) == 1, statuses

    # The wallet must retain exactly 20.00.
    wallet_response = client.get(
        f"/api/wallets/{wallet['id']}",
        headers=auth_headers(token),
    )
    assert wallet_response.status_code == 200, wallet_response.text
    assert float(wallet_response.json()["available_balance"]) == 20.0


def test_deposit_above_single_transaction_limit_is_rejected(client):
    email, password, _ = register_user(client)
    token = login_user(client, email, password)
    wallet = create_wallet(client, token)

    response = client.post(
        "/api/transactions/deposit",
        headers=auth_headers(token),
        json={
            "wallet_id": wallet["id"],
            "amount": "50000.01",
            "idempotency_key": f"deposit-{uuid4().hex[:16]}",
        },
    )

    assert response.status_code == 409, response.text


def test_withdrawal_above_single_transaction_limit_is_rejected(client):
    email, password, _ = register_user(client)
    token = login_user(client, email, password)
    wallet = create_wallet(client, token)

    deposit = client.post(
        "/api/transactions/deposit",
        headers=auth_headers(token),
        json={
            "wallet_id": wallet["id"],
            "amount": "30000.00",
            "idempotency_key": f"fund-{uuid4().hex[:16]}",
        },
    )
    assert deposit.status_code == 201, deposit.text

    response = client.post(
        "/api/transactions/withdraw",
        headers=auth_headers(token),
        json={
            "wallet_id": wallet["id"],
            "amount": "25000.01",
            "idempotency_key": f"withdraw-{uuid4().hex[:16]}",
        },
    )

    assert response.status_code == 409, response.text


def test_daily_outgoing_limit_combines_withdrawals_and_transfers(client):
    email_a, password_a, _ = register_user(client)
    token_a = login_user(client, email_a, password_a)
    source_wallet = create_wallet(client, token_a, "Sender")

    email_b, password_b, _ = register_user(client)
    token_b = login_user(client, email_b, password_b)
    destination_wallet = create_wallet(client, token_b, "Receiver")

    # Two deposits fund the sender with 60,000.
    for amount in ("30000.00", "30000.00"):
        response = client.post(
            "/api/transactions/deposit",
            headers=auth_headers(token_a),
            json={
                "wallet_id": source_wallet["id"],
                "amount": amount,
                "idempotency_key": f"fund-{uuid4().hex[:16]}",
            },
        )
        assert response.status_code == 201, response.text

    withdrawal = client.post(
        "/api/transactions/withdraw",
        headers=auth_headers(token_a),
        json={
            "wallet_id": source_wallet["id"],
            "amount": "25000.00",
            "idempotency_key": f"withdraw-{uuid4().hex[:16]}",
        },
    )
    assert withdrawal.status_code == 201, withdrawal.text

    transfer = client.post(
        "/api/transactions/transfer",
        headers=auth_headers(token_a),
        json={
            "source_wallet_id": source_wallet["id"],
            "destination_wallet_id": destination_wallet["id"],
            "amount": "25000.00",
            "idempotency_key": f"transfer-{uuid4().hex[:16]}",
        },
    )
    assert transfer.status_code == 201, transfer.text

    # The customer has now used the full daily outgoing allowance.
    extra_withdrawal = client.post(
        "/api/transactions/withdraw",
        headers=auth_headers(token_a),
        json={
            "wallet_id": source_wallet["id"],
            "amount": "1.00",
            "idempotency_key": f"extra-{uuid4().hex[:16]}",
        },
    )
    assert extra_withdrawal.status_code == 409, extra_withdrawal.text

    source_response = client.get(
        f"/api/wallets/{source_wallet['id']}",
        headers=auth_headers(token_a),
    )
    assert source_response.status_code == 200
    assert float(source_response.json()["available_balance"]) == 10000.0



def _assign_role(email, role_name):
    """Test helper: promote a registered user to a chosen role."""
    from sqlalchemy import select

    from app.database.database import SessionLocal
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        role = db.scalar(select(Role).where(Role.name == role_name))

        assert user is not None, f"User not found: {email}"
        assert role is not None, f"Role not found: {role_name}"

        user.role_id = role.id
        db.commit()
    finally:
        db.close()


def test_refresh_token_rotation(client):
    email, password, _ = register_user(client)
    tokens = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert tokens.status_code == 200, tokens.text

    old_refresh = tokens.json()["refresh_token"]

    refreshed = client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert refreshed.status_code == 200, refreshed.text

    new_refresh = refreshed.json()["refresh_token"]
    assert new_refresh != old_refresh

    # A rotated refresh token must not be reusable.
    replay = client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert replay.status_code == 401, replay.text

    # The replacement token should work.
    next_refresh = client.post(
        "/api/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert next_refresh.status_code == 200, next_refresh.text


def test_logout_revokes_refresh_token(client):
    email, password, _ = register_user(client)
    tokens_response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert tokens_response.status_code == 200, tokens_response.text

    tokens = tokens_response.json()

    logout_response = client.post(
        "/api/auth/logout",
        headers=auth_headers(tokens["access_token"]),
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout_response.status_code == 200, logout_response.text

    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 401, refresh_response.text


def test_password_change_revokes_refresh_tokens(client):
    email, old_password, _ = register_user(client)
    tokens_response = client.post(
        "/api/auth/login",
        json={"email": email, "password": old_password},
    )
    assert tokens_response.status_code == 200, tokens_response.text

    tokens = tokens_response.json()
    new_password = "NewWalletPass456!"

    change_response = client.post(
        "/api/auth/change-password",
        headers=auth_headers(tokens["access_token"]),
        json={
            "current_password": old_password,
            "new_password": new_password,
        },
    )
    assert change_response.status_code == 200, change_response.text

    # Existing refresh tokens must no longer work.
    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 401, refresh_response.text

    # The new password should allow a fresh login.
    login_response = client.post(
        "/api/auth/login",
        json={"email": email, "password": new_password},
    )
    assert login_response.status_code == 200, login_response.text

    # The old password must be rejected.
    old_login = client.post(
        "/api/auth/login",
        json={"email": email, "password": old_password},
    )
    assert old_login.status_code == 401, old_login.text


def test_customer_cannot_access_admin_endpoints(client):
    email, password, _ = register_user(client)
    token = login_user(client, email, password)

    audit_response = client.get(
        "/api/audit-logs",
        headers=auth_headers(token),
    )
    assert audit_response.status_code == 403, audit_response.text

    suspicious_response = client.get(
        "/api/suspicious-activities",
        headers=auth_headers(token),
    )
    assert suspicious_response.status_code == 403, suspicious_response.text


def test_admin_can_review_suspicious_activity(client):
    # Register the customer whose transaction will trigger a flag.
    customer_email, customer_password, _ = register_user(client)
    customer_token = login_user(
        client, customer_email, customer_password
    )
    wallet = create_wallet(client, customer_token)

    # The configured high-value threshold is 25,000.
    deposit = client.post(
        "/api/transactions/deposit",
        headers=auth_headers(customer_token),
        json={
            "wallet_id": wallet["id"],
            "amount": "25000.00",
            "idempotency_key": f"high-value-{uuid4().hex}",
        },
    )
    assert deposit.status_code == 201, deposit.text

    # Register a separate user and promote it for this test.
    admin_email, admin_password, _ = register_user(client)
    _assign_role(admin_email, "Admin")
    admin_token = login_user(client, admin_email, admin_password)

    list_response = client.get(
        "/api/suspicious-activities",
        headers=auth_headers(admin_token),
    )
    assert list_response.status_code == 200, list_response.text

    activities = list_response.json()
    activity = next(
        (
            item for item in activities
            if item["transaction_id"] == deposit.json()["id"]
            and item["reason"] == "HIGH_VALUE_TRANSACTION"
        ),
        None,
    )
    assert activity is not None, activities
    assert activity["status"] == "OPEN"

    review_response = client.patch(
        f"/api/suspicious-activities/{activity['id']}/review",
        headers=auth_headers(admin_token),
        json={
            "status": "REVIEWED",
            "review_notes": "Reviewed during automated testing.",
        },
    )
    assert review_response.status_code == 200, review_response.text
    assert review_response.json()["status"] == "REVIEWED"
    assert review_response.json()["reviewed_by"] is not None

    # Verify an administrator can also access audit logs.
    audit_response = client.get(
        "/api/audit-logs",
        headers=auth_headers(admin_token),
    )
    assert audit_response.status_code == 200, audit_response.text
