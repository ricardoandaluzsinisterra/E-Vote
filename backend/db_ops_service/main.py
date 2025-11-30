import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import logging

from db_ops_service.database.connection import DatabaseManager, get_database
from db_ops_service.database.operations import (
    create_user,
    get_user_by_id,
    get_user_by_email_as_user,
    verify_user,
    update_user_password,
)
from models.User import User
from models.auth_models import VerificationTokenRequest, UpdatePasswordRequest

logger = logging.getLogger(__name__)
logging.basicConfig(filename='myapp.log', level=logging.INFO)

app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://frontend:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

SERVICE_ROLE = "db_ops"
AUTH_URL = os.getenv("AUTH_URL", "http://auth-service:8000")

@app.on_event("startup")
async def startup():
    db = DatabaseManager()
    db.connect()
    db.initialize_tables()

@app.get("/health")
async def health():
    return {"status": "ok", "role": SERVICE_ROLE}

@app.get("/db/user/{user_id}")
async def api_get_user(user_id: int, db: DatabaseManager = Depends(get_database)):
    user = get_user_by_id(db.get_cursor(), user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "user_id": user.user_id,
        "email": user.email,
        "is_verified": user.is_verified,
        "created_at": str(user.created_at)
    }

@app.get("/db/user-by-email")
async def api_get_user_by_email(email: str, db: DatabaseManager = Depends(get_database)):
    """
    Lookup user by email. Returns full user details (including password_hash and verification_token)
    so auth_service can perform login and verification checks without holding DB connections.
    """
    user = get_user_by_email_as_user(db.get_cursor(), email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "user_id": user.user_id,
        "email": user.email,
        "password_hash": user.password_hash,
        "is_verified": user.is_verified,
        "verification_token": user.verification_token,
        "created_at": str(user.created_at)
    }


@app.post("/db/create")
async def api_create_user(payload: dict, db: DatabaseManager = Depends(get_database)):
    """
    Create a user synchronously in Postgres. Expects payload with:
      - email (str)
      - password_hash (str)
      - verification_token (str) [optional]

    Returns created user details (including integer `user_id`).
    """
    email = payload.get("email")
    password_hash = payload.get("password_hash")
    verification_token = payload.get("verification_token")

    if not email or not password_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email and password_hash required")

    # Build User object expected by create_user
    temp_user = User(user_id=0, email=email, password_hash=password_hash, is_verified=False, verification_token=verification_token)
    try:
        created = create_user(db.get_cursor(), temp_user)
        return {
            "user_id": created.user_id,
            "email": created.email,
            "is_verified": created.is_verified,
            "verification_token": created.verification_token,
            "created_at": str(created.created_at)
        }
    except Exception as e:
        # Detect unique constraint violation for email and return 409 Conflict
        try:
            import psycopg
            if isinstance(e, psycopg.IntegrityError):
                logger.warning("Duplicate email attempted: %s", email)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")
        except Exception:
            # fall through to general error handling
            pass
        logger.exception("Failed to create user: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/db/verify")
async def api_verify_user(token: VerificationTokenRequest, db: DatabaseManager = Depends(get_database)):
    # Construct a minimal User object required by verify_user
    temp_user = User(user_id=0, email="", password_hash="", verification_token=token.verification_token)
    try:
        updated = verify_user(db.get_cursor(), temp_user)
        # Optionally invalidate Redis cache for the user if present
        try:
            redis_client = DatabaseManager().redis_client
            if redis_client and updated.email:
                cache_key = f"user:email:{updated.email}"
                redis_client.delete(cache_key)
        except Exception:
            pass
        return {"status": "verified", "user_id": updated.user_id}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.post("/db/update-password")
async def api_update_password(req: UpdatePasswordRequest, db: DatabaseManager = Depends(get_database)):
    """
    Update password endpoint expects the caller (auth-service) to provide a hashed password.
    Auth-service is the single owner of hashing/verification logic and must hash the new password
    before calling this endpoint.
    """
    temp_user = User(user_id=req.user_id, email="", password_hash="")
    # Expect `req.new_password` to be plain text; delegate hashing to auth service
    try:
        import urllib.request, json
        hash_url = f"{AUTH_URL.rstrip('/')}/internal/hash-password"
        data = json.dumps({"password": req.new_password}).encode("utf-8")
        req_h = urllib.request.Request(hash_url, data=data, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req_h, timeout=5) as resp:
            if resp.status != 200:
                raise Exception(f"Auth service hash failed: {resp.status}")
            body = resp.read().decode("utf-8")
            resp_json = json.loads(body)
            new_hash = resp_json.get("password_hash")
            if not new_hash:
                raise Exception("No password_hash returned from auth service")
    except Exception as e:
        logger.exception("Failed to obtain password hash from auth service: %s", e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth service unavailable")

    updated = update_user_password(db.get_cursor(), temp_user, new_hash)
    # Invalidate Redis cache for this user id/email if possible
    try:
        redis_client = DatabaseManager().redis_client
        if redis_client and updated.email:
            cache_key = f"user:email:{updated.email}"
            redis_client.delete(cache_key)
    except Exception:
        pass
