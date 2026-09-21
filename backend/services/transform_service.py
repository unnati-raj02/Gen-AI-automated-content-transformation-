from schemas.transform_schema import TransformRequest, TransformResponse


def transform_content(request: TransformRequest) -> TransformResponse:
    """
    Mock transformation service.
    
    Generates a clearly labelled placeholder response based on the requested
    output_type and input configuration parameters.
    No external AI API is called at this stage.
    """
    # Extract request values with sensible fallbacks for display
    source = request.source_content.strip()
    output_type = request.output_type.strip()
    audience = request.target_audience or "General Audience"
    tone = request.tone or "Professional"
    language = request.language or "English"
    detail = request.detail_level or "Standard"

    # Create a short snippet from the source for previewing
    snippet = source[:120] + "..." if len(source) > 120 else source
    output_type_lower = output_type.lower()

    # Generate tailored placeholder output based on output_type
    if "executive summary" in output_type_lower:
        transformed_text = (
            f"[MOCK GENERATION - EXECUTIVE SUMMARY]\n"
            f"Audience: {audience} | Tone: {tone} | Language: {language} | Detail Level: {detail}\n\n"
            f"1. Executive Overview:\n"
            f"   This summary synthesizes the primary findings from the source information: \"{snippet}\"\n\n"
            f"2. Strategic Impact:\n"
            f"   The referenced initiative is expected to streamline communication across designated stakeholder groups.\n\n"
            f"3. Action Items:\n"
            f"   - Align operational milestones with the target delivery schedule.\n"
            f"   - Review key performance indicators periodically.\n\n"
            f"---\n"
            f"(Note: Placeholder mock output. Real LLM transformation will be integrated in subsequent steps.)"
        )
    elif "advisory" in output_type_lower:
        transformed_text = (
            f"[MOCK GENERATION - ADVISORY NOTICE]\n"
            f"Audience: {audience} | Tone: {tone} | Language: {language} | Detail Level: {detail}\n\n"
            f"ADVISORY BULLETIN:\n"
            f"Purpose: Guidance derived from provided source material.\n"
            f"Context: \"{snippet}\"\n\n"
            f"RECOMMENDED DIRECTIVES:\n"
            f"1. Acknowledge and distribute this advisory to all relevant team members.\n"
            f"2. Adopt recommended safety and compliance measures immediately.\n\n"
            f"---\n"
            f"(Note: Placeholder mock output. Real LLM transformation will be integrated in subsequent steps.)"
        )
    elif "linkedin" in output_type_lower or "post" in output_type_lower:
        transformed_text = (
            f"[MOCK GENERATION - LINKEDIN POST]\n"
            f"Audience: {audience} | Tone: {tone} | Language: {language} | Detail Level: {detail}\n\n"
            f"🚀 Key insights from our latest update!\n\n"
            f"Here is what you need to know:\n"
            f"\"{snippet}\"\n\n"
            f"💡 Key Takeaway: Effective transformation of ideas into impactful communication builds stronger teams and better outcomes.\n\n"
            f"What are your perspectives on this? Share your thoughts below! 👇\n\n"
            f"#Innovation #Leadership #ContentTransformation #FutureOfWork\n"
            f"---\n"
            f"(Note: Placeholder mock output. Real LLM transformation will be integrated in subsequent steps.)"
        )
    else:
        # Fallback for any other custom output type
        transformed_text = (
            f"[MOCK GENERATION - {output_type.upper()}]\n"
            f"Audience: {audience} | Tone: {tone} | Language: {language} | Detail Level: {detail}\n\n"
            f"Transformed Content Preview:\n"
            f"\"{snippet}\"\n\n"
            f"The content above has been structured into {output_type} format tailored for {audience}.\n\n"
            f"---\n"
            f"(Note: Placeholder mock output. Real LLM transformation will be integrated in subsequent steps.)"
        )

    return TransformResponse(
        status="success",
        output_type=output_type,
        transformed_content=transformed_text,
        metadata={
            "target_audience": audience,
            "tone": tone,
            "language": language,
            "detail_level": detail,
            "source_character_count": len(source),
            "is_mock": True
        }
    )
