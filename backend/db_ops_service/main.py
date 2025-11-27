import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import logging

from db_ops_service.database.connection import DatabaseManager, get_database
from db_ops_service.database.operations import get_user_by_id, get_user_by_email_as_user, verify_user, update_user_password
from auth.password_utils import hash_password
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

@app.post("/db/verify")
async def api_verify_user(token: VerificationTokenRequest, db: DatabaseManager = Depends(get_database)):
    temp_user = User(verification_token=token.verification_token)
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
    temp_user = User(user_id=req.user_id)
    new_hash = hash_password(req.new_password)
    updated = update_user_password(db.get_cursor(), temp_user, new_hash)
    # Invalidate Redis cache for this user id/email if possible
    try:
        redis_client = DatabaseManager().redis_client
        if redis_client and updated.email:
            cache_key = f"user:email:{updated.email}"
            redis_client.delete(cache_key)
    except Exception:
        pass
