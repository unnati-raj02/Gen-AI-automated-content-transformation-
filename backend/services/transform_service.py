import base64
import os
import re
import warnings
from typing import Optional, Tuple

# Suppress Google SDK deprecation notice in console output
warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import HTTPException

from schemas.transform_schema import TransformRequest, TransformResponse

# Load environment variables from .env file (if present)
load_dotenv()


def parse_media_data(media_data: str, default_mime: str = "image/png") -> Tuple[str, bytes]:
    """
    Parses a data URI (data:<mime_type>;base64,...) or raw base64 string
    and returns (mime_type, raw_bytes).
    Supports images (.png, .jpg, .webp, .gif) and videos (.mp4, .webm, .mov).
    """
    cleaned = media_data.strip()
    if cleaned.startswith("data:"):
        match = re.match(r"^data:([^;]+);base64,(.+)$", cleaned, re.DOTALL)
        if match:
            mime_type = match.group(1).strip()
            raw_b64 = match.group(2).strip()
            return mime_type, base64.b64decode(raw_b64)
    return default_mime, base64.b64decode(cleaned)


def parse_image_data(image_data: str) -> Tuple[str, bytes]:
    """Parses base64 image data (defaulting to image/png)."""
    return parse_media_data(image_data, default_mime="image/png")


def parse_video_data(video_data: str) -> Tuple[str, bytes]:
    """Parses base64 video data (defaulting to video/mp4)."""
    return parse_media_data(video_data, default_mime="video/mp4")


def build_prompt(
    source_content: str,
    output_type: str,
    target_audience: str,
    tone: str,
    language: str,
    detail_level: str,
    communication_objective: Optional[str] = None,
    content_style: Optional[str] = None,
    document_name: Optional[str] = None,
    image_name: Optional[str] = None,
    video_name: Optional[str] = None
) -> str:
    """
    Constructs a structured prompt for the LLM based on source content
    and transformation parameters.
    """
    doc_spec = f"\n- Source Document Name: {document_name}" if document_name else ""
    img_spec = f"\n- Attached Source Image: {image_name} (Analyze and synthesize all visual charts, diagrams, graphics, and text from the image)" if image_name else ""
    vid_spec = f"\n- Attached Source Video: {video_name} (Thoroughly examine visual narrative, scene progression, demonstrations, on-screen text, and spoken audio in the video)" if video_name else ""
    return f"""You are an expert AI content transformer.
Transform the provided source content into the requested communication artefact.

TRANSFORMATION SPECIFICATIONS:
- Target Artefact (Output Type): {output_type}
- Target Audience: {target_audience}
- Tone: {tone}
- Communication Objective: {communication_objective or 'Inform'}
- Content Style: {content_style or 'Direct & Concise'}
- Language: {language}
- Detail Level: {detail_level}{doc_spec}{img_spec}{vid_spec}

SOURCE CONTENT:
\"\"\"
{source_content}
\"\"\"

INSTRUCTIONS:
1. Transform the source content strictly into the format of '{output_type}'.
2. Tailor vocabulary and complexity to the '{target_audience}' audience.
3. Maintain the requested '{tone}' tone throughout the output.
4. Align the narrative structure, messaging emphasis, and presentation flow with the Communication Objective ('{communication_objective or 'Inform'}') and Content Style ('{content_style or 'Direct & Concise'}').
5. Output the result in the '{language}' language.
6. Provide content matching the '{detail_level}' level of detail according to the format structure:
   - If Executive Summary: Include overview, strategic impact, and key takeaways/action items.
   - If Advisory: Include context, risk/operational impact, and clear directives.
   - If LinkedIn Post: Include a strong hook, concise bullet points, a call-to-action, and relevant hashtags.
   - If Twitter/X Post: Provide a concise, platform-optimized post or short threaded sequence (keep each segment punchy, under 280 characters, with high-impact opening hook, clear takeaways, and relevant hashtags).
   - If Infographic: Provide a complete visual blueprint with Catchy Title, Core Key Message, 3-5 Key Points/Statistics, Sectional Narrative Flow, and Layout & Visual Recommendations (suggested icons, chart ideas, and color/design hierarchy).
   - If Presentation: Provide a slide-by-slide structure with 4-6 slides (e.g. Title/Agenda, Context/Problem, Key Solution/Findings, Strategic Impact, and Next Steps). For every slide, clearly provide: Slide Title, 3-4 concise Bullet Points, and Speaker Notes.
   - If Video Package: Provide a complete production package including Video Objective & Target Duration (e.g., 60-90s), Full Voiceover Script, Scene-by-Scene Storyboard breakdown (Scene number, Visual Description/Action, On-Screen Text / Subtitles, and Narration), and Production Recommendations (music mood, pacing, and visual style).
7. If an attached image is provided, thoroughly examine and interpret its visual components (diagrams, flowcharts, data graphs, illustrations, or embedded text) and integrate those insights directly into the output.
8. If an attached video is provided, thoroughly examine and interpret its visual scenes, motion progression, on-screen text/chyrons, demonstrations, and spoken audio track, integrating those insights directly into the output.
9. Do NOT include conversational filler, introductory remarks, or meta-commentary (e.g., do not say "Here is your summary"). Directly output the transformed artefact.
"""


