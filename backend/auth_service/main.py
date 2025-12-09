import asyncio
import os
import json
import smtplib
import time
import uuid
import logging
import urllib.request
import urllib.error
import urllib.parse
import random
import string
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from aiokafka import AIOKafkaProducer

from auth_service.auth.password_utils import *
from auth_service.auth.jwt_handler import generate_tokens
from models.User import User
from models.auth_models import *
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

OTP_EXPIRY_SECONDS = 600  
MAX_OTP_ATTEMPTS = 5

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

# Only log sensitive tokens (OTP, registration tokens) when DEBUG mode is enabled
DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

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
    new_user.verification_token = f"{uuid.uuid4()}-{int(time.time())}"

    # Check if user already exists to avoid duplicate insert errors
    try:
        lookup_url = f"{DB_OPS_URL.rstrip('/')}/db/user-by-email?email={urllib.parse.quote(new_user.email)}"
        req_lookup = urllib.request.Request(lookup_url, method="GET")
        with urllib.request.urlopen(req_lookup, timeout=3) as resp_lookup:
            if resp_lookup.status == 200:
                # User already exists
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")
    except HTTPException:
        # Re-raise HTTPException (e.g., 409 Conflict) so it doesn't get caught by generic Exception handler
        raise
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

@app.post("/send-otp")
async def send_otp(request: OTPRequest) -> OTPResponse:
    """
    Generate and send OTP to user's email.
    Used for both admin registration and voter login verification.
    """
    email = request.email
    user_type = request.user_type
    
    # Validate user_type
    if user_type not in ["voter", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_type must be 'voter' or 'admin'"
        )
    
    # Rate limiting: max 3 OTP requests per email per hour
    try:
        rate_limit_url = f"{DB_OPS_URL.rstrip('/')}/redis/check-otp-rate-limit"
        rate_payload = {
            "email": email,
            "user_type": user_type,
            "max_requests": 3,
            "window_seconds": 3600  # 1 hour
        }
        req_data = json.dumps(rate_payload).encode("utf-8")
        req = urllib.request.Request(
            rate_limit_url,
            data=req_data,
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            pass  # If we get here, rate limit check passed
    except urllib.error.HTTPError as e:
        if getattr(e, 'code', None) == 429:
            # Rate limit exceeded
            try:
                error_body = e.read().decode()
                error_data = json.loads(error_body)
                detail = error_data.get("detail", "Too many OTP requests. Please try again later.")
            except Exception:
                detail = "Too many OTP requests. Please try again later."
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail
            )
        # For other errors, log and continue (fail open)
        logger.warning("Rate limit check failed with code %s, allowing request", getattr(e, 'code', None))
    except Exception as e:
        # If rate limiting service unavailable, allow the request (fail open)
        logger.warning("Rate limit check failed: %s, allowing request", e)
    
    # For voters, check if user exists and is verified
    # For admins, this is part of registration flow
    if user_type == "voter":
        try:
            lookup_url = f"{DB_OPS_URL.rstrip('/')}/db/user-by-email?email={urllib.parse.quote(email)}"
            req_lookup = urllib.request.Request(lookup_url, method="GET")
            with urllib.request.urlopen(req_lookup, timeout=3) as resp_lookup:
                if resp_lookup.status == 200:
                    body = resp_lookup.read().decode("utf-8")
                    user_data = json.loads(body)
                    # Check if user is already verified for login
                    if not user_data.get("is_verified"):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Please verify your email first before requesting login OTP"
                        )
        except urllib.error.HTTPError as e:
            if getattr(e, 'code', None) == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User lookup service unavailable"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to lookup user: %s", e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )
    
    # Generate 6-digit OTP
    otp = ''.join(random.choices(string.digits, k=6))
    
    # Store OTP in Redis via db_ops_service
    try:
        store_url = f"{DB_OPS_URL.rstrip('/')}/redis/store-otp"
        req_payload = {
            "email": email,
            "otp": otp,
            "user_type": user_type,
            "expiry_seconds": OTP_EXPIRY_SECONDS
        }
        req_data = json.dumps(req_payload).encode("utf-8")
        req = urllib.request.Request(
            store_url,
            data=req_data,
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                logger.warning("Failed to store OTP in Redis")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="OTP service unavailable"
                )
    except urllib.error.HTTPError as e:
        logger.warning("Redis store OTP HTTPError %s", getattr(e, 'code', None))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OTP service unavailable"
        )
    except Exception as e:
        logger.exception("Failed to store OTP: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OTP service unavailable"
        )
    
    # Send OTP via email
    try:
        await send_otp_email(email, otp, user_type)
    except Exception as e:
        logger.warning("Failed to send OTP email for %s: %s", email, e)
        # Don't fail the request if email fails, OTP is still stored
    
    logger.info("OTP sent to %s (type=%s)", email, user_type)
    return OTPResponse(
        message="OTP sent to your email",
        email=email,
        expires_in_seconds=OTP_EXPIRY_SECONDS
    )


