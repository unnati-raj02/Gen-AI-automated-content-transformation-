from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.transform import router as transform_router

# Initialize the FastAPI application
app = FastAPI(
    title="AI Content Transformer API",
    description="Backend API for AI Content Transformer (SIH Project)",
    version="0.1.0"
)

# Enable CORS (Cross-Origin Resource Sharing) so React frontend can talk to FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
