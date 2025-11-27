#!/usr/bin/env python3
"""
verify_and_login.py

- Marks a user as verified in Postgres (via docker-compose exec psql)
- Attempts to login via the auth service (/login)
- Prints DB rows before/after and the login response

Usage:
    python scripts/verify_and_login.py --email ci-user@example.com --password StrongPass1!
"""
import argparse
import subprocess
import json
import sys
import urllib.request
import urllib.error

def run_psql_query(sql: str) -> subprocess.CompletedProcess:
    cmd = [
        "docker-compose",
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "postgres",
        "-d",
        "user_info_db",
        "-c",
        sql
    ]
    return subprocess.run(cmd, capture_output=True, text=True)

def print_section(title: str):
    print("\n" + "="*10 + f" {title} " + "="*10 + "\n")

def mark_verified(email: str) -> bool:
    # Show before
    print_section("Before updating user")
    before = run_psql_query(f"SELECT id,email,is_verified,verification_token,created_at FROM users WHERE email='{email}';")
    print(before.stdout)
    if before.returncode != 0:
        print("psql error (before):", before.stderr, file=sys.stderr)

    # Update is_verified
    print_section("Updating is_verified = true")
    upd = run_psql_query(f"UPDATE users SET is_verified = true WHERE email='{email}';")
    if upd.returncode != 0:
        print("psql update error:", upd.stderr, file=sys.stderr)
        return False
    else:
        print(upd.stdout)

    # Show after
    print_section("After updating user")
    after = run_psql_query(f"SELECT id,email,is_verified,verification_token,created_at FROM users WHERE email='{email}';")
    print(after.stdout)
    if after.returncode != 0:
        print("psql error (after):", after.stderr, file=sys.stderr)
    return True

def attempt_login(email: str, password: str):
    url = "http://localhost:8000/login"
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    print_section("Attempting login")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            print("HTTP", resp.status)
            try:
                parsed = json.loads(body)
                print(json.dumps(parsed, indent=2))
            except Exception:
                print(body)
            return True
    except urllib.error.HTTPError as e:
        print("HTTPError:", e.code, e.reason)
        try:
            print(e.read().decode())
        except Exception:
            pass
        return False
    except Exception as e:
        print("Request failed:", str(e))
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", "-e", default="ci-user@example.com")
    parser.add_argument("--password", "-p", default="StrongPass1!")
    args = parser.parse_args()

    ok = mark_verified(args.email)
    if not ok:
        print("Failed to mark user verified. Aborting login attempt.", file=sys.stderr)
        sys.exit(2)

    success = attempt_login(args.email, args.password)
    if success:
        print_section("RESULT")
        print("Login succeeded (see token above if returned).")
        sys.exit(0)
    else:
        print_section("RESULT")
        print("Login failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
