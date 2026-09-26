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
    provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured per-output provenance and traceability records"
    )


class RefineRequest(BaseModel):
    """
    Request schema for the /refine endpoint.
    Allows interactive single-output refinement with a dedicated user instruction.
    """
    source_content: str = Field(
        ...,
        description="Original source text content"
    )
    output_type: str = Field(
        ...,
        description="Specific output format to refine (e.g. 'Executive Summary', 'LinkedIn Post')"
    )
    current_output: str = Field(
        ...,
        description="Current text of the output artefact to be refined"
    )
    refinement_instruction: str = Field(
        ...,
        description="User instruction directing how the output should be refined"
    )
    target_audience: Optional[str] = Field(
        default=None,
        description="Target audience (e.g. 'C-suite Executives', 'Engineers')"
    )
    tone: Optional[str] = Field(
        default=None,
        description="Tone of voice (e.g. 'Professional', 'Urgent', 'Inspiring')"
    )
    language: Optional[str] = Field(
        default="English",
        description="Language for the refined output (defaults to English)"
    )
    detail_level: Optional[str] = Field(
        default=None,
        description="Detail level ('Brief', 'Moderate', 'Detailed')"
    )
    communication_objective: Optional[str] = Field(
        default=None,
        description="Communication objective (e.g. 'Inform', 'Persuade', 'Call to Action')"
    )
    content_style: Optional[str] = Field(
        default=None,
        description="Content style (e.g. 'Direct & Concise', 'Analytical & Data-Driven')"
    )
    document_name: Optional[str] = Field(
        default=None,
        description="Optional original document name if content was uploaded as a file"
    )
    image_data: Optional[str] = Field(
        default=None,
        description="Optional base64-encoded image data or data URI"
    )
    image_name: Optional[str] = Field(
        default=None,
        description="Optional original filename of attached image"
    )
    video_data: Optional[str] = Field(
        default=None,
        description="Optional base64-encoded video data or data URI"
    )
    video_name: Optional[str] = Field(
        default=None,
        description="Optional original filename of attached video"
    )


class RefineResponse(BaseModel):
    """
    Response schema for the /refine endpoint.
    Returns the refined output along with validation, recovery, and provenance metadata.
    """
    status: str = Field(
        ...,
        description="Status of refinement ('success' or 'error')"
    )
    output_type: str = Field(
        ...,
        description="The refined output format"
    )
    refined_output: str = Field(
        ...,
        description="The refined content text"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Refinement metadata: model, is_mock, output_type, refinement_applied, validation, recovery_attempted"
    )
    provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured provenance and traceability record for the refined output"
    )