@app.post("/verify-otp")
async def verify_otp(request: OTPVerificationRequest) -> dict:
    """
    Verify OTP submitted by user.
    Used for both admin registration completion and voter login MFA.
    """
    email = request.email
    otp = request.otp
    user_type = request.user_type
    
    if not otp or len(otp) != 6 or not otp.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP must be a 6-digit code"
        )
    
    # Verify OTP via db_ops_service (Redis check)
    try:
        verify_url = f"{DB_OPS_URL.rstrip('/')}/redis/verify-otp"
        req_payload = {
            "email": email,
            "otp": otp,
            "user_type": user_type
        }
        req_data = json.dumps(req_payload).encode("utf-8")
        req = urllib.request.Request(
            verify_url,
            data=req_data,
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                body = resp.read().decode() if resp else ""
                logger.warning("OTP verification failed: %s", body)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired OTP"
                )
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            
    except urllib.error.HTTPError as e:
        body = None
        try:
            body = e.read().decode()
            error_data = json.loads(body)
            detail = error_data.get("detail", "Invalid or expired OTP")
        except Exception:
            detail = "Invalid or expired OTP"
        
        logger.warning("OTP verify HTTPError %s: %s", getattr(e, 'code', None), body)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to verify OTP: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OTP verification service unavailable"
        )
    
    logger.info("OTP verified successfully for %s (type=%s)", email, user_type)
    
    # For voter login, generate JWT token
    if user_type == "voter":
        try:
            # Get user data
            lookup_url = f"{DB_OPS_URL.rstrip('/')}/db/user-by-email?email={urllib.parse.quote(email)}"
            req_lookup = urllib.request.Request(lookup_url, method="GET")
            with urllib.request.urlopen(req_lookup, timeout=5) as resp_lookup:
                body = resp_lookup.read().decode("utf-8")
                user_data = json.loads(body)
                
            user_id = user_data.get("user_id")
            access_token = generate_tokens(user_id=user_id, email=email)
            
            return {
                "message": "OTP verified successfully",
                "verified": True,
                "access_token": access_token,
                "token_type": "bearer"
            }
        except Exception as e:
            logger.exception("Failed to generate token after OTP verify: %s", e)
            return {
                "message": "OTP verified successfully",
                "verified": True
            }
    
    # For admin registration, just confirm verification
    return {
        "message": "OTP verified successfully",
        "verified": True
    }


async def send_otp_email(email: str, otp: str, user_type: str):
    """
    Send OTP via email using SMTP.
    This replaces your existing send_otp_email function.
    """
    if user_type == "admin":
        subject = "Your Admin Registration OTP - E-Vote"
        body_text = f"""
Hello,

Your E-Vote Admin Registration OTP Code is: {otp}

This code will expire in 10 minutes.

If you did not request this code, please ignore this email.

Best regards,
E-Vote Team
"""
        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #4CAF50;">Admin Registration Verification</h2>
    <p>Your OTP code is:</p>
    <div style="background-color: #f0f0f0; padding: 20px; text-align: center; border-radius: 5px;">
        <h1 style="color: #4CAF50; font-size: 36px; letter-spacing: 8px; margin: 0;">{otp}</h1>
    </div>
    <p style="margin-top: 20px;">This code will expire in <strong>10 minutes</strong>.</p>
    <p style="color: #666;">If you did not request this code, please ignore this email.</p>
