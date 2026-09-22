import os
import warnings
# Suppress Google SDK deprecation notice in console output
warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import HTTPException

from schemas.transform_schema import TransformRequest, TransformResponse

# Load environment variables from .env file (if present)
load_dotenv()


def build_prompt(
    source_content: str,
    output_type: str,
    target_audience: str,
    tone: str,
    language: str,
    detail_level: str
) -> str:
    """
    Constructs a structured prompt for the LLM based on source content
    and transformation parameters.
    """
    return f"""You are an expert AI content transformer.
Transform the provided source content into the requested communication artefact.

TRANSFORMATION SPECIFICATIONS:
- Target Artefact (Output Type): {output_type}
- Target Audience: {target_audience}
- Tone: {tone}
- Language: {language}
- Detail Level: {detail_level}

SOURCE CONTENT:
\"\"\"
{source_content}
\"\"\"

INSTRUCTIONS:
1. Transform the source content strictly into the format of '{output_type}'.
2. Tailor vocabulary and complexity to the '{target_audience}' audience.
3. Maintain the requested '{tone}' tone throughout the output.
4. Output the result in the '{language}' language.
5. Provide content matching the '{detail_level}' level of detail:
   - If Executive Summary: Include overview, strategic impact, and key takeaways/action items.
   - If Advisory: Include context, risk/operational impact, and clear directives.
   - If LinkedIn Post: Include a strong hook, concise bullet points, a call-to-action, and relevant hashtags.
6. Do NOT include conversational filler, introductory remarks, or meta-commentary (e.g., do not say "Here is your summary"). Directly output the transformed artefact.
"""


def mock_transform_content(request: TransformRequest) -> TransformResponse:
    """
    Mock transformation fallback.
    Retained for testing without an API key or when offline.
    """
    source = request.source_content.strip()
    output_type = request.output_type.strip()
    audience = request.target_audience or "General Audience"
    tone = request.tone or "Professional"
    language = request.language or "English"
    detail = request.detail_level or "Standard"

    snippet = source[:120] + "..." if len(source) > 120 else source
    output_type_lower = output_type.lower()

    if "executive summary" in output_type_lower:
        transformed_text = (
            f"[MOCK GENERATION - EXECUTIVE SUMMARY]\n"
            f"Audience: {audience} | Tone: {tone} | Language: {language} | Detail Level: {detail}\n\n"
            f"1. Executive Overview:\n"
            f"   This summary synthesizes the primary findings: \"{snippet}\"\n\n"
            f"2. Strategic Impact:\n"
            f"   The referenced initiative is expected to streamline communication across designated stakeholder groups.\n\n"
            f"3. Action Items:\n"
            f"   - Align operational milestones with the target delivery schedule.\n"
            f"   - Review key performance indicators periodically.\n\n"
            f"---\n"
            f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
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
            f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
        )
    elif "linkedin" in output_type_lower or "post" in output_type_lower:
        transformed_text = (
            f"[MOCK GENERATION - LINKEDIN POST]\n"
            f"Audience: {audience} | Tone: {tone} | Language: {language} | Detail Level: {detail}\n\n"
            f"🚀 Key insights from our latest update!\n\n"
            f"Here is what you need to know:\n"
            f"\"{snippet}\"\n\n"
            f"💡 Key Takeaway: Effective transformation of ideas into impactful communication builds stronger teams.\n\n"
            f"What are your perspectives on this? Share your thoughts below! 👇\n\n"
            f"#Innovation #Leadership #ContentTransformation #FutureOfWork\n"
            f"---\n"
            f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
        )
    else:
        transformed_text = (
            f"[MOCK GENERATION - {output_type.upper()}]\n"
            f"Audience: {audience} | Tone: {tone} | Language: {language} | Detail Level: {detail}\n\n"
            f"Transformed Content Preview:\n"
            f"\"{snippet}\"\n\n"
            f"---\n"
            f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
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


def transform_content(request: TransformRequest) -> TransformResponse:
    """
    Main transformation service function.
    Validates input, checks for API key or mock flag, calls Google Gemini LLM,
    and returns the structured response.
    """
    # 1. Basic validation for invalid input
    if not request.source_content or not request.source_content.strip():
        raise HTTPException(
            status_code=400,
            detail="Invalid input: 'source_content' cannot be empty."
        )

    if not request.output_type or not request.output_type.strip():
        raise HTTPException(
            status_code=400,
            detail="Invalid input: 'output_type' cannot be empty."
        )

    source = request.source_content.strip()
    output_type = request.output_type.strip()
    audience = request.target_audience or "General Audience"
    tone = request.tone or "Professional"
    language = request.language or "English"
    detail = request.detail_level or "Standard"

    # 2. Check if mock mode is explicitly requested via environment variable
    if os.getenv("USE_MOCK", "").lower() in ("true", "1", "yes"):
        return mock_transform_content(request)

    # 3. Retrieve and validate API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip() or api_key.strip() == "your_gemini_api_key_here":
        raise HTTPException(
            status_code=500,
            detail=(
                "Missing API Key: 'GEMINI_API_KEY' is not configured. "
                "Please add your GEMINI_API_KEY in the backend/.env file "
                "(or set USE_MOCK=true to run with mock responses)."
            )
        )

    # 4. Build prompt
    prompt = build_prompt(
        source_content=source,
        output_type=output_type,
        target_audience=audience,
        tone=tone,
        language=language,
        detail_level=detail
    )

    # 5. Call LLM with error handling
    try:
        genai.configure(api_key=api_key.strip())
        model = genai.GenerativeModel("gemini-3.6-flash")
        response = model.generate_content(prompt)

        if not response or not response.text:
            raise HTTPException(
                status_code=502,
                detail="LLM generation failed: Model returned an empty response."
            )

        generated_text = response.text.strip()

    except HTTPException:
        # Re-raise explicit HTTPExceptions
        raise
    except Exception as e:
        # Handle API failure, network errors, invalid keys, or quota issues
        raise HTTPException(
            status_code=502,
            detail=f"LLM API failure: {str(e)}"
        )

    # 6. Return response with metadata
    return TransformResponse(
        status="success",
        output_type=output_type,
        transformed_content=generated_text,
        metadata={
            "target_audience": audience,
            "tone": tone,
            "language": language,
            "detail_level": detail,
            "source_character_count": len(source),
            "model": "gemini-3.6-flash",
            "is_mock": False
        }
    )
