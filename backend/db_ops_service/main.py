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

@app.post("/redis/store-otp")
async def redis_store_otp(payload: dict, db: DatabaseManager = Depends(get_database)):
    """
    Store OTP in Redis with expiration.
    """
    email = payload.get("email")
    otp = payload.get("otp")
    user_type = payload.get("user_type", "voter")
    expiry_seconds = payload.get("expiry_seconds", 600)
    
    if not email or not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email and otp required"
        )
    
    try:
        redis_client = db.redis_client
        if not redis_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis unavailable"
            )
        
        # Store OTP
        otp_key = f"otp:{user_type}:{email}"
        redis_client.setex(otp_key, expiry_seconds, otp)
        
        # Reset attempt counter
        attempts_key = f"otp:attempts:{user_type}:{email}"
        redis_client.delete(attempts_key)
        
        logger.info("OTP stored for %s (type=%s, expires in %ds)", email, user_type, expiry_seconds)
        return {"status": "stored", "expires_in": expiry_seconds}
        
    except Exception as e:
        logger.exception("Failed to store OTP in Redis: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store OTP"
        )


@app.post("/redis/verify-otp")
async def redis_verify_otp(payload: dict, db: DatabaseManager = Depends(get_database)):
    """
    Verify OTP from Redis and delete it after successful verification.
    """
    email = payload.get("email")
    otp = payload.get("otp")
    user_type = payload.get("user_type", "voter")
    max_attempts = 5
    
    if not email or not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email and otp required"
        )
    
    try:
        redis_client = db.redis_client
        if not redis_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis unavailable"
            )
        
        otp_key = f"otp:{user_type}:{email}"
        attempts_key = f"otp:attempts:{user_type}:{email}"
        
        # Check attempt count
        attempts = redis_client.get(attempts_key)
        current_attempts = int(attempts) if attempts else 0
        
        if current_attempts >= max_attempts:
            logger.warning("Max OTP attempts reached for %s", email)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Maximum OTP verification attempts exceeded. Please request a new OTP."
            )
        
        # Get stored OTP
        stored_otp = redis_client.get(otp_key)
        
        if not stored_otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP expired or not found. Please request a new OTP."
            )
        
        # Increment attempt counter
        redis_client.incr(attempts_key)
        redis_client.expire(attempts_key, 600)  # Expire with OTP
        
        # Verify OTP
        if stored_otp != otp:
            remaining_attempts = max_attempts - (current_attempts + 1)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OTP. {remaining_attempts} attempts remaining."
            )
        
        # OTP is valid - delete it so it can't be reused
        redis_client.delete(otp_key)
        redis_client.delete(attempts_key)
        
        logger.info("OTP verified successfully for %s (type=%s)", email, user_type)
        return {"verified": True, "email": email}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to verify OTP: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify OTP"
        )
    
@app.post("/db/mark-verified")
async def mark_user_verified(payload: dict, db: DatabaseManager = Depends(get_database)):
    """
    Mark user account as verified after OTP verification.
    """
    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email required"
        )
    
    try:
        cursor = db.get_cursor()
        cursor.execute(
            "UPDATE users SET is_verified = TRUE WHERE email = %s",
            (email,)
        )
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Invalidate Redis cache
        try:
            redis_client = db.redis_client
            if redis_client:
                cache_key = f"user:email:{email}"
                redis_client.delete(cache_key)
        except Exception:
            pass
        
        logger.info("User marked as verified: %s", email)
        return {"status": "verified", "email": email}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to mark user as verified: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update verification status"
        )


@app.post("/db/store-candidate")
async def store_candidate(payload: dict, db: DatabaseManager = Depends(get_database)):
    """
    Store candidate record in database.
    """
    try:
        cursor = db.get_cursor()
        
        # Create candidates table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                party VARCHAR(255),
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert candidate
        cursor.execute("""
            INSERT INTO candidates (name, party, description)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (
            payload.get("name"),
            payload.get("party", ""),
            payload.get("description", "")
        ))
        
        candidate_id = cursor.fetchone()[0]
        logger.info("Candidate stored: %s (id=%s)", payload.get("name"), candidate_id)
        return {"status": "stored", "candidate_id": candidate_id, "name": payload.get("name")}
    except Exception as e:
        logger.exception("Failed to store candidate: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store candidate"
        )


@app.post("/db/store-voter-record")
async def store_voter_record(payload: dict, db: DatabaseManager = Depends(get_database)):
    """
    Store pending voter record with registration token.
    """
    try:
        cursor = db.get_cursor()
        
        # Create voter_records table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voter_records (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                phone_number VARCHAR(50) NOT NULL,
                voter_id VARCHAR(100) UNIQUE NOT NULL,
                registration_token VARCHAR(500) UNIQUE NOT NULL,
                token_used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert voter record
        cursor.execute("""
            INSERT INTO voter_records 
            (email, full_name, phone_number, voter_id, registration_token)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE
            SET registration_token = EXCLUDED.registration_token,
                token_used = FALSE
        """, (
            payload["email"],
            payload["full_name"],
            payload["phone_number"],
            payload["voter_id"],
            payload["registration_token"]
        ))
        
        logger.info("Voter record stored: %s", payload["email"])
        return {"status": "stored", "email": payload["email"]}
    except Exception as e:
        logger.exception("Failed to store voter record: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store voter record"
        )


@app.post("/db/verify-voter-token")
async def verify_voter_token(payload: dict, db: DatabaseManager = Depends(get_database)):
    """
    Verify voter registration token and return voter data if valid.
    """
    token = payload.get("token")
    email = payload.get("email")
    
    if not token or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="token and email required"
        )
    
    try:
        cursor = db.get_cursor()
        
        cursor.execute("""
            SELECT email, full_name, phone_number, voter_id, token_used
            FROM voter_records
            WHERE registration_token = %s AND email = %s
        """, (token, email))
        
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid token or email"
            )
        
        if row[4]:  # token_used
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration token has already been used"
            )
        
        return {
            "email": row[0],
            "full_name": row[1],
            "phone_number": row[2],
            "voter_id": row[3]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to verify voter token: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token verification failed"
        )


@app.post("/db/create-voter")
async def create_voter(payload: dict, db: DatabaseManager = Depends(get_database)):
    """
    Create voter account and mark registration token as used.
    """
    try:
        cursor = db.get_cursor()
        
        # Mark token as used
        cursor.execute("""
            UPDATE voter_records
            SET token_used = TRUE
            WHERE registration_token = %s AND email = %s
        """, (payload["registration_token"], payload["email"]))
        
        # Create user account
        cursor.execute("""
            INSERT INTO users 
            (email, password_hash, is_verified, verification_token, created_at)
            VALUES (%s, %s, TRUE, %s, CURRENT_TIMESTAMP)
            RETURNING id, email, is_verified, created_at
        """, (
            payload["email"],
            payload["password_hash"],
            payload["registration_token"]
        ))
        
        row = cursor.fetchone()
        logger.info("Voter account created: %s", payload["email"])
        
        return {
            "user_id": row[0],
            "email": row[1],
            "is_verified": row[2],
            "created_at": str(row[3])
        }
    except Exception as e:
        logger.exception("Failed to create voter account: %s", e)
        
        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account creation failed"
        )