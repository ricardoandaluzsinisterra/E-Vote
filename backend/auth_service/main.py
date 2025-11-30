import os
import json
import uuid
import logging
import urllib.request
import urllib.error
import urllib.parse
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from aiokafka import AIOKafkaProducer

from auth_service.auth.password_utils import *
from auth_service.auth.jwt_handler import generate_tokens
from models.User import User
from models.auth_models import *

logger = logging.getLogger(__name__)
logging.basicConfig(filename='myapp.log', level=logging.INFO)

# Kafka producer (initialized on startup)
producer: AIOKafkaProducer | None = None

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

SERVICE_ROLE = "auth"
DB_OPS_URL = os.getenv("DB_OPS_URL", "http://db_ops:8001")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
POST_USER_TOPIC = os.getenv("KAFKA_POSTGRES_TOPIC", "user.postgres.ops")

@app.on_event("startup")
async def startup():
    global producer
    try:
        producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
        await producer.start()
        logger.info("Kafka producer started (bootstrap=%s)", KAFKA_BOOTSTRAP)
    except Exception as e:
        logger.warning("Failed to start Kafka producer: %s", e)

@app.on_event("shutdown")
async def shutdown():
    global producer
    if producer:
        try:
            await producer.stop()
            logger.info("Kafka producer stopped")
        except Exception as e:
            logger.warning("Error stopping Kafka producer: %s", e)

@app.get("/health")
async def health():
    return {"status": "ok", "role": SERVICE_ROLE}

@app.post("/register")
async def register_user(user_data: UserRegistrationRequest) -> RegistrationSuccessResponse:
    """
    Registration is now asynchronous: auth validates input, generates verification token and a UUID user id,
    and publishes a create event to Kafka. db_ops_service is responsible for persisting to Postgres and Redis.
    """
    password_strength = validate_password_strength(user_data.password)
    if not password_strength.get("valid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_strength.get("message")
        )

    # Create a lightweight user object and generate verification token locally
    new_user = User.from_user_registration_request(user_data)
    new_user.password_hash = hash_password(user_data.password)
    new_user.verification_token = f"{uuid.uuid4()}-{int(__import__('time').time())}"

    # Check if user already exists to avoid duplicate insert errors
    try:
        lookup_url = f"{DB_OPS_URL.rstrip('/')}/db/user-by-email?email={urllib.parse.quote(new_user.email)}"
        req_lookup = urllib.request.Request(lookup_url, method="GET")
        with urllib.request.urlopen(req_lookup, timeout=3) as resp_lookup:
            if resp_lookup.status == 200:
                # User already exists
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")
    except urllib.error.HTTPError as e:
        # 404 means user not found (expected), other errors bubble up
        if getattr(e, 'code', None) != 404:
            logger.warning("db_ops lookup HTTPError during register %s", getattr(e, 'code', None))
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User lookup service unavailable")
    except Exception as e:
        # timeout or other network errors
        logger.exception("Failed to call db_ops_service for pre-create lookup: %s", e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User lookup service unavailable")

    # Synchronously request db_ops_service to persist the user so we get an integer user_id
    try:
        create_url = f"{DB_OPS_URL.rstrip('/')}/db/create"
        req_payload = {
            "email": new_user.email,
            "password_hash": new_user.password_hash,
            "verification_token": new_user.verification_token
        }
        req_data = json.dumps(req_payload).encode("utf-8")
        req = urllib.request.Request(create_url, data=req_data, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                body = resp.read().decode() if resp else ""
                logger.warning("db_ops create returned %s: %s", resp.status, body)
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User persistence service unavailable")
            body = resp.read().decode("utf-8")
            created = json.loads(body)
    except urllib.error.HTTPError as e:
        body = None
        try:
            body = e.read().decode()
        except Exception:
            pass
        logger.warning("db_ops create HTTPError %s: %s", getattr(e, 'code', None), body)
        # If db_ops returns 409 (duplicate), propagate 409 to the client
        if getattr(e, 'code', None) == 409:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User persistence failed")
    except Exception as e:
        logger.exception("Failed to call db_ops_service create: %s", e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User persistence unavailable")

    # `created` should contain integer `user_id` and created_at
    return RegistrationSuccessResponse(
        user=UserResponse(
            user_id=int(created.get("user_id")),
            email=created.get("email"),
            is_verified=created.get("is_verified", False),
            created_at=created.get("created_at")
        ),
        verification_token=new_user.verification_token
    )

@app.post("/login")
async def login_user(user_data: UserLoginRequest) -> TokenResponse:
    """
    Login flow delegates user lookup to the db_ops_service HTTP read endpoint.
    This keeps Postgres/Redis connections inside db_ops_service while still allowing auth to respond synchronously.
    """
    # Query db_ops_service for user by email
    import urllib.parse
    url = f"{DB_OPS_URL.rstrip('/')}/db/user-by-email?email={urllib.parse.quote(user_data.email)}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except urllib.error.HTTPError as e:
        body = None
        try:
            body = e.read().decode()
        except Exception:
            pass
        logger.warning("db_ops lookup HTTPError %s: %s", getattr(e, 'code', None), body)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    except Exception as e:
        logger.exception("Failed to call db_ops_service for user lookup: %s", e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User lookup service unavailable")

    # data should contain user fields
    user = User(
        user_id=data.get("user_id"),
        email=data.get("email"),
        password_hash=data.get("password_hash"),
        is_verified=data.get("is_verified"),
        verification_token=data.get("verification_token"),
        created_at=data.get("created_at")
    )

    if user is None or user.email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(user.password_hash, user_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email before logging in."
        )

    access_token = generate_tokens(user_id=user.user_id, email=user.email)
    return TokenResponse(access_token=access_token, token_type="bearer")


# Internal endpoints for other services to centralize auth logic
@app.post("/internal/hash-password")
async def internal_hash_password(payload: dict):
    """Return Argon2 hash for a plain password. Intended for internal use only."""
    password = payload.get("password")
    if not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="password required")
    try:
        hashed = hash_password(password)
        return {"password_hash": hashed}
    except Exception as e:
        logger.exception("Internal hash failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="hash failed")


@app.post("/internal/verify-password")
async def internal_verify_password(payload: dict):
    """Verify a plain password against a stored hash. Intended for internal use only."""
    password_hash = payload.get("password_hash")
    password = payload.get("password")
    if password_hash is None or password is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="password_hash and password required")
    try:
        valid = verify_password(password_hash, password)
        return {"valid": bool(valid)}
    except Exception as e:
        logger.exception("Internal verify failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="verify failed")
