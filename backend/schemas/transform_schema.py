from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class TransformRequest(BaseModel):
    """
    Request schema for the /transform endpoint.
    Defines the source content and optional configuration parameters.
    """
    source_content: str = Field(
        ...,
        description="Source text content to be transformed"
    )
    output_types: List[str] = Field(
        ...,
        description="Types of communication artefacts (e.g., ['Executive Summary', 'Advisory', 'LinkedIn Post', 'Twitter/X Post', 'Infographic', 'Presentation', 'Video Package'])"
    )
    target_audience: Optional[str] = Field(
        default=None,
        description="Intended audience (e.g., 'C-suite Executives', 'Students', 'General Public')"
    )
    tone: Optional[str] = Field(
        default=None,
        description="Tone of voice (e.g., 'Professional', 'Casual', 'Urgent', 'Informative')"
    )
    language: Optional[str] = Field(
        default="English",
        description="Language for the transformed content (defaults to English)"
    )
    detail_level: Optional[str] = Field(
        default=None,
        description="Detail level (e.g., 'Brief', 'Moderate', 'Detailed')"
    )
    communication_objective: Optional[str] = Field(
        default=None,
        description="Core communication goal (e.g., 'Inform', 'Persuade', 'Educate', 'Call to Action', 'Inspire')"
    )
    content_style: Optional[str] = Field(
        default=None,
        description="Content presentation style (e.g., 'Direct & Concise', 'Analytical & Data-Driven', 'Storytelling', 'Technical')"
    )
    document_name: Optional[str] = Field(
        default=None,
        description="Optional original document name if content was uploaded as a file"
    )
    image_data: Optional[str] = Field(
        default=None,
        description="Optional base64-encoded image data or data URI for multimodal processing"
    )
    image_name: Optional[str] = Field(
        default=None,
        description="Optional original filename of the uploaded image"
    )
    video_data: Optional[str] = Field(
        default=None,
        description="Optional base64-encoded video data or data URI for multimodal processing (.mp4, .webm, .mov)"
    )
    video_name: Optional[str] = Field(
        default=None,
        description="Optional original filename of the uploaded video"
    )


class TransformResponse(BaseModel):
    """
    Response schema for the /transform endpoint.
    Returns the transformed text and relevant processing metadata.
    """
    status: str = Field(
        ...,
        description="Status of transformation ('success' or 'error')"
    )
    outputs: Dict[str, str] = Field(
        default_factory=dict,
        description="Dictionary mapping output types to transformed content"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration parameters and processing metadata"
    )

