import subprocess
import json
import urllib.request
import urllib.error
import pytest
import time

POSTGRES_SERVICE = "postgres"
DB_NAME = "user_info_db"
PSQL_USER = "postgres"
AUTH_URL = "http://localhost:8000"

def run_psql(sql: str) -> subprocess.CompletedProcess:
    cmd = [
        "docker-compose",
        "exec",
        "-T",
        POSTGRES_SERVICE,
        "psql",
        "-U",
        PSQL_USER,
        "-d",
        DB_NAME,
        "-c",
        sql,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)

@pytest.fixture(scope="module")
def email():
    return "ci-user@example.com"

@pytest.fixture(scope="module")
def ensure_services_up():
    # Give services a short moment to be reachable (useful in CI runs where compose just started)
    time.sleep(1)
    return True

def test_mark_user_verified(ensure_services_up, email):
    """
    Mark user is_verified = true in Postgres and assert the row reflects the change.
    """
    # Show before (for logs)
    before = run_psql(f"SELECT id,email,is_verified,verification_token,created_at FROM users WHERE email='{email}';")
    assert before.returncode == 0, f"psql before query failed: {before.stderr}\n{before.stdout}"

    # Update is_verified
    upd = run_psql(f"UPDATE users SET is_verified = true WHERE email='{email}';")
    assert upd.returncode == 0, f"psql update failed: {upd.stderr}\n{upd.stdout}"

    # Confirm after
    after = run_psql(f"SELECT id,email,is_verified FROM users WHERE email='{email}';")
    assert after.returncode == 0, f"psql after query failed: {after.stderr}\n{after.stdout}"
    stdout = after.stdout.lower()
    assert "true" in stdout or "t" in stdout, f"user not marked verified: {after.stdout}"

def http_post_json(path: str, payload: dict, timeout=10):
    url = AUTH_URL.rstrip("/") + path
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, body

def test_login_returns_token(ensure_services_up, email):
    """
    Attempt to login for the verified user and assert a token is returned.
    """
    payload = {"email": email, "password": "StrongPass1!"}
    try:
        status, body = http_post_json("/login", payload)
    except urllib.error.HTTPError as e:
        pytest.fail(f"Login HTTPError {e.code}: {e.read().decode()}")

    assert status == 200, f"Unexpected HTTP status: {status} body={body}"
    try:
        parsed = json.loads(body)
    except Exception:
        pytest.fail(f"Response is not JSON: {body}")

    # accept either 'access_token' or 'token' or 'jwt' as possible keys
    token_keys = ["access_token", "token", "jwt"]
    assert any(k in parsed for k in token_keys), f"No token key in response JSON: {parsed}"