</body>
</html>
"""
    else:  # voter
        subject = "Your Login OTP - E-Vote"
        body_text = f"""
Hello,

Your E-Vote Login OTP Code is: {otp}

This code will expire in 10 minutes.

If you did not request this code, please secure your account immediately.

Best regards,
E-Vote Team
"""
        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #2196F3;">Login Verification</h2>
    <p>Your OTP code is:</p>
    <div style="background-color: #f0f0f0; padding: 20px; text-align: center; border-radius: 5px;">
        <h1 style="color: #2196F3; font-size: 36px; letter-spacing: 8px; margin: 0;">{otp}</h1>
    </div>
    <p style="margin-top: 20px;">This code will expire in <strong>10 minutes</strong>.</p>
    <p style="color: #ff5722;"><strong>Security Alert:</strong> If you did not request this code, please secure your account immediately.</p>
</body>
</html>
"""
    
    # Get SMTP configuration
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587)) if os.getenv("SMTP_PORT") else None
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    email_from = os.getenv("EMAIL_FROM", "uvote.verify@gmail.com")
    
    # Check if SMTP is configured
    if not smtp_host or not smtp_port:
        logger.warning("SMTP not configured - OTP will only be logged in debug mode")
        if DEBUG_MODE:
            logger.info("[DEV MODE] OTP for %s (%s): %s", email, user_type, otp)
        return
    
    try:
        # Send email using SMTP in a separate thread to avoid blocking
        await asyncio.to_thread(
            _smtp_send_otp,
            smtp_host, smtp_port, smtp_user, smtp_pass,
            email_from, email, subject, body_text, body_html
        )
        logger.info("✅ OTP email sent successfully via SMTP to %s", email)
    except Exception as e:
        logger.error("❌ SMTP send failed: %s", e)
        if DEBUG_MODE:
            logger.info("[FALLBACK] OTP for %s (%s): %s", email, user_type, otp)
        raise  # Re-raise so caller knows email failed

def _smtp_send_otp(smtp_host, smtp_port, smtp_user, smtp_pass, email_from, to_email, subject, body_text, body_html):
    """
    Send OTP email via Gmail SMTP using STARTTLS on port 587.
    """
    msg = MIMEMultipart('alternative')
    msg["From"] = email_from
    msg["To"] = to_email
    msg["Subject"] = subject

    # Attach plain text and HTML
    msg.attach(MIMEText(body_text, 'plain'))
    msg.attach(MIMEText(body_html, 'html'))

    try:
        # Connect to Gmail SMTP on port 587
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()           # Identify ourselves to SMTP server
            server.starttls()       # Upgrade connection to TLS
            server.ehlo()           # Re-identify after STARTTLS
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info("✅ Email sent successfully to %s via %s:%s", to_email, smtp_host, smtp_port)
    except Exception as e:
        logger.error("❌ Failed to send OTP email: %s", e)
        raise
    
@app.post("/admin/verify-and-activate")
async def verify_admin_otp(request: VerifyAdminOTPRequest):
    """
    Verify admin OTP and mark their account as verified in the database.
    This completes admin registration.
    """
    email = request.email
    otp = request.otp
    
    if not otp or len(otp) != 6 or not otp.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP must be a 6-digit code"
        )
    
    # Verify OTP via Redis
    try:
        verify_url = f"{DB_OPS_URL.rstrip('/')}/redis/verify-otp"
        req_payload = {
            "email": email,
            "otp": otp,
            "user_type": "admin"
        }
        req_data = json.dumps(req_payload).encode("utf-8")
        req = urllib.request.Request(
            verify_url,
            data=req_data,
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired OTP"
                )
    except urllib.error.HTTPError as e:
        body = None
        try:
            body = e.read().decode()
            error_data = json.loads(body)
            detail = error_data.get("detail", "Invalid or expired OTP")
        except Exception:
            detail = "Invalid or expired OTP"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to verify OTP: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OTP verification service unavailable"
        )
    
    # Mark user as verified in database
    try:
        mark_verified_url = f"{DB_OPS_URL.rstrip('/')}/db/mark-verified"
        req_payload = {"email": email}
        req_data = json.dumps(req_payload).encode("utf-8")
        req = urllib.request.Request(
            mark_verified_url,
            data=req_data,
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Failed to mark account as verified"
                )
    except Exception as e:
        logger.exception("Failed to mark user as verified: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Account verification failed"
        )
    
    logger.info("Admin account verified and activated: %s", email)
    return {
        "message": "Account verified successfully. You can now login.",
        "email": email,
        "verified": True
    }


