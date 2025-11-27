#!/usr/bin/env python3
"""
Run a registration POST against the local auth service and then tail compose logs
for `auth` and `db_worker`. Cross-platform (no external Python dependencies).

Usage:
  python scripts/register_and_tail.py [email] [password]

Examples:
  python scripts/register_and_tail.py
  python scripts/register_and_tail.py test@example.com StrongPass1!
"""
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error

DEFAULT_EMAIL = "ci-user@example.com"
EMAIL = sys.argv[1] if len(sys.argv) > 1 else None
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else "StrongPass1!"

# If no email was provided, generate a unique CI email to avoid duplicates
if EMAIL is None:
    local, domain = DEFAULT_EMAIL.split("@", 1)
    ts = int(time.time())
    EMAIL = f"{local}+{ts}@{domain}"

def post_register(email: str, password: str, timeout: int = 10):
    url = "http://localhost:8000/register"
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            print("REGISTER_OK")
            print(body)
            return True
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        print(f"REGISTER_FAILED status={e.code} reason={e.reason} body={body}")
        return False
    except Exception as e:
        print("REGISTER_FAILED", e)
        return False

def tail_logs(services, tail=200):
    for svc in services:
        print(f"\n--- docker-compose logs {svc} (last {tail} lines) ---\n")
        subprocess.run(["docker-compose", "logs", "--no-color", "--timestamps", svc, f"--tail={tail}"])

def main():
    print(f"Registering user: {EMAIL}")
    ok = post_register(EMAIL, PASSWORD)
    # give the consumer a short moment to process
    time.sleep(1)
    tail_logs(["auth", "db_worker"], tail=200)
    if not ok:
        sys.exit(1)

if __name__ == "__main__":
    main()