def mock_transform_content(request: TransformRequest) -> TransformResponse:
    """
    Mock transformation fallback.
    Retained for testing without an API key or when offline.
    """
    source = request.source_content.strip()
    audience = request.target_audience or "General Audience"
    tone = request.tone or "Professional"
    objective = request.communication_objective or "Inform"
    style = request.content_style or "Direct & Concise"
    language = request.language or "English"
    detail = request.detail_level or "Standard"

    snippet = source[:120] + "..." if len(source) > 120 else source
    if request.image_name:
        snippet += f" [Attached Image: {request.image_name}]"
    if request.video_name:
        snippet += f" [Attached Video: {request.video_name}]"

    outputs = {}
    for output_type in request.output_types:
        ot_stripped = output_type.strip()
        output_type_lower = ot_stripped.lower()

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
        elif "linkedin" in output_type_lower:
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
        elif "twitter" in output_type_lower or "x post" in output_type_lower:
            transformed_text = (
                f"[MOCK GENERATION - TWITTER/X POST]\n"
                f"Audience: {audience} | Tone: {tone} | Language: {language} | Detail Level: {detail}\n\n"
                f"🧵 1/3: Essential update you need to know today:\n"
                f"\"{snippet}\"\n\n"
                f"2/3: Key takeaways:\n"
                f"• Strategic priorities are actively accelerating.\n"
                f"• Clear communication ensures high alignment across stakeholders.\n\n"
                f"3/3: What impact does this have on your workflow? Drop your thoughts below! 👇\n\n"
                f"#TechTrends #Leadership #Innovation\n"
                f"---\n"
                f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
            )
        elif "infographic" in output_type_lower:
            transformed_text = (
                f"[MOCK GENERATION - INFOGRAPHIC BLUEPRINT]\n"
                f"Audience: {audience} | Tone: {tone} | Language: {language} | Detail Level: {detail}\n\n"
                f"📊 INFOGRAPHIC SPECIFICATION\n\n"
                f"1. Headline Banner:\n"
                f"   \"Transforming Complex Updates into Actionable Insights\"\n\n"
                f"2. Core Message:\n"
                f"   {snippet}\n\n"
                f"3. Key Data & Pillar Points:\n"
                f"   • Metric 1: 95% clarity improvement across recipient groups.\n"
                f"   • Metric 2: 3x faster response cycle for critical updates.\n"
                f"   • Metric 3: End-to-end alignment across core operations.\n\n"
                f"4. Layout & Visual Recommendations:\n"
                f"   - Hierarchy: Top banner header → 3-column metric cards → summary footer.\n"
                f"   - Color Scheme: Modern dark slate (#0B0F19) with indigo (#6366F1) accent.\n"
                f"   - Icon Suggestions: Target icon for goals, lightning bolt for efficiency, handshake for alignment.\n\n"
                f"---\n"
                f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
            )
        elif "presentation" in output_type_lower:
            transformed_text = (
                f"[MOCK GENERATION - PRESENTATION SLIDEDECK]\n"
                f"Audience: {audience} | Tone: {tone} | Language: {language} | Detail Level: {detail}\n\n"
                f"🖥️ SLIDE-BY-SLIDE OUTLINE\n\n"
                f"Slide 1: Title & Executive Overview\n"
                f"• Title: Strategic Content Transformation\n"
                f"• Subtitle: Driving High-Impact Operational Communication\n"
                f"• Speaker Notes: Welcome everyone. Today we are walking through the critical updates derived from source material.\n\n"
                f"Slide 2: Background & Context\n"
                f"• Current Situation: \"{snippet}\"\n"
                f"• Challenge: Navigating fast-moving requirements with cross-functional teams.\n"
                f"• Speaker Notes: Highlight the foundational context and why this matters right now.\n\n"
                f"Slide 3: Strategic Impact & Key Takeaways\n"
                f"• Measurable efficiency gains across primary workflows.\n"
                f"• Standardized communication formats tailored by stakeholder group.\n"
                f"• Speaker Notes: Emphasize the tangible value delivered by this initiative.\n\n"
                f"Slide 4: Roadmap & Next Actions\n"
                f"• Immediate phase-one operational deployment.\n"
                f"• Review metrics after 30 days.\n"
                f"• Speaker Notes: Direct the audience to the action items and open the floor for Q&A.\n\n"
                f"---\n"
                f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
            )
        elif "video" in output_type_lower:
            transformed_text = (
                f"[MOCK GENERATION - VIDEO PRODUCTION PACKAGE]\n"
                f"Audience: {audience} | Tone: {tone} | Language: {language} | Detail Level: {detail}\n\n"
                f"🎬 VIDEO PRODUCTION BRIEF\n"
                f"Target Duration: 60 Seconds | Format: 16:9 Landscape & 9:16 Vertical Cut\n"
                f"Objective: Deliver concise, engaging overview to {audience}.\n\n"
                f"STORYBOARD & SCRIPT BREAKDOWN:\n\n"
                f"Scene 1 (0:00 - 0:10) - The Hook\n"
                f"• Visual: High-energy kinetic text over clean motion background.\n"
                f"• Subtitles: \"Big updates are here. Here's what you need to know.\"\n"
                f"• Voiceover: \"Big updates are here. Here is what you need to know.\"\n\n"
                f"Scene 2 (0:10 - 0:35) - Core Update\n"
                f"• Visual: Screen recording or dynamic infographic breakdown of core points.\n"
                f"• Subtitles: \"{snippet}\"\n"
                f"• Voiceover: \"Looking at the key facts: {snippet}\"\n\n"
                f"Scene 3 (0:35 - 0:50) - Value & Impact\n"
                f"• Visual: Split screen with icons highlighting operational efficiency.\n"
                f"• Subtitles: \"Faster execution. Clearer results. Better alignment.\"\n"
                f"• Voiceover: \"Teams can now execute faster and align better on strategic goals.\"\n\n"
                f"Scene 4 (0:50 - 1:00) - Call to Action\n"
                f"• Visual: Closing brand card with URL and contact handle.\n"
                f"• Subtitles: \"Learn more at our portal today.\"\n"
                f"• Voiceover: \"Check out the full release and stay ahead. See you next time.\"\n\n"
                f"PRODUCTION RECOMMENDATIONS:\n"
                f"• Music: Upbeat, modern ambient electronic with confident rhythm.\n"
                f"• Voiceover Tone: {tone}, clear, articulate, professional pace.\n\n"
                f"---\n"
                f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
            )
        else:
            transformed_text = (
                f"[MOCK GENERATION - {ot_stripped.upper()}]\n"
                f"Audience: {audience} | Tone: {tone} | Language: {language} | Detail Level: {detail}\n\n"
                f"Transformed Content Preview:\n"
                f"\"{snippet}\"\n\n"
                f"---\n"
                f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
            )
        outputs[output_type] = transformed_text

    return TransformResponse(
        status="success",
        outputs=outputs,
        metadata={
            "target_audience": audience,
            "tone": tone,
            "communication_objective": objective,
            "content_style": style,
            "language": language,
            "detail_level": detail,
            "source_character_count": len(source),
            "document_name": request.document_name,
            "image_name": request.image_name,
            "video_name": request.video_name,
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

    if not request.output_types or len(request.output_types) == 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid input: 'output_types' cannot be empty."
        )

    source = request.source_content.strip()
    audience = request.target_audience or "General Audience"
    tone = request.tone or "Professional"
    objective = request.communication_objective or "Inform"
    style = request.content_style or "Direct & Concise"
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

    # 4. Handle optional multimodal image & video inputs
    multimodal_parts = []
    if request.image_data:
        try:
            mime_type, img_bytes = parse_image_data(request.image_data)
            multimodal_parts.append({"mime_type": mime_type, "data": img_bytes})
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image data: {str(e)}"
            )

    if request.video_data:
        try:
            mime_type, vid_bytes = parse_video_data(request.video_data)
            multimodal_parts.append({"mime_type": mime_type, "data": vid_bytes})
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid video data: {str(e)}"
            )

    # 5. Call LLM for each output type with error handling
    outputs = {}
    try:
        genai.configure(api_key=api_key.strip())
        model = genai.GenerativeModel("gemini-3.6-flash")

        for output_type in request.output_types:
            prompt = build_prompt(
                source_content=source,
                output_type=output_type.strip(),
                target_audience=audience,
                tone=tone,
                language=language,
                detail_level=detail,
                communication_objective=objective,
                content_style=style,
                document_name=request.document_name,
                image_name=request.image_name,
                video_name=request.video_name
            )

            content_payload = [prompt] + multimodal_parts if multimodal_parts else prompt
            response = model.generate_content(content_payload)

            if not response or not response.text:
                raise HTTPException(
                    status_code=502,
                    detail=f"LLM generation failed: Model returned an empty response for '{output_type}'."
                )

            outputs[output_type] = response.text.strip()

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
        outputs=outputs,
        metadata={
            "target_audience": audience,
            "tone": tone,
            "communication_objective": objective,
            "content_style": style,
            "language": language,
            "detail_level": detail,
            "source_character_count": len(source),
            "document_name": request.document_name,
            "image_name": request.image_name,
            "video_name": request.video_name,
            "model": "gemini-3.6-flash",
            "is_mock": False
        }
    )