@app.post("/admin/upload-candidates")
async def upload_candidates(payload: dict):
    """
    Admin uploads list of candidates for the election.
    Stores candidates in database.
    """
    candidates = payload.get("candidates", [])
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No candidates provided"
        )
    
    results = {
        "uploaded": 0,
        "failed": []
    }
    
    for candidate in candidates:
        try:
            store_url = f"{DB_OPS_URL.rstrip('/')}/db/store-candidate"
            req_data = json.dumps(candidate).encode("utf-8")
            req = urllib.request.Request(
                store_url,
                data=req_data,
                method="POST",
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    results["uploaded"] += 1
                else:
                    results["failed"].append({
                        "name": candidate.get("name"),
                        "reason": "Database storage failed"
                    })
        except Exception as e:
            logger.exception("Failed to store candidate %s: %s", candidate.get("name"), e)
            results["failed"].append({
                "name": candidate.get("name", "unknown"),
                "reason": str(e)
            })
    
    logger.info("Candidate upload complete: %d uploaded, %d failed", 
                results["uploaded"], len(results["failed"]))
    return results


@app.post("/admin/upload-voters")
async def upload_voters(payload: dict):
    """
    Admin uploads list of eligible voters.
    Generates registration tokens and sends invitation emails.
    """
    voters = payload.get("voters", [])
    if not voters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No voters provided"
        )
    
    results = {
        "uploaded": 0,
        "failed": [],
        "tokens": {}  # For development - you can check tokens here
    }
    
    for voter in voters:
        try:
            # Generate one-time registration token
            token = f"{uuid.uuid4()}-voter-{int(time.time())}"
            
            # Store voter record in database
            store_url = f"{DB_OPS_URL.rstrip('/')}/db/store-voter-record"
            req_payload = {
                "email": voter["email"],
                "full_name": voter["full_name"],
                "phone_number": voter["phone_number"],
                "voter_id": voter["voter_id"],
                "registration_token": token
            }
            req_data = json.dumps(req_payload).encode("utf-8")
            req = urllib.request.Request(
                store_url,
                data=req_data,
                method="POST",
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    # Send registration email
                    try:
                        await send_voter_registration_email(
                            voter["email"],
                            voter["full_name"],
                            token
                        )
                        logger.info("Registration email sent to %s", voter["email"])
                    except Exception as e:
                        logger.warning("Failed to send email to %s: %s", voter["email"], e)
                        # Continue anyway - voter can still register with token
                    
                    results["uploaded"] += 1
                    results["tokens"][voter["email"]] = token  # For dev/testing
                else:
                    results["failed"].append({
                        "email": voter["email"],
                        "reason": "Database storage failed"
                    })
        except Exception as e:
            logger.exception("Failed to process voter %s: %s", voter.get("email"), e)
            results["failed"].append({
                "email": voter.get("email", "unknown"),
                "reason": str(e)
            })
    
    logger.info("Voter upload complete: %d uploaded, %d failed", 
                results["uploaded"], len(results["failed"]))
    return results


@app.post("/voter/register")
async def register_voter(request: VoterRegistrationRequest):
    """
    Voter registration using one-time token from email.
    Validates token and voter data before creating account.
    """
    # Validate password
    password_strength = validate_password_strength(request.password)
    if not password_strength.get("valid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_strength.get("message")
        )
    
    # Verify token and get stored voter record
    try:
        verify_url = f"{DB_OPS_URL.rstrip('/')}/db/verify-voter-token"
        req_payload = {
            "token": request.token,
            "email": request.email
        }
        req_data = json.dumps(req_payload).encode("utf-8")
        req = urllib.request.Request(
            verify_url,
            data=req_data,
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired registration token"
                )
            body = resp.read().decode("utf-8")
            stored_voter = json.loads(body)
    except urllib.error.HTTPError as e:
        error_code = getattr(e, 'code', None)
        # Try to get the detail message from db_ops response
        try:
            error_body = e.read().decode()
            error_data = json.loads(error_body)
            error_detail = error_data.get("detail", "")
        except Exception:
            error_detail = ""
        
        if error_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registration token not found"
            )
        elif error_code == 400:
            # Token already used or other validation error from db_ops
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail or "Registration token has already been used"
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification service unavailable"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to verify voter token: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable"
        )
    
    # Validate voter data matches stored record
    if (
        stored_voter["voter_id"] != request.voter_id or
        stored_voter["phone_number"] != request.phone_number or
        stored_voter["full_name"].lower() != request.full_name.lower()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voter information does not match our records"
        )
    
    # Create voter account
    password_hash = hash_password(request.password)
    
    try:
        create_url = f"{DB_OPS_URL.rstrip('/')}/db/create-voter"
        req_payload = {
            "email": request.email,
            "password_hash": password_hash,
            "voter_id": request.voter_id,
            "phone_number": request.phone_number,
            "full_name": request.full_name,
            "registration_token": request.token
        }
        req_data = json.dumps(req_payload).encode("utf-8")
        req = urllib.request.Request(
            create_url,
            data=req_data,
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Failed to create voter account"
                )
            body = resp.read().decode("utf-8")
            created_user = json.loads(body)
    except urllib.error.HTTPError as e:
        if getattr(e, 'code', None) == 409:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already registered"
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Account creation failed"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create voter account: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable"
        )
    
    logger.info("Voter registered successfully: %s", request.email)
    return {
        "message": "Registration successful. Your account is now active and you can vote.",
        "email": request.email,
        "user_id": created_user.get("user_id")
    }


