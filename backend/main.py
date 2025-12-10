import os
import json
import logging
import urllib.request
import urllib.error
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from backend.middleware import require_auth
from backend.routes import poll_router
from backend.routes.vote_routes import router as vote_router
from backend.db_ops_service.database.connection import DatabaseManager

logger = logging.getLogger(__name__)
logging.basicConfig(filename='myapp.log', level=logging.INFO)

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on application startup"""
    try:
        db = DatabaseManager()
        db.connect()
        db.initialize_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

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

# Include routers
app.include_router(poll_router)
app.include_router(vote_router)

SERVICE_ROLE = "backend"
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")

@app.get("/health")
async def health():
    return {"status": "ok", "role": SERVICE_ROLE}

def proxy_post(path: str, body: dict, timeout: int = 5):
    url = f"{AUTH_SERVICE_URL.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            if resp.status >= 400:
                raise HTTPException(status_code=resp.status, detail=resp_body)
            return json.loads(resp_body)
    except urllib.error.HTTPError as e:
        body_text = None
        try:
            body_text = e.read().decode()
        except Exception:
            pass
        logger.warning("Auth service HTTPError %s: %s", getattr(e, "code", None), body_text)
        raise HTTPException(status_code=getattr(e, "code", 502), detail=body_text or "Auth service error")
    except Exception as e:
        logger.exception("Failed to call auth service: %s", e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth service unavailable")

@app.post("/register")
async def register_user(payload: dict):
    """
    Proxy registration requests to auth service which now owns all authentication logic.
    """
    result = proxy_post("/register", payload)
    return result

@app.post("/login")
async def login_user(payload: dict):
    """
    Proxy login requests to auth service which now handles lookup, verification and token issuance.
    """
    result = proxy_post("/login", payload)
    return result

@app.post("/send-otp")
async def send_otp(payload: dict):
    """Proxy OTP send requests to auth service."""
    result = proxy_post("/send-otp", payload)
    return result

@app.post("/verify-otp")
async def verify_otp(payload: dict):
    """Proxy OTP verification requests to auth service."""
    result = proxy_post("/verify-otp", payload)
    return result

@app.post("/admin/verify-and-activate")
async def admin_verify_otp(payload: dict):
    """Proxy admin OTP verification and activation"""
    result = proxy_post("/admin/verify-and-activate", payload)
    return result

@app.post("/admin/upload-candidates")
async def admin_upload_candidates(payload: dict):
    """Proxy candidate upload"""
    result = proxy_post("/admin/upload-candidates", payload)
    return result

@app.post("/admin/upload-voters")
async def admin_upload_voters(payload: dict):
    """Proxy voter upload"""
    result = proxy_post("/admin/upload-voters", payload)
    return result

@app.post("/voter/register")
async def voter_register(payload: dict):
    """Proxy voter registration"""
    result = proxy_post("/voter/register", payload)
    return result