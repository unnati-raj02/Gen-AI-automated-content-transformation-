from fastapi import APIRouter
from schemas.transform_schema import TransformRequest, TransformResponse
from services.transform_service import transform_content

# Initialize APIRouter for transformation endpoints
router = APIRouter(tags=["Transformation"])


@router.post("/transform", response_model=TransformResponse, summary="Transform source content")
def transform(request: TransformRequest):
    """
    Accepts source content along with target configurations (audience, tone, language, detail level)
    and transforms it into the requested communication artefact.
    Currently delegates to the mock transformation service.
    """
    return transform_content(request)
