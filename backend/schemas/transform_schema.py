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


class CanonicalContentModel(BaseModel):
    """
    Canonical Content Model (Intermediate Representation) representing structured source information
    prior to format-specific generation.
    Captures verifiable entities, factual claims, metrics, dates, events, key messages,
    risks/impacts, certifications/standards, and terminology while preserving source traceability.
    """
    source_reference: Optional[str] = Field(
        default=None,
        description="Source identifier or reference (e.g. document name, file reference, direct input)"
    )
    source_text: str = Field(
        default="",
        description="Original source text content preserved for full provenance and traceability"
    )
    entities: List[str] = Field(
        default_factory=list,
        description="Extracted named entities, organizations, or platform components"
    )
    claims: List[str] = Field(
        default_factory=list,
        description="Key factual propositions and substantive assertions extracted from source"
    )
    metrics: List[str] = Field(
        default_factory=list,
        description="Quantitative numbers, percentages, multipliers, and monetary values"
    )
    dates: List[str] = Field(
        default_factory=list,
        description="Temporal anchors, quarters, years, or calendar milestones"
    )
    events: List[str] = Field(
        default_factory=list,
        description="Verifiable event occurrences (e.g. launch, acquisition, certification, deployment)"
    )
    key_messages: List[str] = Field(
        default_factory=list,
        description="Core high-level takeaways or summary themes distilled from source"
    )
    risks_and_impacts: List[str] = Field(
        default_factory=list,
        description="Identified risks, threats, vulnerabilities, or operational impacts"
    )
    standards_and_certifications: List[str] = Field(
        default_factory=list,
        description="Industry standards, compliance benchmarks, and certifications (e.g. SOC2, ISO/IEC 27001)"
    )
    terminology: List[str] = Field(
        default_factory=list,
        description="Domain-specific technical terms, acronyms, and specialized nomenclature"
    )

    def to_canonical_context(self) -> str:
        """
        Returns a concise, structured textual representation of canonical source facts
        usable across format-specific generation, prompt context, and validation.
        """
        lines = []
        if self.source_reference:
            lines.append(f"- Source Reference: {self.source_reference}")
        if self.key_messages:
            lines.append(f"- Key Messages: {'; '.join(self.key_messages)}")
        if self.entities:
            lines.append(f"- Entities: {', '.join(self.entities)}")
        if self.metrics:
            lines.append(f"- Metrics: {', '.join(self.metrics)}")
        if self.dates:
            lines.append(f"- Dates/Timeline: {', '.join(self.dates)}")
        if self.events:
            lines.append(f"- Events: {', '.join(self.events)}")
        if self.standards_and_certifications:
            lines.append(f"- Standards & Certifications: {', '.join(self.standards_and_certifications)}")
        if self.risks_and_impacts:
            lines.append(f"- Risks & Impacts: {'; '.join(self.risks_and_impacts)}")
        if self.terminology:
            lines.append(f"- Terminology: {', '.join(self.terminology)}")
        return "\n".join(lines)


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
    canonical_content: Optional[CanonicalContentModel] = Field(
        default=None,
        description="Canonical Content Model (Intermediate Representation) representing extracted source information"
    )
    cross_format_consistency: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Cross-format consistency validation report comparing facts across all generated formats"
    )
    quality_score: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Deterministic explainable quality and confidence score breakdown"
    )
    quality_gate: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Final quality gate evaluation status and threshold report"
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
    canonical_content: Optional[CanonicalContentModel] = Field(
        default=None,
        description="Canonical Content Model (Intermediate Representation) of the source content"
    )
    cross_format_consistency: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Consistency validation report for the refined output"
    )
    quality_score: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Deterministic explainable quality and confidence score breakdown"
    )
    quality_gate: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Final quality gate evaluation status"
    )
