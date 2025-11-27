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

from auth.password_utils import *
from auth.jwt_handler import generate_tokens
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

SERVICE_ROLE = "backend"
DB_OPS_URL = os.getenv("DB_OPS_URL", "http://db-ops-service:8001")
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
    Register: validate input locally, generate verification token and temporary id,
    then publish a create event to Kafka. db_ops_service owns DB/Redis persistence.
    """
    password_strength = validate_password_strength(user_data.password)
    if not password_strength.get("valid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_strength.get("message")
        )

    new_user = User.from_user_registration_request(user_data)
    new_user.password_hash = hash_password(user_data.password)
    new_user.verification_token = f"{uuid.uuid4()}-{int(__import__('time').time())}"
    new_user.user_id = str(uuid.uuid4())

    payload = {
        "op": "create",
        "resource": "user",
        "event": "user.registered",
        "payload": {
            "user_id": new_user.user_id,
            "email": new_user.email,
            "password_hash": new_user.password_hash,
            "verification_token": new_user.verification_token
        },
        "meta": {"source": "backend", "topic": POST_USER_TOPIC}
    }

    try:
        if producer:
            await producer.send_and_wait(POST_USER_TOPIC, json.dumps(payload).encode())
            logger.info("Published user.create event for email=%s", new_user.email)
    except Exception as e:
        logger.warning("Failed to publish user.create event: %s", e)

    return RegistrationSuccessResponse(
        user=UserResponse(
            user_id=new_user.user_id,
            email=new_user.email,
            is_verified=new_user.is_verified,
            created_at=str(new_user.created_at)
        ),
        verification_token=new_user.verification_token
    )

@app.post("/login")
async def login_user(user_data: UserLoginRequest) -> TokenResponse:
    """
    Login: perform synchronous read from db_ops_service HTTP endpoint to keep DB connections centralized.
    """
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
