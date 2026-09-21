from typing import Optional, Dict, Any
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
    output_type: str = Field(
        ...,
        description="Type of communication artefact (e.g., 'Executive Summary', 'Advisory', 'LinkedIn Post')"
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


class TransformResponse(BaseModel):
    """
    Response schema for the /transform endpoint.
    Returns the transformed text and relevant processing metadata.
    """
    status: str = Field(
        ...,
        description="Status of transformation ('success' or 'error')"
    )
    output_type: str = Field(
        ...,
        description="The output type that was generated"
    )
    transformed_content: str = Field(
        ...,
        description="The generated output text (currently placeholder mock output)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration parameters and processing metadata"
    )
