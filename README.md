# E-Vote (Cinnamon) — Secure Voting Prototype

Secure, auditable online voting prototype for small-scale elections. Designed for students, community groups and small organizations to vote remotely while preserving anonymity, integrity and verifiability.

## Goals
- Enable accessible remote voting (email/OTP identity flows).
- Preserve voter anonymity and integrity using immutable, hash-chained vote records.
- Provide real-time tallying, admin controls and verifiable audit trails.
- Be deployable locally via Docker and suitable as a cloud-deployable proof-of-concept.

## Quick start
Build and run services:
```bash
docker-compose up --build
```
- Backend: http://localhost:8000
- Frontend: http://localhost:5173

## Architecture & stack
- Backend: Python, FastAPI
- Database: PostgreSQL (psycopg)
- Auth: Argon2 password hashing, JWT tokens
- Frontend: React + TypeScript (Vite)
- Orchestration: Docker Compose (backend, frontend, postgres)

## Core features
- Voter registration and authentication (email-based / OTP simulation)
- Remote voting UI (cast encrypted/hashed votes)
- Hash-chained vote storage for tamper-evidence
- Admin dashboard for election creation, voter lists, and results
- Real-time tallying and audit export

## API (examples)
Health:
```bash
curl http://localhost:8000/
```
Register:
```bash
curl -X POST http://localhost:8000/register -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"P@ssw0rd!"}'
```
Login:
```bash
curl -X POST http://localhost:8000/login -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"P@ssw0rd!"}'
```

## Configuration
- Provided via docker-compose: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB.
- Frontend uses VITE_API_URL to target the backend.
- Production: supply secrets (JWT key, DB creds) via environment variables or secret store.

## Security (actionable)
- Do not use hardcoded secrets. Move JWT signing key into env var.
- Use Argon2 for hashing; tune parameters and handle verification errors.
- Ensure transport protection (HTTPS/TLS) in production.
- Keep immutable logs, secure backups, and restricted admin access.
- Audit trails should allow voters to verify inclusion without exposing choices.

## Known issues / TODO
- Fix login password verification argument order.
- Implement email/OTP verification flow and admin features.
- Review password entropy calculation and PyJWT version compatibility.
- Harden defaults before any real deployment.

## Development notes
- DB tables created at FastAPI startup.
- Backend deps: `backend/requirements.txt`
- Frontend: `npm install` then `npm run dev` (if running outside Docker).

## Contributing & license
- Open issues / PRs. Prefer small, reviewed changes.
- License: MIT (or specify preferred license)
