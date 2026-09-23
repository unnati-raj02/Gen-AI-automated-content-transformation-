from fastapi import APIRouter, UploadFile, File
from schemas.transform_schema import TransformRequest, TransformResponse
from services.transform_service import transform_content
from services.document_service import extract_text_from_document

# Initialize APIRouter for transformation endpoints
router = APIRouter(tags=["Transformation"])


@router.post("/transform", response_model=TransformResponse, summary="Transform source content")
def transform(request: TransformRequest):
    """
    Accepts source content along with target configurations (audience, tone, language, detail level, output types)
    and transforms it into the requested communication artefacts.
    Delegates to the transformation service and returns multiple generated outputs.
    """
    return transform_content(request)


@router.post("/extract-text", summary="Extract readable text from uploaded document (.txt, .pdf, .docx)")
async def extract_text(file: UploadFile = File(...)):
    """
    Accepts an uploaded document file (.txt, .md, .pdf, .docx),
    extracts the readable text, and returns it for use as source content.
    """
    file_bytes = await file.read()
    extracted_text = extract_text_from_document(file.filename, file_bytes)
    return {
        "filename": file.filename,
        "extracted_text": extracted_text,
        "character_count": len(extracted_text)
    }

