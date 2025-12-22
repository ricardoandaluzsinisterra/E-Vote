#!/usr/bin/env python3
"""
Create an admin user (or mark existing user verified) so you can login.

Usage:
  python scripts/create_admin_mark_verified.py

Requirements:
  - Services running: auth (http://localhost:8000) and db_ops (http://localhost:8001)
  - requests library installed

What it does:
  - If user exists: calls db_ops /db/mark-verified to set is_verified = TRUE
  - If user does not exist: hashes the password via auth /internal/hash-password,
    creates the user via db_ops /db/create, then marks the user verified.
"""
import os
import sys
try:
    import requests
except Exception:
    print("Missing requests. Install with: pip install requests")
    sys.exit(1)

API_AUTH = os.getenv("API_AUTH", "http://localhost:8000").rstrip("/")
API_DB = os.getenv("API_DB", "http://localhost:8001").rstrip("/")

EMAIL = os.getenv("ADMIN_EMAIL", "d00262961@student.dkit.ie")
PASSWORD = os.getenv("ADMIN_PASSWORD", "AdminPass123!")

def user_exists():
    url = f"{API_DB}/db/user-by-email"
    try:
        r = requests.get(url, params={"email": EMAIL}, timeout=10)
        if r.status_code == 200:
            return True, r.json()
        return False, None
    except requests.exceptions.RequestException as e:
        print("ERROR: could not contact db_ops:", e)
        sys.exit(1)

def mark_verified():
    url = f"{API_DB}/db/mark-verified"
    try:
        r = requests.post(url, json={"email": EMAIL}, timeout=10)
        if r.status_code == 200:
            print("OK: user marked as verified:", EMAIL)
            return True
        else:
            print("Failed to mark verified:", r.status_code, r.text)
            return False
    except requests.exceptions.RequestException as e:
        print("ERROR: mark-verified request failed:", e)
        return False

def hash_password(password: str):
    url = f"{API_AUTH}/internal/hash-password"
    try:
        r = requests.post(url, json={"password": password}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("password_hash")
        else:
            print("Failed to hash password via auth service:", r.status_code, r.text)
            return None
    except requests.exceptions.RequestException as e:
        print("ERROR: auth service hash request failed:", e)
        return None

def create_user(password_hash: str):
    url = f"{API_DB}/db/create"
    payload = {"email": EMAIL, "password_hash": password_hash}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("OK: user created:", EMAIL)
            return True, r.json()
        else:
            print("Failed to create user:", r.status_code, r.text)
            return False, None
    except requests.exceptions.RequestException as e:
        print("ERROR: db create request failed:", e)
        return False, None

def main():
    exists, info = user_exists()
    if exists:
        print("User already exists:", info.get("email"), "is_verified=", info.get("is_verified"))
        if info.get("is_verified"):
            print("No action needed.")
            return
        print("Marking existing user as verified...")
        if mark_verified():
            print("User is now verified. You can login.")
        else:
            print("Failed to mark user verified.")
        return

    print("User not found. Creating user:", EMAIL)
    pwd_hash = hash_password(PASSWORD)
    if not pwd_hash:
        print("Cannot proceed without password hash.")
        sys.exit(1)

    ok, created = create_user(pwd_hash)
    if not ok:
        sys.exit(1)

    print("Marking newly created user as verified...")
    if not mark_verified():
        print("Warning: user created but marking verified failed.")
        sys.exit(1)

    print("Done. You can now login with the credentials and proceed with OTP flow if required.")

if __name__ == "__main__":
    main()
