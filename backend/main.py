import os
import time
from collections import defaultdict
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from routers.transform import router as transform_router
from dotenv import load_dotenv

load_dotenv()

# Initialize the FastAPI application
app = FastAPI(
    title="AI Content Transformer API",
    description="Backend API for AI Content Transformer (SIH Project)",
    version="0.1.0"
)

# 1. Configurable CORS: Restrictable for production via ALLOWED_ORIGINS
raw_origins = os.getenv("ALLOWED_ORIGINS", "*").strip()
if raw_origins == "*" or not raw_origins:
    allowed_origins = ["*"]
else:
    allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Request body / file size protection middleware (35MB default)
MAX_BODY_SIZE_BYTES = int(os.getenv("MAX_REQUEST_BODY_SIZE_BYTES", str(35 * 1024 * 1024)))


@app.middleware("http")
async def limit_body_size_middleware(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_SIZE_BYTES:
                limit_mb = MAX_BODY_SIZE_BYTES // (1024 * 1024)
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request payload too large. Maximum allowed size is {limit_mb}MB."}
                )
        except ValueError:
            pass
    return await call_next(request)


# 3. Basic in-memory rate limiting to protect Gemini quota and prevent abuse
rate_limit_records = defaultdict(list)


@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    # Exclude system endpoints from rate limiting
    path = request.url.path
    if path in ["/", "/health", "/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)

    rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    if rate_limit <= 0:
        return await call_next(request)

    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    one_minute_ago = now - 60.0

    # Prune timestamps older than 60s
    timestamps = [t for t in rate_limit_records[client_ip] if t > one_minute_ago]
    rate_limit_records[client_ip] = timestamps

    if len(timestamps) >= rate_limit:
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"Rate limit exceeded ({rate_limit} requests/minute). Please wait before retrying."
            },
            headers={"Retry-After": "60"}
        )

    rate_limit_records[client_ip].append(now)
    return await call_next(request)


# Register transformation routes
app.include_router(transform_router)


@app.get("/")
def read_root():
    """Basic root route to check if the server is up."""
    return {"message": "AI Content Transformer API is running"}


@app.get("/health")
def health_check():
    """Health check route."""
    return {"status": "ok"}