async def send_voter_registration_email(email: str, full_name: str, token: str):
    """
    Send registration invitation email to eligible voter.
    """
    base_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    register_url = f"{base_url}/voter-register?token={token}"
    
    subject = "Voter Registration Invitation - E-Vote"
    body_text = f"""
Hello {full_name},

You have been registered as an eligible voter in the upcoming election.

Please complete your registration by visiting:
{register_url}

Your one-time registration token: {token}

This link will expire after one use.

If you did not expect this email, please contact the election administrator.

Best regards,
E-Vote Election Commission
"""
    
    body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #2196F3;">Voter Registration Invitation</h2>
    <p>Hello <strong>{full_name}</strong>,</p>
    <p>You have been registered as an eligible voter in the upcoming election.</p>
    <p>Please complete your registration by clicking below:</p>
    <div style="text-align: center; margin: 30px 0;">
        <a href="{register_url}" 
           style="background-color: #4CAF50; color: white; padding: 15px 30px; 
                  text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
            Complete Registration
        </a>
    </div>
    <p>Or copy this link: <br><code style="background: #f0f0f0; padding: 5px;">{register_url}</code></p>
    <p style="font-size: 12px; color: #666;">Registration token: <code>{token}</code></p>
    <p style="color: #ff5722; font-size: 14px;">⚠️ This link expires after one use.</p>
    <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
    <p style="font-size: 12px; color: #999;">
        If you did not expect this email, please contact the election administrator.<br>
        E-Vote Election Commission
    </p>
</body>
</html>
"""
    
    # Get SMTP config
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587)) if os.getenv("SMTP_PORT") else None
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    email_from = os.getenv("EMAIL_FROM", "noreply@evote.example.com")
    
    if not smtp_host or not smtp_port:
        logger.warning("SMTP not configured - registration link logged only in debug mode")
        if DEBUG_MODE:
            logger.info("[DEV MODE] Registration link for %s: %s", email, register_url)
            logger.info("[DEV MODE] Token: %s", token)
        return
    
    try:
        await asyncio.to_thread(
            _smtp_send_otp,
            smtp_host, smtp_port, smtp_user, smtp_pass,
            email_from, email, subject, body_text, body_html
        )
        logger.info("✅ Registration email sent to %s", email)
    except Exception as e:
        logger.error("❌ Failed to send registration email: %s", e)
        if DEBUG_MODE:
            logger.info("[FALLBACK] Registration link for %s: %s", email, register_url)
            logger.info("[FALLBACK] Token: %s", token)
        raise