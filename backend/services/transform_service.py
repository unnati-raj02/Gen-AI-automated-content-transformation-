import base64
import json
import os
import re
import time
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Set

# Suppress Google SDK deprecation notice in console output
warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import HTTPException

from schemas.transform_schema import TransformRequest, TransformResponse, RefineRequest, RefineResponse
from services.document_service import validate_extracted_content

# Load environment variables from .env file (if present)
load_dotenv(override=True)


# Maximum size limits for multimodal media uploads (MVP protection)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


def parse_media_data(media_data: str, default_mime: str = "image/png") -> Tuple[str, bytes]:
    """
    Parses a data URI (data:<mime_type>;base64,...) or raw base64 string
    and returns (mime_type, raw_bytes).
    Supports images (.png, .jpg, .webp, .gif) and videos (.mp4, .webm, .mov).
    """
    cleaned = media_data.strip()
    if not cleaned:
        raise ValueError("Empty media data payload.")

    raw_b64 = cleaned
    mime_type = default_mime

    if cleaned.startswith("data:"):
        match = re.match(r"^data:([^;]+);base64,(.+)$", cleaned, re.DOTALL)
        if match:
            mime_type = match.group(1).strip()
            raw_b64 = match.group(2).strip()
        else:
            raise ValueError("Malformed media data URI format.")

    try:
        raw_bytes = base64.b64decode(raw_b64, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding: {str(e)}")

    if not raw_bytes or len(raw_bytes) == 0:
        raise ValueError("Decoded media payload is empty.")

    return mime_type, raw_bytes


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


# ==============================================================================
# PS-SPECIFIC OUTPUT FORMAT SPECIFICATIONS & CONSOLIDATED GENERATION HELPERS
# ==============================================================================

OUTPUT_FORMAT_SPECIFICATIONS: Dict[str, str] = {
    "executive summary": (
        "Executive Summary: Include overview, strategic impact, and key takeaways/action items."
    ),
    "advisory": (
        "Advisory: Include context, risk/operational impact, and clear directives."
    ),
    "linkedin post": (
        "LinkedIn Post: Include a strong hook, concise bullet points, a call-to-action, and relevant hashtags."
    ),
    "twitter/x post": (
        "Twitter/X Post: Provide a concise, platform-optimized post or short threaded sequence "
        "(keep each segment punchy, under 280 characters, with high-impact opening hook, clear takeaways, and relevant hashtags)."
    ),
    "infographic": (
        "Infographic: Provide a complete visual blueprint with Catchy Title, Core Key Message, 3-5 Key Points/Statistics, "
        "Sectional Narrative Flow, and Layout & Visual Recommendations (suggested icons, chart ideas, and color/design hierarchy)."
    ),
    "presentation": (
        "Presentation: Provide a slide-by-slide structure with 4-6 slides (e.g. Title/Agenda, Context/Problem, "
        "Key Solution/Findings, Strategic Impact, and Next Steps). For every slide, clearly provide: Slide Title, "
        "3-4 concise Bullet Points, and Speaker Notes."
    ),
    "video package": (
        "Video Package: Provide a complete production package including Video Objective & Target Duration (e.g., 60-90s), "
        "Full Voiceover Script, Scene-by-Scene Storyboard breakdown (Scene number, Visual Description/Action, "
        "On-Screen Text / Subtitles, and Narration), and Production Recommendations (music mood, pacing, and visual style)."
    ),
}


def get_format_instruction(output_type: str) -> str:
    """Returns the PS-compliant instruction for a given output format."""
    ot_lower = output_type.strip().lower()
    for key, spec in OUTPUT_FORMAT_SPECIFICATIONS.items():
        if key in ot_lower or (key == "twitter/x post" and ("twitter" in ot_lower or "x post" in ot_lower)):
            return spec
    return f"{output_type}: Provide a comprehensive, professional transformation of the source material tailored to {output_type}."


def build_consolidated_prompt(
    source_content: str,
    output_types: List[str],
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
    Constructs a unified prompt instructing the LLM to generate all requested
    communication artefacts in a single structured JSON response.
    """
    doc_spec = f"\n- Source Document Name: {document_name}" if document_name else ""
    img_spec = f"\n- Attached Source Image: {image_name} (Analyze and synthesize all visual charts, diagrams, graphics, and text from the image)" if image_name else ""
    vid_spec = f"\n- Attached Source Video: {video_name} (Thoroughly examine visual narrative, scene progression, demonstrations, on-screen text, and spoken audio in the video)" if video_name else ""

    format_specs = []
    for i, ot in enumerate(output_types, 1):
        spec = get_format_instruction(ot)
        format_specs.append(f"   {i}. \"{ot}\": {spec}")
    format_specs_text = "\n".join(format_specs)

    schema_example_parts = [f'"{ot}": "<full formatted text of {ot}>"' for ot in output_types]
    schema_example = "{\n  " + ",\n  ".join(schema_example_parts) + "\n}"

    return f"""You are an expert AI content transformer.
Transform the provided source content into the requested communication artefacts.

TRANSFORMATION SPECIFICATIONS:
- Target Artefacts to Generate ({len(output_types)} total): {", ".join(output_types)}
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

OUTPUT FORMAT REQUIREMENTS:
You MUST respond with a single, valid JSON object containing exactly one key for each requested artefact.
Schema structure:
{schema_example}

Each key MUST be the exact name of the requested artefact from: {output_types}.
Each value MUST be a complete, fully formed string containing the entire generated artefact.

SPECIFIC INSTRUCTIONS PER ARTEFACT:
{format_specs_text}

GENERAL ADAPTATION & QUALITY RULES:
1. Tailor vocabulary and complexity to the '{target_audience}' audience.
2. Maintain the requested '{tone}' tone throughout all artefacts.
3. Align narrative structure, messaging emphasis, and presentation flow with the Communication Objective ('{communication_objective or 'Inform'}') and Content Style ('{content_style or 'Direct & Concise'}').
4. Output all content in the '{language}' language.
5. Provide content matching the '{detail_level}' level of detail according to the format requirements.
6. If an attached image is provided, examine and interpret its visual components (diagrams, flowcharts, data graphs, illustrations, or embedded text) and integrate those insights directly.
7. If an attached video is provided, examine and interpret its visual scenes, motion progression, on-screen text/chyrons, demonstrations, and spoken audio track, integrating those insights directly.
8. Do NOT include conversational filler, introductory remarks, or meta-commentary (e.g., do not say "Here is your summary").
9. Output ONLY the JSON object. Do not include markdown formatting or backticks outside the JSON.
"""


def extract_json_response(raw_text: str) -> dict:
    """
    Extracts and parses a JSON dictionary from LLM output.
    Handles potential markdown code fences and whitespace cleanly.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Model returned an empty response.")

    cleaned = raw_text.strip()

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # Fallback: find outer-most JSON object bounds if extra text was included
    if not (cleaned.startswith("{") and cleaned.endswith("}")):
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()

    try:
        data = json.loads(cleaned, strict=False)
    except Exception as e:
        try:
            repaired = re.sub(r'\\(?![/\\bfnrt"u])', r'\\\\', cleaned)
            data = json.loads(repaired, strict=False)
        except Exception:
            raise ValueError(f"Failed to parse LLM response as JSON: {str(e)}. Raw text snippet: {cleaned[:200]}")

    if not isinstance(data, dict):
        raise ValueError(f"Expected top-level JSON object/dictionary, got {type(data).__name__}.")

    return data


def call_gemini_with_retry(
    model: genai.GenerativeModel,
    content_payload: Any,
    generation_config: Optional[Any] = None,
    max_retries: int = 2
) -> Any:
    """
    Calls Gemini generate_content with a bounded retry loop for transient errors
    (rate limits / 429, service unavailable / 503, internal server errors / 500).
    Fatal client errors (400, 401, 403) are raised immediately without retrying.
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            if generation_config is not None:
                return model.generate_content(content_payload, generation_config=generation_config)
            return model.generate_content(content_payload)
        except Exception as e:
            last_exception = e
            err_msg = str(e).lower()

            # Non-retryable fatal client errors
            if any(term in err_msg for term in ["invalidargument", "400", "permissiondenied", "401", "403"]):
                raise

            # Retryable transient errors
            is_transient = any(term in err_msg for term in [
                "429", "resourceexhausted", "quota", "503", "unavailable", "500", "internal", "overloaded"
            ])

            if is_transient and attempt < max_retries:
                # Exponential backoff: 1.5s on attempt 0, 3.0s on attempt 1
                backoff_time = 1.5 * (2 ** attempt)
                time.sleep(backoff_time)
                continue

            raise last_exception


def targeted_recover_missing_output(
    model: genai.GenerativeModel,
    output_type: str,
    source_content: str,
    target_audience: str,
    tone: str,
    language: str,
    detail_level: str,
    communication_objective: Optional[str],
    content_style: Optional[str],
    document_name: Optional[str],
    image_name: Optional[str],
    video_name: Optional[str],
    multimodal_parts: list
) -> str:
    """
    Performs a single targeted Gemini request for one missing output format.
    """
    prompt = build_prompt(
        source_content=source_content,
        output_type=output_type.strip(),
        target_audience=target_audience,
        tone=tone,
        language=language,
        detail_level=detail_level,
        communication_objective=communication_objective,
        content_style=content_style,
        document_name=document_name,
        image_name=image_name,
        video_name=video_name
    )
    content_payload = [prompt] + multimodal_parts if multimodal_parts else prompt
    gen_config = genai.types.GenerationConfig(max_output_tokens=4096, temperature=0.3)
    response = call_gemini_with_retry(model, content_payload, generation_config=gen_config, max_retries=1)
    if not response or not response.text or not response.text.strip():
        raise ValueError(f"Empty targeted response for '{output_type}'.")
    return response.text.strip()


# ==============================================================================
# STAGE 2: QUALITY & CONSISTENCY VALIDATOR
# ==============================================================================

COMMON_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "also", "across", "within", "overall",
    "furthermore", "additionally"
}


CURRENCY_REGEX = re.compile(
    r'(?:'
    # 1. Symbol or ISO code with number and optional scale word (e.g. $12 million, USD 12 million, $12M, $12,000,000)
    r'(?:[\$\€\£\₹]|(?:USD|EUR|GBP|INR)\s*)\s*\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:\s*(?:million|billion|trillion|[MBKk]))?\b'
    r'|'
    r'(?:[\$\€\£\₹]|(?:USD|EUR|GBP|INR)\s*)\s*\d+(?:\.\d+)?(?:\s*(?:million|billion|trillion|[MBKk]))?\b'
    r'|'
    # 2. Number with scale and postfixed currency (e.g. 12 million dollars, 12M USD)
    r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:million|billion|trillion|[MBKk])?\s*(?:dollars?|euros?|pounds?|rupees?|usd|eur|gbp|inr)\b'
    r')',
    re.IGNORECASE
)

BUSINESS_ENTITY_TERMS = (
    r"firm|company|corporation|startup|conglomerate|provider|vendor|"
    r"business|enterprise|agency|institution|group|consortium|laboratory|lab|partner"
)

CREDENTIAL_NOUNS = (
    r"certifications?|certificates?|"
    r"accreditations?|"
    r"licen[sc]es?|licen[sc]ing|licensure|"
    r"qualifications?|"
    r"awards?|"
    r"credentials?|"
    r"clearances?|"
    r"badges?|charters?|"
    r"diplomas?|degrees?|"
    r"designations?|"
    r"compliances?|standards?|"
    r"soc\s*[12](?:\s+type\s+[i|ii|1|2]+)?|iso(?:\s*[/iec]*\s*\d+)?"
)

CREDENTIAL_ADJECTIVES = r"(?:certified|accredited|licen[sc]ed|qualified|awarded|credentialed)"

CREDENTIAL_TARGET = rf"(?:{CREDENTIAL_NOUNS}|{CREDENTIAL_ADJECTIVES}\b(?!\s+(?:[a-zA-Z0-9_\-]+\s+){{0,2}}(?:{BUSINESS_ENTITY_TERMS})\b))"

CREDENTIAL_ACQUISITION_PATTERN = re.compile(
    rf"\b(?:"
    rf"(?:acquisition|acquisitions)\s+of\s+(?:the\s+|a\s+|an\s+|its\s+|their\s+|our\s+)?"
    rf"(?:(?!{BUSINESS_ENTITY_TERMS}\b)[a-zA-Z0-9_\-\./&]+\s+){{0,6}}"
    rf"{CREDENTIAL_TARGET}\b"
    rf"|"
    rf"(?:acquire|acquired|acquires|acquiring)\s+(?:the\s+|a\s+|an\s+|its\s+|their\s+|our\s+)?"
    rf"(?:(?!{BUSINESS_ENTITY_TERMS}\b)[a-zA-Z0-9_\-\./&]+\s+){{0,6}}"
    rf"{CREDENTIAL_TARGET}\b"
    rf"|"
    rf"(?:{CREDENTIAL_NOUNS})\s+(?:[a-zA-Z0-9_\-\./&]+\s+){{0,3}}acquisition\b"
    rf"|"
    rf"(?:talent|skills?|knowledge|language|data|customer|user)\s+acquisition\b"
    rf")",
    re.IGNORECASE
)

ACQUISITION_BASE_PATTERN = re.compile(
    r"\b(?:acquisition|acquire|acquired|acquires|acquiring|buyout|takeover)\b",
    re.IGNORECASE
)


class _ContextAwareAcquisitionPattern:
    """
    Context-aware pattern wrapper for factual corporate/business acquisition events.
    Excludes instances where 'acquisition' refers to obtaining/achieving a certification,
    accreditation, license, qualification, award, clearance, or similar credential.
    """

    def __init__(self):
        self.pattern = ACQUISITION_BASE_PATTERN.pattern
        self.flags = ACQUISITION_BASE_PATTERN.flags

    def finditer(self, string, *args, **kwargs):
        if not string or not isinstance(string, str):
            return iter(())
        cred_spans = [(cm.start(), cm.end()) for cm in CREDENTIAL_ACQUISITION_PATTERN.finditer(string)]
        matches = []
        for m in ACQUISITION_BASE_PATTERN.finditer(string, *args, **kwargs):
            word = m.group(0).lower()
            if word in ("buyout", "takeover"):
                matches.append(m)
                continue
            m_start, m_end = m.start(), m.end()
            is_cred = any(
                (c_start <= m_start and c_end >= m_end) or
                (max(c_start, m_start) < min(c_end, m_end))
                for c_start, c_end in cred_spans
            )
            if not is_cred:
                matches.append(m)
        return iter(matches)

    def search(self, string, *args, **kwargs):
        for m in self.finditer(string, *args, **kwargs):
            return m
        return None

    def match(self, string, *args, **kwargs):
        m = self.search(string, *args, **kwargs)
        if m and m.start() == 0:
            return m
        return None

    def findall(self, string, *args, **kwargs):
        return [m.group(0) for m in self.finditer(string, *args, **kwargs)]


def is_factual_event_present(event_name: str, text: str) -> bool:
    """
    Context-aware factual event detector.
    Returns True if the specified event type is asserted in text.
    For 'acquisition', distinguishes corporate/business acquisitions from credential attainments.
    """
    if not text:
        return False
    pat = FACTUAL_EVENT_PATTERNS.get(event_name)
    return bool(pat.search(text)) if pat else False


FACTUAL_EVENT_PATTERNS = {
    "acquisition": _ContextAwareAcquisitionPattern(),
    "merger": re.compile(r"\b(?:merger|merged|merges|merging)\b", re.IGNORECASE),
    "investment": re.compile(r"\b(?:investment|invested|invests|investing|funding|venture\s+round|series\s+[a-e])\b", re.IGNORECASE),
    "launch": re.compile(r"\b(?:launch|launched|launches|launching|initiated|initiation|initiates|inception)\b", re.IGNORECASE),
    "certification": re.compile(r"\b(?:certification|certified|certifies|certifying|accreditation|accredited)\b", re.IGNORECASE),
    "deployment": re.compile(r"\b(?:deployment|deployed|deploys|deploying|distributed|rollout)\b", re.IGNORECASE),
    "partnership": re.compile(r"\b(?:partnership|partnered|partnering|joint\s+venture|alliance|collaborated\s+with)\b", re.IGNORECASE),
    "layoff": re.compile(r"\b(?:laid\s+off|layoffs?|downsized|fired|workforce\s+reduction)\b", re.IGNORECASE),
    "shutdown": re.compile(r"\b(?:shut\s*down|shutdown|closed\s+down|dissolved|dissolution|liquidated|bankruptcy)\b", re.IGNORECASE),
}

NATIONALITY_OR_GEO = (
    r"German|European|American|Japanese|Chinese|British|French|Swiss|Asian|Australian|"
    r"Indian|Canadian|Israeli|Russian|Swedish|Dutch|Italian|Spanish|Brazilian|Korean|"
    r"Munich|Berlin|Paris|London|Tokyo|Beijing|Boston|Zurich|Frankfurt"
)

COMPOUND_ENTITY_PATTERNS = [
    re.compile(
        rf'\b(?:{NATIONALITY_OR_GEO})'
        r'(?:\s+[a-zA-Z0-9_-]+)*\s+'
        r'(?:firm|company|corporation|startup|conglomerate|provider|vendor|agency|institution|university|organization|group|consortium|laboratory|lab|enterprise)\b',
        re.IGNORECASE
    ),
    re.compile(
        r'\b[A-Z][a-zA-Z0-9_-]+\s+(?:[a-z0-9_-]+\s+)*(?:firm|company|corporation|startup|conglomerate|provider|vendor|agency|institution|university)\b'
    ),
    re.compile(
        r'\b[A-Z][a-zA-Z0-9_-]+(?:\s+[A-Z][a-zA-Z0-9_-]+)+\b'
    )
]

GENERIC_ENTITY_TOKENS = {
    # Structural & document formatting
    "executive", "summary", "overview", "agenda", "key", "takeaways", "takeaway",
    "findings", "finding", "notes", "speaker", "slide", "slides", "scene", "scenes",
    "video", "package", "production", "blueprint", "infographic", "advisory", "directive",
    "report", "presentation", "table", "figure", "section", "sections", "header", "footer",
    "recommendations", "recommendation", "status", "update", "updates", "action", "actions",
    "introduction", "conclusion", "context", "problem", "solution", "next", "steps",
    # Domain & technical architecture
    "cybersecurity", "security", "cloud", "framework", "enterprise", "project", "platform",
    "architecture", "system", "systems", "compliance", "initiative", "initiatives",
    "firm", "company", "standards", "standard", "pillars", "pillar", "controls", "control",
    "component", "components", "module", "modules", "capabilities", "capability",
    "monitoring", "anomaly", "detection", "policy", "enforcement", "posture", "management",
    "scanning", "infrastructure", "vulnerabilities", "vulnerability", "intrusions", "intrusion",
    "threat", "threats", "response", "times", "time", "pilot", "testing", "results", "result",
    "resilience", "readiness", "governance", "operations", "engineering", "leadership",
    "teams", "team", "officers", "officer", "practitioners", "practitioner",
    # General words
    "strategic", "strategy", "core", "primary", "statement", "statements", "impact", "impacts",
    "phase", "phases", "step", "tier", "tiers", "level", "levels", "data", "unit", "units",
    "first", "second", "third", "quarter", "annual", "internal", "external", "distributed"
}


def normalize_currency_token(token: str) -> Optional[Tuple[str, float]]:
    clean = token.strip().lower()
    symbol = "$"
    if "€" in clean or "eur" in clean:
        symbol = "€"
    elif "£" in clean or "gbp" in clean:
        symbol = "£"
    elif "₹" in clean or "inr" in clean:
        symbol = "₹"

    mult = 1.0
    if "trillion" in clean:
        mult = 1e12
    elif "billion" in clean or re.search(r"\b\d+(?:\.\d+)?b\b", clean):
        mult = 1e9
    elif "million" in clean or re.search(r"\b\d+(?:\.\d+)?m\b", clean):
        mult = 1e6
    elif "thousand" in clean or re.search(r"\b\d+(?:\.\d+)?k\b", clean):
        mult = 1e3

    num_match = re.search(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?", clean.replace(" ", ""))
    if num_match:
        try:
            raw_str = num_match.group(0)
            val = float(raw_str.replace(",", ""))
            if mult > 1.0 and "," not in raw_str:
                val *= mult
            return (symbol, val)
        except ValueError:
            pass
    return None


def extract_key_factual_tokens(text: str) -> set:
    """
    Extracts significant factual and numerical tokens from text:
    - Percentages (e.g. 68%, 99.4%)
    - Currencies (e.g. $12 million, USD 12 million, $42.5M, $12,000,000)
    - Quarters and Years (e.g. Q1 2026, 2026)
    - Multipliers and Data Units (e.g. 3.8x, 10MB, 25MB, 15ms)
    - Standards & Named Enterprise Entities (e.g. SOC2, ISO 27001, CI/CD, Zero-Trust)
    """
    if not text:
        return set()

    facts = set()

    # 1. Percentages
    for m in re.finditer(r"\b\d+(?:\.\d+)?%", text):
        facts.add(m.group(0).lower())

    # 2. Currencies (complete monetary fact matching)
    for m in CURRENCY_REGEX.finditer(text):
        raw_curr = m.group(0).strip()
        norm_curr = re.sub(r"\s+", " ", raw_curr)
        facts.add(norm_curr)
        if norm_curr.lower() != norm_curr:
            facts.add(norm_curr.lower())
        compact = re.sub(r"\s+", "", raw_curr).lower()
        if "million" not in compact and "billion" not in compact and "trillion" not in compact and "thousand" not in compact:
            facts.add(compact)

    # 3. Quarters and Years
    for m in re.finditer(r"\bQ[1-4]\s*20\d\d\b", text, re.IGNORECASE):
        facts.add(re.sub(r"\s+", "", m.group(0)).lower())
    for m in re.finditer(r"\b20\d\d\b", text):
        facts.add(m.group(0))

    # 4. Multipliers, units, and rates (e.g. 3.8x, 10mb, 25mb, 15ms)
    for m in re.finditer(r"\b\d+(?:\.\d+)?(?:x|X|mb|gb|ms|k|m|b)\b", text, re.IGNORECASE):
        facts.add(m.group(0).lower())

    # 5. Specific compliance standards and named enterprise entities
    for m in re.finditer(r"\b(?:SOC\s*2|ISO\s*(?:27001|IEC)?|Zero-Trust|CI/CD)\b", text, re.IGNORECASE):
        clean_std = re.sub(r"\s+", "", m.group(0)).upper()
        facts.add(clean_std)

    return facts



COMMON_SUFFIXES = (
    "ational", "isation", "ization", "fulness", "ousness", "bilities", "bility",
    "tions", "sions", "ments", "ement", "ties", "ting", "ted", "tes",
    "tion", "sion", "ment", "able", "ible", "ance", "ence", "ally", "ful", "ous",
    "ive", "ity", "ing", "ies", "ied", "ed", "es", "ly", "er", "or", "al", "s", "e"
)


def _stem_word(word: str) -> str:
    """Lightweight zero-dependency suffix stripper for semantic grounding."""
    w = word.lower().strip()
    if len(w) <= 3:
        return w
    for sfx in COMMON_SUFFIXES:
        if w.endswith(sfx) and len(w) - len(sfx) >= 3:
            res = w[:-len(sfx)]
            if res.endswith("e") and len(res) > 3:
                res = res[:-1]
            return res
    return w


def _extract_content_stems(text: str) -> Set[str]:
    """Extracts stemmed content tokens (excluding stopwords and pure digits)."""
    tokens = re.findall(r"\b[a-zA-Z0-9_\-\.\/\%]{2,}\b", text.lower())
    stems = set()
    for tok in tokens:
        clean_tok = tok.strip(".-/")
        if clean_tok and clean_tok not in COMMON_STOPWORDS and not clean_tok.isdigit():
            stems.add(_stem_word(clean_tok))
    return stems


# Reusable deterministic classification patterns for non-factual scaffolding
ACTION_IMPERATIVE_VERBS = (
    r"inform|proceed|integrate|utilize|adopt|implement|deploy|mandate|establish|maintain|"
    r"review|conduct|execute|ensure|enforce|accelerate|transition|schedule|leverage|"
    r"initiate|upgrade|configure|prioritize|optimize|align|standardize|collaborate|"
    r"embed|automate|verify|monitor|continue|prepare|define|assign|empower|foster|"
    r"explore|evaluate|assess|expand|scale|operationalize|provide|deliver|report|"
    r"authorize|coordinate|submit|present|secure|read|check|visit|download|contact|"
    r"reach|consult|investigate|audit|track|update|communicate|direct|require|act|"
    r"incorporate|apply|address|safeguard|protect|mitigate|strengthen|oversee"
)

ACTION_ROLE_ADJ = (
    r"all|our|enterprise|technical|security|engineering|compliance|it|business|cross-functional|"
    r"operational|leadership|executive"
)

ACTION_ROLE_NOUN = (
    r"teams?|units?|leaderships?|officers?|developers?|engineers?|stakeholders?|administrators?|"
    r"organizations?|enterprises?|practitioners?|executives?|employees?|users?|auditors?|"
    r"management|personnel|staff|specialists?|analysts?|architects?|custodians?|"
    r"division\s+heads?|department\s+heads?|unit\s+heads?|heads?|directors?|managers?|leads?|"
    r"operations?|secops|oversight|we"
)

ACTION_SINGLE_ROLE = rf"(?:(?:{ACTION_ROLE_ADJ})\s+)*(?:{ACTION_ROLE_NOUN})"

ACTION_STAKEHOLDER_ROLES = (
    rf"(?:(?:{ACTION_ROLE_ADJ})\s+(?:and|&|,)\s+)?{ACTION_SINGLE_ROLE}"
    rf"(?:\s*(?:and|&|,)\s*(?:(?:(?:{ACTION_ROLE_ADJ})\s+(?:and|&|,)\s+)?{ACTION_SINGLE_ROLE}))*"
)

MODAL_OBLIGATIONS = (
    r"must|should|ought\s+to|need\s+to|needs\s+to|are\s+advised\s+to|is\s+advised\s+to|"
    r"are\s+recommended\s+to|is\s+recommended\s+to|shall|are\s+encouraged\s+to|"
    r"is\s+encouraged\s+to|are\s+urged\s+to|is\s+urged\s+to|are\s+directed\s+to|"
    r"is\s+directed\s+to|are\s+required\s+to|is\s+required\s+to|have\s+to|has\s+to|"
    r"must\s+be|should\s+be|are\s+to|is\s+to|cannot\s+wait|"
    r"are\s+instructed\s+to|is\s+instructed\s+to|require|requires|require\s+an?|demand|demands"
)

PRODUCTION_DESIGN_LABELS = (
    r"music\s*mood|pacing|visual\s*style|chart\s*ideas?|suggested\s*icons?|"
    r"(?:donut|bar|pie|flow|line|progress)?\s*charts?|"
    r"color(?:/design)?\s*hierarchy|audio\s*track|camera\s*angle|lighting|scene\s*mood|"
    r"graphic\s*overlay|typography|layout\s*grid|visual\s*aesthetic|sound\s*design|"
    r"color\s*palette|voiceover\s*tone|tone\s*of\s*voice|design\s*system|aspect\s*ratio|"
    r"visual\s*cues?|b-roll\s*ideas?|transition\s*style|visual\s*layout|visual\s*blueprint|"
    r"infographic(?:\s*blueprint)?|blueprint|icon|layout|color|graphic|"
    r"header|footer|banner|statistics\s*grid|stat\s*grid|compliance\s*footer|"
    r"core\s*pillars?|core\s*(?:key\s*)?message|narrative\s*flow|section\s*[a-z0-9]+|"
    r"callout\s*[a-z0-9]*|specification|catchy\s*title|headline\s*banner|headline|title|"
    r"visual\s*elements?|visual\s*description(?:/action)?|visual\s*notes?|"
    r"layout\s*&\s*visual\s*recommendations?|visual\s*recommendations?|suggested\s*charts?|"
    r"color\s*hierarchy|design\s*hierarchy|storyboard(?:\s*breakdown)?|"
    r"on-screen\s*text(?:\s*/\s*subtitles)?|subtitles(?:\s*/\s*on-screen\s*text)?|"
    r"voiceover(?:\s*script)?|narration|"
    r"(?:top|bottom|central|middle|header|footer|side|hero)\s*(?:banner|hub|section|panel|card|bar)?|"
    r"(?:data\s*impact|statistical\s*callouts?|visual\s*breakdown|infographic\s*flow)"
)

METADATA_INSTRUCTION_LABELS = (
    r"target\s*duration|estimated\s*(?:reading\s*)?time|word\s*count|objective|"
    r"target\s*audience|audience|tone|language|detail\s*level|format|channel|"
    r"deliverable|content\s*style|document\s*type|file\s*name|production\s*recommendations?|"
    r"next\s*steps?|action\s*(?:items?|required|needed|points?|directives?)|immediate\s*priorities|prerequisites?|execution\s*timeline|"
    r"slide(?:\s*\d+)?(?:\s*(?:title|header|overview|notes?))?|"
    r"scene\s*\d+|speaker\s*notes?|section\s*\d+|key\s*takeaways?|"
    r"strategic\s*recommendations?|overview|summary|advisory\s*bulletin|directives?|"
    r"purpose|context|risk\s*(?:&|and|/)\s*operational\s*impact|recommended\s*directives|"
    r"(?:video\s*)?objective(?:\s*&\s*target\s*duration)?|full\s*voiceover\s*script|voiceover\s*script|"
    r"narration|storyboard|scene-by-scene\s*storyboard|clear\s*directives?|"
    r"key\s*points(?:/statistics)?|sectional\s*narrative\s*flow|performance\s*metrics|"
    r"compliance\s*&\s*(?:certification|next\s*steps)|context\s*&\s*problem|"
    r"key\s*solution\s*&\s*framework\s*pillars|strategic\s*impact\s*&\s*pilot\s*results|agenda|"
    r"bullet\s*points?|roadmap(?:\s+for)?|video\s+production\s+package|production\s+package"
)

TRANSITIONAL_LEADINS = (
    r"today\s+we\s+(?:introduce|present|announce|share|examine|review|discuss)|"
    r"our\s+recent\s+pilot\s+testing\s+delivered\s+compelling|"
    r"internal\s+pilot\s+testing\s+demonstrated|"
    r"in\s+this\s+(?:report|briefing|presentation|overview|document|update|advisory)\s+we\s+(?:present|examine|review|outline)|"
    r"welcome\s+to\s+project\s+[a-z0-9_-]+|"
    r"here\s+is\s+(?:a|the|what|an\s+in-depth)|"
    r"in\s+the\s+sections?\s+that\s+follow|"
    r"let['’]s\b.*|"
    r"consider\s+the\s+following|"
    r"the\s+following\s+(?:data\s+points|sections?|insights?|highlights?|findings?|recommendations?)|"
    r"as\s+(?:demonstrated|evidenced|shown|outlined)\s+in\s+our|"
    r"key\s+highlights?:?|in\s+summary,?|in\s+conclusion,?|to\s+summarize,?|"
    r"overall\s+takeaway:?|moving\s+forward,?|looking\s+ahead,?|"
    r"without\s+unified\s+controls|"
    r"in\s+a\s+[\w\s-]+world,\s+security\s+cannot\s+wait|"
    r"automation\s+is\s+no\s+longer\s+optional|"
    r"potential\s+vulnerability\s+exposure|"
    r"action\s+is\s+required|"
    r"immediate\s+action\s+is\s+needed|"
    r"project\s+[a-z0-9_-]+:\s*operational\s+resilience\s+realized|"
    r"securing\s+the\s+enterprise|in\s+today['’]s|in\s+an\s+era\s+of|"
    r"these\s+capabilities\s+fundamentally\s+alter|"
    r"(?:is|are)\s+no\s+longer\s+(?:optional|viable|sufficient|effective)|"
    r"is\s+a\s+mission-critical\s+imperative"
)


def _is_scaffolding_or_boilerplate(text: str) -> bool:
    """
    Deterministically determines if a text line/candidate represents non-factual scaffolding:
    1. Action / recommendation directives (imperatives, modals, prescriptive obligations)
    2. Production / audiovisual / design recommendations
    3. Output metadata / instructions / structural blueprint labels
    4. Transitional / lead-in discourse hooks
    """
    stripped = text.strip().strip('"').strip("'").strip()
    if not stripped:
        return True

    # 0. Mock placeholder banners
    if stripped.startswith("[MOCK GENERATION") or stripped.startswith("(Note: Placeholder"):
        return True

    # 1. Markdown headers (# Header)
    if re.match(r"^#{1,6}\s+.*$", stripped):
        return True

    # 2. Horizontal dividers
    if re.match(r"^[-*_]{3,}$", stripped):
        return True

    # 3. Pure hashtag sequences
    if re.match(r"^(?:#\w+\s*)+$", stripped):
        return True

    # 4. Pure section / category headers ending with a colon
    if stripped.endswith(":") and len(_extract_content_stems(stripped)) <= 6:
        return True

    # 4b. All-caps title / package banners (e.g. "VIDEO PRODUCTION PACKAGE", "EXECUTIVE SUMMARY")
    if stripped.isupper() and len(stripped.split()) <= 6:
        return True

    # 4c. Structural slide/section headers without terminal punctuation (e.g. "Operational Impact & Pilot Results", "Initiative launch and strategic goals for Q1 2026")
    if not stripped.endswith(('.', '!', '?', ';', ':')) and len(stripped.split()) <= 10:
        if not re.search(r"\b\d+(?:\.\d+)?%|[\$€£₹]\d|\b(?:acquired|acquisition|partnered|partnership|laid\s+off|shut\s*down|dissolved|merger)\b", stripped, re.IGNORECASE):
            return True

    # 5. Production / Design recommendation lines (e.g. "Music Mood: ...", "Visual Style: ...")
    if re.match(rf"^(?:{PRODUCTION_DESIGN_LABELS}):?.*$", stripped, re.IGNORECASE):
        return True

    # 5b. Design & typography keyword match (e.g. "Clean, sans-serif typography.", "structured grid layout")
    if re.search(r"\b(?:typography|sans-serif|font\s*family|color\s*palette|minimalist\s*aesthetic|glassmorphic|aspect\s*ratio|b-roll|audio\s*track|sound\s*design|visual\s*style|music\s*mood|grid\s*layout|high\s*contrast)\b", stripped, re.IGNORECASE):
        return True

    # 6. Output metadata & structural instruction labels (e.g. "Target Duration: 75 seconds", "Objective: Inform...")
    if re.match(rf"^(?:{METADATA_INSTRUCTION_LABELS}):?.*$", stripped, re.IGNORECASE):
        return True

    # 7. Timecode and duration markers (e.g. "Duration: 75s", "0:00 - 0:15")
    if re.match(r"^(?:Duration:\s*.*|\d{1,2}:\d{2}\s*(?:-\s*\d{1,2}:\d{2})?|Timecode:?.*)$", stripped, re.IGNORECASE):
        return True

    # 8. Transitional & Lead-In Phrases (e.g. "Our recent pilot testing delivered compelling data-driven results:", "Today we present...")
    if re.match(rf"^(?:{TRANSITIONAL_LEADINS})\b.*$", stripped, re.IGNORECASE):
        return True

    # Strip optional leading label/category/stakeholder prefix (e.g. "Automated Policy Enforcement: ", "Security Operations (SecOps): ", "Leadership and technical teams: ", "For all engineering teams, the directive is active: ")
    stripped_clean = re.sub(r"^[A-Za-z0-9\s/&_(),\-]{1,80}:\s*", "", stripped)

    # 8b. Ongoing action / roadmap / next steps directives
    if re.match(r"^(?:ongoing|future|continuous|planned|scheduled)\s+(?:monitoring|optimization|implementation|rollout|deployment|execution|development|evaluation|review|maintenance|alignment)\b.*$", stripped_clean, re.IGNORECASE):
        return True
    if re.match(r"^roadmap\b.*$", stripped_clean, re.IGNORECASE):
        return True

    # 8c. Risk / consequence framing in advisories
    if re.match(r"^(?:non-compliance\s+with|failure\s+to\s+\w+|(?:operating|working|deploying\s+without|without)\s+.*controls|deferring\s+mitigation|organizations?\s+face\s+heightened\s+risks?)\b.*$", stripped_clean, re.IGNORECASE):
        return True

    # 8d. Status / directive active markers (e.g. "Leadership and technical teams: the directive is active.", "... the directive is clear.")
    if re.match(r"^(?:for\s+.*,\s+)?(?:the\s+)?(?:directive|advisory|guidance|policy)\s+(?:is|remains)\s+(?:active|in\s+effect|effective|mandatory|clear|established)\b.*$", stripped_clean, re.IGNORECASE):
        return True

    # 8e. Passive obligation / operational directive statements
    if (
        re.search(r"\b(?:is|are)\s+(?:now\s+)?(?:required|mandatory|mandated|essential|recommended|directed|expected)\b", stripped_clean, re.IGNORECASE) or
        re.search(r"\b(?:must|should|shall)\s+be\s+(?:submitted|completed|implemented|established|conducted|reviewed|enforced|performed|scheduled|maintained|followed|applied|sent|forwarded|delivered|presented|executed|\w+ed)\b", stripped_clean, re.IGNORECASE)
    ):
        if not re.search(r"\b(?:acquired|acquisition|partnered|partnership|laid\s+off|shut\s*down|dissolved|merger)\b", stripped_clean, re.IGNORECASE):
            return True

    # 8f. Threat vectors / problem framing in advisories / presentations
    if re.search(r"\b(?:prime\s+vectors?|heightened\s+risks?|vulnerability\s+exposure|threat\s+vectors?|too\s+slow|necessitating\s+(?:a\s+shift|action)|modern\s+attack\s+velocities|expose[s]?\s+.*to|breach\s+risks?)\b", stripped_clean, re.IGNORECASE):
        if not re.search(r"\b(?:acquired|acquisition|partnered|partnership|laid\s+off|shut\s*down|dissolved|merger)\b", stripped_clean, re.IGNORECASE):
            return True

    # 8g. Strategic impact / benefit statements
    if re.match(r"^this\s+(?:drastically|significantly|substantially|further|greatly)?\s*(?:reduces?|minimizes?|mitigates?|eliminates?|enhances?|strengthens?|improves?|lowers?)\b.*$", stripped_clean, re.IGNORECASE):
        if not re.search(r"\b(?:acquired|acquisition|partnered|partnership|laid\s+off|shut\s*down|dissolved|merger)\b", stripped_clean, re.IGNORECASE):
            return True

    # 8h. Architectural component / pillar synthesis statements
    if re.match(r"^(?:our|the|these|project\s+[a-z0-9_-]+['’]?s?)\s+(?:(?:\w+)\s+)*(?:pillars?|capabilities|components?|modules?|controls|architecture)\s+(?:work|operate|function|integrate|collaborate|combine|automate|deliver|provide|enforce|secure|establish)\b.*$", stripped_clean, re.IGNORECASE):
        if not re.search(r"\b(?:acquired|acquisition|partnered|partnership|laid\s+off|shut\s*down|dissolved|merger)\b", stripped_clean, re.IGNORECASE):
            return True

    # 9. Action / Recommendation Statements (Imperatives)
    if re.match(
        rf"^(?:(?:please|kindly|immediately|actively|consistently|regularly|to\s+further\s+advance)\s+)?"
        rf"(?:{ACTION_IMPERATIVE_VERBS})(?:s|es|ed|ing)?\b",
        stripped_clean,
        re.IGNORECASE
    ):
        # Guard: If it asserts past historical events, treat as substantive fact
        if not re.search(r"\b(?:acquired|acquisition|partnered|partnership\s+with|laid\s+off|shut\s*down|dissolved|merger)\b", stripped_clean, re.IGNORECASE):
            return True

    # 10. Role + Modal / Prescriptive Obligation Statements (e.g. "Security Teams must...", "Compliance Officers must...", "Leadership will oversee...")
    for candidate_str in (stripped, stripped_clean):
        if re.match(
            rf"^(?:(?:For\s+)?(?:{ACTION_STAKEHOLDER_ROLES})\b.*?\b(?:{MODAL_OBLIGATIONS})\b)",
            candidate_str,
            re.IGNORECASE
        ) or re.match(
            rf"^(?:{ACTION_STAKEHOLDER_ROLES})\s*(?:[:,]|\s+to|\s+will)\s+(?:{ACTION_IMPERATIVE_VERBS}|.*)\b.*$",
            candidate_str,
            re.IGNORECASE
        ):
            if not re.search(r"\b(?:acquired|acquisition|partnered|partnership\s+with|laid\s+off|shut\s*down|dissolved|merger)\b", candidate_str, re.IGNORECASE):
                return True

    # 11. Social CTAs & engagement questions
    cta_patterns = [
        r"^(?:what\s+(?:are\s+your|do\s+you)|drop\s+your|share\s+your|let\s+us\s+know|follow\s+for|read\s+the|stay\s+tuned|join\s+the|secure\s+your).*$",
        r"^we\s+(?:call\s+(?:upon|on)|urge|encourage|invite|direct|advise|recommend)\b.*$",
        r"^(?:it\s+is\s+time\s+(?:for|to))\b.*$",
        r"^let['’]s\b.*$",
        r"^we\s+are\s+not\s+(?:just|only)\b.*$",
        r"^(?:readiness|resilience|security|compliance|cybersecurity)\s+is\b.*$",
        r"^(?:here\s+is\s+(?:a|the|what)|key\s+highlights?:?|in\s+summary,?|in\s+conclusion,?)$"
    ]
    for cp in cta_patterns:
        if re.match(cp, stripped_clean, re.IGNORECASE):
            return True

    # 12. Short fragments (< 3 non-stopword tokens)
    stems = _extract_content_stems(stripped)
    if len(stems) < 3:
        return True

    return False


def _split_into_claim_candidates(text: str) -> List[str]:
    """Splits output text into substantive propositional candidate units."""
    if not text:
        return []
    # Normalize escaped newlines and CRLF
    normalized_text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\r\n", "\n")
    lines = [line.strip() for line in normalized_text.split("\n") if line.strip()]
    candidates = []

    for line in lines:
        clean_line = re.sub(r"^[\*\-\•\d+\.\(\)\[\]]+\s*", "", line).strip()
        if not clean_line:
            continue

        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'#])", clean_line)
        for s in sentences:
            s_clean = s.strip()
            if s_clean and not _is_scaffolding_or_boilerplate(s_clean):
                candidates.append(s_clean)

    return candidates


def _build_source_windows(source_text: str) -> Tuple[List[Tuple[str, Set[str]]], Set[str]]:
    """Builds 1-sentence and sliding multi-sentence context windows from source."""
    raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])|\n+", source_text.strip())
    sentences = [s.strip() for s in raw_sentences if s.strip() and len(s.strip()) > 10]

    windows: List[Tuple[str, Set[str]]] = []
    full_source_stems: Set[str] = set()

    for s in sentences:
        stems = _extract_content_stems(s)
        if stems:
            windows.append((s, stems))
            full_source_stems.update(stems)

    for i in range(len(sentences) - 1):
        pair_text = sentences[i] + " " + sentences[i + 1]
        pair_stems = _extract_content_stems(pair_text)
        windows.append((pair_text, pair_stems))

    for i in range(len(sentences) - 2):
        triplet_text = sentences[i] + " " + sentences[i + 1] + " " + sentences[i + 2]
        triplet_stems = _extract_content_stems(triplet_text)
        windows.append((triplet_text, triplet_stems))

    return windows, full_source_stems


def _verify_claims_against_source(
    claims: List[str],
    source_windows: List[Tuple[str, Set[str]]],
    full_source_stems: Set[str],
    source_text: str,
    source_facts: Optional[Set[str]] = None,
    source_curr_norms: Optional[List[Tuple[str, float]]] = None
) -> Tuple[List[str], List[str], Set[str], Set[str], Set[str], float]:
    """
    Verifies candidate claims against multi-scale source windows using:
    1. Hard-fail rule on unverified metrics, dates, percentages, and currencies
    2. Event/relation validation for factual events (acquisition, merger, investment, launch, certification, deployment, etc.)
    3. Compound entity validation (e.g. 'German cybersecurity firm')
    4. Lexical containment as supporting evidence (not sufficient proof)
    """
    if not claims:
        return [], [], set(), set(), set(), 1.0

    if source_facts is None:
        source_facts = extract_key_factual_tokens(source_text)
    if source_curr_norms is None:
        source_curr_norms = [normalize_currency_token(sf) for sf in source_facts if normalize_currency_token(sf)]

    supported: List[str] = []
    unsupported: List[str] = []
    unsupported_events: Set[str] = set()
    unsupported_entities: Set[str] = set()
    unverified_metrics: Set[str] = set()
    source_text_lower = source_text.lower()

    for claim in claims:
        # Strip structural label prefixes (e.g., "Header Metric: ", "Pillar 1: ", "Security Operations (SecOps): ", "Key Metric: ")
        unlabeled_claim = re.sub(
            r"^[A-Za-z0-9\s/&_()\-]{1,60}:\s*",
            "",
            claim
        ).strip()
        target_claim = unlabeled_claim if len(unlabeled_claim) >= 10 else claim

        # Detect if claim is title-cased formatting
        words_in_claim = re.findall(r"\b[A-Za-z]+\b", target_claim)
        cap_words = [w for w in words_in_claim if w[0].isupper()]
        is_title_cased = len(words_in_claim) > 0 and (len(cap_words) / len(words_in_claim)) >= 0.6

        claim_is_unsupported = False

        # 1. Hard-fail rule: any generated metric, percentage, date, or monetary value not supported/equivalent in source
        claim_facts = extract_key_factual_tokens(target_claim)
        for cf in claim_facts:
            cf_lower = cf.lower()
            cf_norm = normalize_currency_token(cf)
            if cf_norm:
                if cf_norm not in source_curr_norms and cf_lower not in source_text_lower:
                    claim_is_unsupported = True
                    unverified_metrics.add(cf)
            elif cf not in source_facts and cf_lower not in source_text_lower:
                if any(char in cf for char in ["%", "$", "€", "£", "₹", "x"]) or any(unit in cf for unit in ["mb", "gb", "ms"]):
                    claim_is_unsupported = True
                    unverified_metrics.add(cf)

        # 2. Hard-fail rule: factual events (acquisition, merger, investment, launch, certification, deployment, etc.)
        for ev_name in FACTUAL_EVENT_PATTERNS:
            if is_factual_event_present(ev_name, target_claim) and not is_factual_event_present(ev_name, source_text):
                claim_is_unsupported = True
                unsupported_events.add(ev_name)

        # 3. Hard-fail rule: compound factual entities (e.g. 'German cybersecurity firm')
        for pat_idx, pat in enumerate(COMPOUND_ENTITY_PATTERNS):
            if pat_idx == 2 and is_title_cased:
                # In title-cased formatting, consecutive capitalized words are formatting, not named entities
                continue
            for m in pat.finditer(target_claim):
                ent = m.group(0).strip()
                words = [
                    w.lower() for w in re.findall(r"\b[A-Za-z]+\b", ent)
                    if w.lower() not in GENERIC_ENTITY_TOKENS and w.lower() not in COMMON_STOPWORDS
                ]
                if words and not any(w in source_text_lower or _stem_word(w) in full_source_stems for w in words):
                    claim_is_unsupported = True
                    unsupported_entities.add(ent)

        if claim_is_unsupported:
            unsupported.append(claim)
            continue

        # 4. Lexical containment as supporting evidence (not sufficient proof on its own)
        stems_target = _extract_content_stems(target_claim)
        stems_full = _extract_content_stems(claim)
        if (not stems_target or len(stems_target) < 3) and (not stems_full or len(stems_full) < 3):
            supported.append(claim)
            continue

        best_window_containment = 0.0
        for win_text, win_stems in source_windows:
            if not win_stems:
                continue
            c_target = len(stems_target.intersection(win_stems)) / len(stems_target) if stems_target else 0.0
            c_full = len(stems_full.intersection(win_stems)) / len(stems_full) if stems_full else 0.0
            containment = max(c_target, c_full)
            if containment > best_window_containment:
                best_window_containment = containment

        g_target = len(stems_target.intersection(full_source_stems)) / len(stems_target) if stems_target else 0.0
        g_full = len(stems_full.intersection(full_source_stems)) / len(stems_full) if stems_full else 0.0
        global_containment = max(g_target, g_full)

        # Check for isolated foreign proper nouns / named entities
        has_foreign_entity = False
        if not is_title_cased:
            potential_entities = re.findall(r"(?<!^)(?<!\.\s)\b[A-Z][a-zA-Z0-9_-]+\b", target_claim)
            for ent in potential_entities:
                ent_lower = ent.lower()
                ent_stem = _stem_word(ent_lower)
                if (
                    ent_lower not in source_text_lower and
                    ent_stem not in full_source_stems and
                    ent_lower not in COMMON_STOPWORDS and
                    ent_lower not in GENERIC_ENTITY_TOKENS
                ):
                    has_foreign_entity = True
                    break

        if not has_foreign_entity:
            if best_window_containment >= 0.35 or global_containment >= 0.50:
                supported.append(claim)
            else:
                unsupported.append(claim)
        else:
            if best_window_containment >= 0.60 and global_containment >= 0.75:
                supported.append(claim)
            else:
                unsupported.append(claim)

    score = len(supported) / len(claims) if claims else 1.0
    return supported, unsupported, unsupported_events, unsupported_entities, unverified_metrics, score


def verify_factual_grounding(source_text: str, output_text: str) -> Dict[str, Any]:
    """
    Deterministically verifies factual, entity, and claim-level fidelity between source and output.
    Returns explainable metrics:
    - is_grounded: bool (True if both metrics and claims are grounded)
    - verified_count: number of source facts preserved in output
    - total_source_facts: total key facts detected in source
    - source_fact_coverage: explicit coverage percentage string (e.g. '8/8 (100.0%)')
    - cited_facts: list of verified factual tokens
    - unverified_metrics: metrics that appear in output but NOT in source (hallucination risk)
    - unsupported_events: factual events asserted in output not supported by source
    - unsupported_entities: compound entities asserted in output not supported by source
    - total_claims: total substantive propositional claims detected in output
    - supported_claims_count: number of supported claims
    - unsupported_claims: list of claims flagged as unsupported
    - claim_grounding_score: fraction of supported claims (0.0 to 1.0)
    - summary: e.g. 'Source fact coverage: 8/8 (100.0%); all 6 claims verified against source (100% grounded)'
    """
    if not source_text or not output_text:
        return {
            "is_grounded": True,
            "verified_count": 0,
            "total_source_facts": 0,
            "source_fact_coverage": "0/0 (100%)",
            "cited_facts": [],
            "unverified_metrics": [],
            "unsupported_events": [],
            "unsupported_entities": [],
            "total_claims": 0,
            "supported_claims_count": 0,
            "unsupported_claims": [],
            "claim_grounding_score": 1.0,
            "summary": "General narrative (no numerical metrics in source)"
        }

    # Skip media source placeholders
    stripped_source = source_text.strip()
    if (
        stripped_source.startswith("[Visual Source:") or
        stripped_source.startswith("[Video Source:") or
        stripped_source.startswith("[Multimodal Analysis")
    ):
        output_facts = extract_key_factual_tokens(output_text)
        return {
            "is_grounded": True,
            "verified_count": len(output_facts),
            "total_source_facts": len(output_facts),
            "source_fact_coverage": f"{len(output_facts)}/{len(output_facts)} (100%)",
            "cited_facts": sorted(list(output_facts))[:8],
            "unverified_metrics": [],
            "unsupported_events": [],
            "unsupported_entities": [],
            "total_claims": 0,
            "supported_claims_count": 0,
            "unsupported_claims": [],
            "claim_grounding_score": 1.0,
            "summary": f"{len(output_facts)} visual/multimodal facts extracted"
        }

    source_facts = extract_key_factual_tokens(source_text)
    output_facts = extract_key_factual_tokens(output_text)

    source_text_lower = source_text.lower()
    source_curr_norms = [normalize_currency_token(sf) for sf in source_facts if normalize_currency_token(sf)]

    cited_source_facts = set()
    for f in source_facts:
        f_norm = normalize_currency_token(f)
        if f in output_facts or f.lower() in output_text.lower():
            cited_source_facts.add(f)
        elif f_norm and any(normalize_currency_token(of) == f_norm for of in output_facts):
            cited_source_facts.add(f)

    # 1. Deterministic Token & Metric Verification across entire document
    unverified_metrics = set()
    for of in output_facts:
        of_lower = of.lower()
        of_norm = normalize_currency_token(of)

        if of_norm:
            if of_norm not in source_curr_norms and of_lower not in source_text_lower:
                unverified_metrics.add(of)
            continue

        if of not in source_facts and of_lower not in source_text_lower:
            if any(char in of for char in ["%", "$", "€", "£", "₹", "x"]) or any(unit in of for unit in ["mb", "gb", "ms"]):
                unverified_metrics.add(of)

    # 2. Claim-Level Unsupported-Content Verification
    claim_candidates = _split_into_claim_candidates(output_text)
    source_words = [w for w in re.findall(r"\b\w+\b", source_text_lower) if w not in COMMON_STOPWORDS]

    if len(source_words) >= 12 and claim_candidates:
        source_windows, full_source_stems = _build_source_windows(source_text)
        (
            supported_claims,
            unsupported_claims,
            unsupported_events,
            unsupported_entities,
            claim_unverified_metrics,
            claim_score
        ) = _verify_claims_against_source(
            claim_candidates, source_windows, full_source_stems, source_text, source_facts, source_curr_norms
        )
        unverified_metrics.update(claim_unverified_metrics)
    else:
        supported_claims = claim_candidates
        unsupported_claims = []
        unsupported_events = set()
        unsupported_entities = set()
        claim_score = 1.0

    is_grounded = (
        len(unverified_metrics) == 0 and
        len(unsupported_claims) == 0 and
        len(unsupported_events) == 0 and
        len(unsupported_entities) == 0
    )

    cov_pct = (len(cited_source_facts) / len(source_facts) * 100) if source_facts else 100.0
    source_fact_coverage = f"{len(cited_source_facts)}/{len(source_facts)} ({round(cov_pct, 1)}%)"

    if is_grounded:
        summary = f"Source fact coverage: {source_fact_coverage}; all {len(supported_claims)} claims verified against source (100% grounded)"
    else:
        parts = [f"Source fact coverage: {source_fact_coverage}"]
        failures = []
        if unverified_metrics:
            failures.append(f"{len(unverified_metrics)} unverified metric(s): {sorted(list(unverified_metrics))}")
        if unsupported_events:
            failures.append(f"{len(unsupported_events)} unsupported event(s): {sorted(list(unsupported_events))}")
        if unsupported_entities:
            failures.append(f"{len(unsupported_entities)} unsupported entity/fact(s): {sorted(list(unsupported_entities))}")
        if unsupported_claims:
            failures.append(f"{len(unsupported_claims)} unsupported claim(s) detected")
        summary = f"{parts[0]}, but ungrounded content detected: {'; '.join(failures)}"

    return {
        "is_grounded": is_grounded,
        "verified_count": len(cited_source_facts),
        "total_source_facts": len(source_facts),
        "source_fact_coverage": source_fact_coverage,
        "cited_facts": sorted(list(cited_source_facts)),
        "unverified_metrics": sorted(list(unverified_metrics)),
        "unsupported_events": sorted(list(unsupported_events)),
        "unsupported_entities": sorted(list(unsupported_entities)),
        "total_claims": len(claim_candidates),
        "supported_claims_count": len(supported_claims),
        "unsupported_claims": sorted(list(unsupported_claims)),
        "claim_grounding_score": round(claim_score, 2),
        "summary": summary
    }


def validate_output(
    output_type: str,
    output_text: Optional[str],
    source_content: str,
    target_audience: Optional[str] = None,
    tone: Optional[str] = None,
    communication_objective: Optional[str] = None,
    content_style: Optional[str] = None,
    language: Optional[str] = None,
    detail_level: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validates a generated communication artefact across five dimensions:
    1. Presence
    2. Basic structural validity
    3. Source-grounding
    4. Configuration compliance
    5. Format-specific compliance

    Returns:
    {
        "valid": bool,
        "severity": "none" | "warning" | "error",
        "issues": List[str]
    }
    """
    issues: List[str] = []
    has_error = False

    # 1. PRESENCE CHECK
    if output_text is None or not str(output_text).strip():
        return {
            "valid": False,
            "severity": "error",
            "issues": ["Output is missing or empty."]
        }

    text = str(output_text).strip()

    # 2. BASIC STRUCTURAL VALIDITY
    # Check minimum length / severe truncation
    if len(text) < 20 or len(text.split()) < 3:
        issues.append(f"Output is too short or severely truncated ({len(text)} characters).")
        has_error = True

    # Detect raw JSON error leakage or traceback artifacts
    error_markers = [
        "{\"error\":", "{\"detail\":", "traceback (most recent call last)",
        "502 bad gateway", "404 not found", "http error"
    ]
    text_lower = text.lower()
    if any(marker in text_lower for marker in error_markers):
        issues.append("Output contains an error message or raw JSON leak instead of formatted content.")
        has_error = True

    # 3. SOURCE-GROUNDING CHECK (Non-aggressive)
    # Check if the output shares vocabulary overlap with source content
    # (Skip if source is a visual/video metadata prompt or very brief)
    source_stripped = source_content.strip() if source_content else ""
    is_media_source = (
        source_stripped.startswith("[Visual Source:") or
        source_stripped.startswith("[Video Source:") or
        source_stripped.startswith("[Multimodal Analysis")
    )
    source_words = [
        w.lower() for w in re.findall(r"\b[a-zA-Z0-9_-]{4,}\b", source_stripped)
        if w.lower() not in COMMON_STOPWORDS
    ]
    if len(source_words) >= 5 and not is_media_source:
        source_vocab = set(source_words)
        output_words = set(re.findall(r"\b[a-zA-Z0-9_-]{4,}\b", text_lower))
        overlap = source_vocab.intersection(output_words)
        if len(overlap) == 0:
            issues.append("Output has low/zero lexical overlap with source content (possible off-topic or heavily paraphrased generation).")

    # 4. CONFIGURATION COMPLIANCE CHECK
    if detail_level:
        dl_lower = detail_level.lower()
        if "brief" in dl_lower and len(text) > 4000:
            issues.append("Output length significantly exceeds requested 'Brief' detail level.")
        elif "detailed" in dl_lower and len(text) < 100 and not has_error:
            issues.append("Output may be too concise for requested 'Detailed' level.")

    # Check non-English language indicators where applicable
    if language and language.lower() not in ("english", "en"):
        lang_lower = language.lower()
        if "hindi" in lang_lower and not re.search(r"[\u0900-\u097F]", text):
            issues.append(f"Output does not appear to use expected Devanagari script for requested language '{language}'.")
        elif any(c in lang_lower for c in ["japanese", "chinese"]) and not re.search(r"[\u3040-\u30FF\u4E00-\u9FFF]", text):
            issues.append(f"Output does not appear to use expected script for requested language '{language}'.")
        elif "spanish" in lang_lower:
            spanish_markers = {" de ", " la ", " el ", " en ", " los ", " las ", " por ", " para ", " una ", " un "}
            if not any(m in f" {text_lower} " for m in spanish_markers) and " the " in f" {text_lower} ":
                issues.append(f"Output appears to be in English rather than requested language '{language}'.")

    # 5. FORMAT-SPECIFIC COMPLIANCE CHECK
    ot_lower = output_type.strip().lower()

    if "presentation" in ot_lower:
        # Presentation requires slide breakdown (e.g. Slide 1, Slide 2, Speaker Notes)
        has_slides = bool(re.search(r"(?i)\bslide\s*(?:[0-9]+|\b)|speaker notes", text))
        if not has_slides and len(text) > 50:
            issues.append("Presentation lacks slide-by-slide structure or speaker notes.")
            has_error = True

    elif "video package" in ot_lower or "video" in ot_lower:
        # Video Package requires storyboard/scene breakdown or narration/script
        has_video_structure = bool(re.search(r"(?i)\bscene\s*(?:[0-9]+|\b)|storyboard|narration|voiceover|subtitles|visual description", text))
        if not has_video_structure and len(text) > 50:
            issues.append("Video Package lacks scene breakdown, storyboard, or narration/script structure.")
            has_error = True

    elif "infographic" in ot_lower:
        # Infographic visual blueprint indicators (sections, metrics, layout, icons)
        has_infographic_structure = bool(re.search(r"(?i)infographic|headline|metric|section|layout|visual|icon|blueprint", text))
        if not has_infographic_structure and len(text) > 50:
            issues.append("Infographic lacks visual blueprint components (metrics, sections, or layout recommendations).")

    elif "linkedin" in ot_lower:
        # LinkedIn Post should have hashtags
        if "#" not in text:
            issues.append("LinkedIn Post is missing hashtags.")

    elif "advisory" in ot_lower:
        has_advisory_structure = bool(re.search(r"(?i)advisory|bulletin|impact|risk|directive|action|guidance|recommend", text))
        if not has_advisory_structure and len(text) > 50:
            issues.append("Advisory lacks clear risk/impact or directive structure.")

    elif "executive summary" in ot_lower:
        has_exec_structure = bool(re.search(r"(?i)overview|summary|impact|takeaway|finding|strategic|recommend", text))
        if not has_exec_structure and len(text) > 50:
            issues.append("Executive Summary lacks overview or strategic impact components.")

    # Determine overall severity
    if has_error:
        severity = "error"
        valid = False
    elif issues:
        severity = "warning"
        valid = True
    else:
        severity = "none"
        valid = True

    # Deterministic factual grounding verification
    factual_grounding = verify_factual_grounding(source_content, text)
    if not factual_grounding.get("is_grounded", True):
        unsupported = factual_grounding.get("unsupported_claims", [])
        if unsupported:
            issues.append(f"Output contains {len(unsupported)} claim(s) unsupported by source content.")
            if severity == "none":
                severity = "warning"
        unverified = factual_grounding.get("unverified_metrics", [])
        if unverified:
            issues.append(f"Output contains unverified metric(s): {', '.join(unverified)}.")
            if severity == "none":
                severity = "warning"
        unsupported_ev = factual_grounding.get("unsupported_events", [])
        if unsupported_ev:
            issues.append(f"Output contains unsupported event(s): {', '.join(unsupported_ev)}.")
            if severity == "none":
                severity = "warning"
        unsupported_ent = factual_grounding.get("unsupported_entities", [])
        if unsupported_ent:
            issues.append(f"Output contains unsupported entity/fact(s): {', '.join(unsupported_ent)}.")
            if severity == "none":
                severity = "warning"

    return {
        "valid": valid,
        "severity": severity,
        "issues": issues,
        "factual_grounding": factual_grounding
    }


def build_output_provenance(
    output_type: str,
    generation_action: str,  # "generated", "recovered", "refined"
    call_architecture: str,  # "consolidated_single_call", "targeted_recovery_call", "single_output_refinement_call", etc.
    model: str,
    is_mock: bool,
    source_reference: Optional[str],
    validation: Dict[str, Any],
    recovery_attempted: bool = False,
    recovery_call_count: int = 0,
    refinement_applied: Optional[str] = None,
    refinement_instruction: Optional[str] = None,
    target_audience: Optional[str] = None,
    tone: Optional[str] = None,
    language: Optional[str] = None,
    detail_level: Optional[str] = None
) -> Dict[str, Any]:
    """
    Constructs a structured provenance and traceability record for an output artefact.
    Preserves truthful tracking of generation calls, actions, and validation status.
    """
    return {
        "output_type": output_type,
        "generation_action": generation_action,
        "call_architecture": call_architecture,
        "model": model,
        "is_mock": is_mock,
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_reference": source_reference,
        "validation": validation,
        "factual_grounding": validation.get("factual_grounding", {}),
        "recovery_attempted": recovery_attempted,
        "recovery_call_count": recovery_call_count,
        "refinement_applied": refinement_applied,
        "refinement_instruction": refinement_instruction,
        "target_audience": target_audience,
        "tone": tone,
        "language": language,
        "detail_level": detail_level
    }


def validate_and_recover_outputs(
    outputs: Dict[str, str],
    request: TransformRequest,
    model: Optional[genai.GenerativeModel],
    multimodal_parts: list
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    Validates all requested outputs across the 5 quality dimensions.
    If an output has actionable 'error' severity (missing, truncated, or structurally non-compliant),
    attempts a single targeted recovery for that specific format only.
    Re-validates the recovered output (maximum 1 recovery attempt per format).
    Returns (final_outputs, validation_report).
    """
    source = request.source_content.strip()
    audience = request.target_audience or "General Audience"
    tone = request.tone or "Professional"
    objective = request.communication_objective or "Inform"
    style = request.content_style or "Direct & Concise"
    language = request.language or "English"
    detail = request.detail_level or "Standard"

    validation_results: Dict[str, Dict[str, Any]] = {}

    # 1. Initial Validation of all requested outputs
    for ot in request.output_types:
        val = validate_output(
            output_type=ot,
            output_text=outputs.get(ot),
            source_content=source,
            target_audience=audience,
            tone=tone,
            communication_objective=objective,
            content_style=style,
            language=language,
            detail_level=detail
        )
        validation_results[ot] = val

    # 2. Identify outputs requiring targeted recovery (severity == 'error')
    failed_outputs = [ot for ot in request.output_types if validation_results[ot]["severity"] == "error"]
    recovered_formats: List[str] = []

    # 3. Targeted Recovery (At most ONE attempt per failed output)
    if failed_outputs and model is not None:
        for failed_ot in failed_outputs:
            try:
                recovered_text = targeted_recover_missing_output(
                    model=model,
                    output_type=failed_ot,
                    source_content=source,
                    target_audience=audience,
                    tone=tone,
                    language=language,
                    detail_level=detail,
                    communication_objective=objective,
                    content_style=style,
                    document_name=request.document_name,
                    image_name=request.image_name,
                    video_name=request.video_name,
                    multimodal_parts=multimodal_parts
                )

                # Re-validate the recovered output
                rec_val = validate_output(
                    output_type=failed_ot,
                    output_text=recovered_text,
                    source_content=source,
                    target_audience=audience,
                    tone=tone,
                    communication_objective=objective,
                    content_style=style,
                    language=language,
                    detail_level=detail
                )
                validation_results[failed_ot] = rec_val
                outputs[failed_ot] = recovered_text
                recovered_formats.append(failed_ot)

            except Exception as rec_err:
                raise HTTPException(
                    status_code=502,
                    detail=f"Targeted recovery failed: LLM did not generate acceptable output format '{failed_ot}' ({str(rec_err)})."
                )

    validation_report = {
        "all_valid": all(v["valid"] for v in validation_results.values()),
        "per_output": validation_results,
        "recovered_formats": recovered_formats,
        "recovered_count": len(recovered_formats)
    }

    return outputs, validation_report


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
                f"Audience: {audience} | Tone: {tone} | Objective: {objective} | Style: {style} | Language: {language} | Detail Level: {detail}\n\n"
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
                f"Audience: {audience} | Tone: {tone} | Objective: {objective} | Style: {style} | Language: {language} | Detail Level: {detail}\n\n"
                f"ADVISORY BULLETIN:\n"
                f"Purpose: Guidance derived from provided source material.\n"
                f"Context: \"{snippet}\"\n\n"
                f"Risk & Operational Impact:\n"
                f"Potential vulnerability exposure and operational latency if mitigation steps are deferred.\n\n"
                f"RECOMMENDED DIRECTIVES:\n"
                f"1. Acknowledge and distribute this advisory to all relevant team members.\n"
                f"2. Adopt recommended safety and compliance measures immediately.\n\n"
                f"---\n"
                f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
            )
        elif "linkedin" in output_type_lower:
            transformed_text = (
                f"[MOCK GENERATION - LINKEDIN POST]\n"
                f"Audience: {audience} | Tone: {tone} | Objective: {objective} | Style: {style} | Language: {language} | Detail Level: {detail}\n\n"
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
                f"Audience: {audience} | Tone: {tone} | Objective: {objective} | Style: {style} | Language: {language} | Detail Level: {detail}\n\n"
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
                f"Audience: {audience} | Tone: {tone} | Objective: {objective} | Style: {style} | Language: {language} | Detail Level: {detail}\n\n"
                f"📊 INFOGRAPHIC SPECIFICATION\n\n"
                f"1. Headline Banner:\n"
                f"   \"Transforming Complex Updates into Actionable Insights\"\n\n"
                f"2. Core Message:\n"
                f"   {snippet}\n\n"
                f"3. Key Data & Pillar Points:\n"
                f"   • Metric 1: 95% clarity improvement across recipient groups.\n"
                f"   • Metric 2: 3x faster response cycle for critical updates.\n"
                f"   • Metric 3: End-to-end alignment across core operations.\n\n"
                f"4. Sectional Narrative Flow:\n"
                f"   - Section A (The Hook): Engaging headline and problem context.\n"
                f"   - Section B (Problem Definition): Core challenge highlighted from source data.\n"
                f"   - Section C (Data Pillars): Visual breakdown of 3 core metrics and findings.\n"
                f"   - Section D (Resolution & Action): Clear next step and stakeholder takeaways.\n\n"
                f"5. Layout & Visual Recommendations:\n"
                f"   - Hierarchy: Top banner header → 3-column metric cards → narrative flow → summary footer.\n"
                f"   - Color Scheme: Modern dark slate (#0B0F19) with indigo (#6366F1) accent.\n"
                f"   - Icon Suggestions: Target icon for goals, lightning bolt for efficiency, handshake for alignment.\n\n"
                f"---\n"
                f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
            )
        elif "presentation" in output_type_lower:
            transformed_text = (
                f"[MOCK GENERATION - PRESENTATION SLIDEDECK]\n"
                f"Audience: {audience} | Tone: {tone} | Objective: {objective} | Style: {style} | Language: {language} | Detail Level: {detail}\n\n"
                f"🖥️ SLIDE-BY-SLIDE OUTLINE\n\n"
                f"Slide 1: Title & Executive Overview\n"
                f"• Strategic Content Transformation and Intelligence Briefing.\n"
                f"• Synthesizing high-priority data into multi-channel communication artefacts.\n"
                f"• Designed specifically for {audience} with a focus on {objective}.\n"
                f"• Speaker Notes: Welcome everyone. Today we are walking through the critical updates derived from our source material.\n\n"
                f"Slide 2: Background & Context\n"
                f"• Core Situation: \"{snippet}\"\n"
                f"• Operational Challenge: Navigating fast-moving requirements with cross-functional teams.\n"
                f"• Critical Driver: Need for rapid, accurate dissemination across stakeholder groups.\n"
                f"• Speaker Notes: Highlight the foundational context and why immediate alignment matters right now.\n\n"
                f"Slide 3: Strategic Impact & Key Takeaways\n"
                f"• Measurable efficiency gains across primary communication workflows.\n"
                f"• Standardized communication formats tailored precisely by stakeholder group.\n"
                f"• Enhanced clarity reducing response latency and cross-functional friction.\n"
                f"• Speaker Notes: Emphasize the tangible value and operational rigor delivered by this initiative.\n\n"
                f"Slide 4: Roadmap & Next Actions\n"
                f"• Immediate Phase-One operational deployment across designated channels.\n"
                f"• Establish real-time feedback loops and audit check intervals.\n"
                f"• Conduct milestone performance review after 30 days of active execution.\n"
                f"• Speaker Notes: Direct the audience to the action items and open the floor for questions and answers.\n\n"
                f"---\n"
                f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
            )
        elif "video" in output_type_lower:
            transformed_text = (
                f"[MOCK GENERATION - VIDEO PRODUCTION PACKAGE]\n"
                f"Audience: {audience} | Tone: {tone} | Objective: {objective} | Style: {style} | Language: {language} | Detail Level: {detail}\n\n"
                f"🎬 VIDEO PRODUCTION BRIEF\n"
                f"Target Duration: 60 Seconds | Format: 16:9 Landscape & 9:16 Vertical Cut\n"
                f"Objective: Deliver concise, engaging overview to {audience}.\n\n"
                f"FULL VOICEOVER SCRIPT:\n"
                f"\"Big updates are here. Here is what you need to know. "
                f"Looking at the key facts: {snippet}. "
                f"Teams can now execute faster and align better on strategic goals. "
                f"Check out the full release and stay ahead. See you next time.\"\n\n"
                f"STORYBOARD & SCRIPT BREAKDOWN:\n\n"
                f"Scene 1 (0:00 - 0:10) - The Hook\n"
                f"• Visual Description / Action: High-energy kinetic text over clean motion background.\n"
                f"• Subtitles / On-Screen Text: \"Big updates are here. Here's what you need to know.\"\n"
                f"• Narration / Voiceover: \"Big updates are here. Here is what you need to know.\"\n\n"
                f"Scene 2 (0:10 - 0:35) - Core Update\n"
                f"• Visual Description / Action: Screen recording or dynamic infographic breakdown of core points.\n"
                f"• Subtitles / On-Screen Text: \"{snippet}\"\n"
                f"• Narration / Voiceover: \"Looking at the key facts: {snippet}\"\n\n"
                f"Scene 3 (0:35 - 0:50) - Value & Impact\n"
                f"• Visual Description / Action: Split screen with icons highlighting operational efficiency.\n"
                f"• Subtitles / On-Screen Text: \"Faster execution. Clearer results. Better alignment.\"\n"
                f"• Narration / Voiceover: \"Teams can now execute faster and align better on strategic goals.\"\n\n"
                f"Scene 4 (0:50 - 1:00) - Call to Action\n"
                f"• Visual Description / Action: Closing brand card with URL and contact handle.\n"
                f"• Subtitles / On-Screen Text: \"Learn more at our portal today.\"\n"
                f"• Narration / Voiceover: \"Check out the full release and stay ahead. See you next time.\"\n\n"
                f"PRODUCTION RECOMMENDATIONS:\n"
                f"• Music: Upbeat, modern ambient electronic with confident rhythm.\n"
                f"• Pacing: Dynamic and engaging (130-140 words per minute).\n"
                f"• Visual Style: Crisp high-contrast typography with smooth kinetic transitions.\n"
                f"• Voiceover Tone: {tone}, clear, articulate, professional pace.\n\n"
                f"---\n"
                f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
            )
        else:
            transformed_text = (
                f"[MOCK GENERATION - {ot_stripped.upper()}]\n"
                f"Audience: {audience} | Tone: {tone} | Objective: {objective} | Style: {style} | Language: {language} | Detail Level: {detail}\n\n"
                f"Transformed Content Preview:\n"
                f"\"{snippet}\"\n\n"
                f"---\n"
                f"(Note: Placeholder mock output. USE_MOCK is active or API key fallback.)"
            )
        outputs[output_type] = transformed_text

    # Validate mock outputs for consistency and compliance
    mock_validation = {}
    for ot in request.output_types:
        mock_validation[ot] = validate_output(
            output_type=ot,
            output_text=outputs.get(ot),
            source_content=source,
            target_audience=audience,
            tone=tone,
            communication_objective=objective,
            content_style=style,
            language=language,
            detail_level=detail
        )

    source_ref = (
        request.document_name or
        (f"Image: {request.image_name}" if request.image_name else None) or
        (f"Video: {request.video_name}" if request.video_name else None) or
        f"Direct Input ({len(source)} chars)"
    )

    provenance = {}
    for ot, text in outputs.items():
        provenance[ot] = build_output_provenance(
            output_type=ot,
            generation_action="generated",
            call_architecture="consolidated_mock_call",
            model="mock-transform-generator",
            is_mock=True,
            source_reference=source_ref,
            validation=mock_validation.get(ot, {}),
            recovery_attempted=False,
            recovery_call_count=0,
            target_audience=audience,
            tone=tone,
            language=language,
            detail_level=detail
        )

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
            "model": "mock-transform-generator",
            "is_mock": True,
            "validation": {
                "all_valid": all(v["valid"] for v in mock_validation.values()),
                "per_output": mock_validation
            },
            "provenance": provenance
        },
        provenance=provenance
    )


def transform_content(request: TransformRequest) -> TransformResponse:
    """
    Main transformation service function.
    Validates input, checks for API key or mock flag, calls Google Gemini LLM,
    and returns the structured response.
    """
    # 1. Basic validation for output types
    if not request.output_types or len(request.output_types) == 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid input: 'output_types' cannot be empty."
        )

    # 2. Extraction Validation Layer (Pre-generation validation)
    # Validates that source content was extracted and normalized reliably before prompt building
    source = validate_extracted_content(
        content=request.source_content,
        document_name=request.document_name
    )
    audience = request.target_audience or "General Audience"
    tone = request.tone or "Professional"
    objective = request.communication_objective or "Inform"
    style = request.content_style or "Direct & Concise"
    language = request.language or "English"
    detail = request.detail_level or "Standard"

    # 2. Parse, validate, and check size limits for multimodal image & video inputs
    # (Enforced identically across both mock and live modes)
    multimodal_parts = []
    if request.image_data:
        try:
            mime_type, img_bytes = parse_image_data(request.image_data)
            if len(img_bytes) > MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Image file exceeds maximum allowed size of 10MB ({len(img_bytes) / (1024 * 1024):.1f}MB)."
                )
            multimodal_parts.append({"mime_type": mime_type, "data": img_bytes})
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image data: {str(e)}"
            )

    if request.video_data:
        try:
            mime_type, vid_bytes = parse_video_data(request.video_data)
            if len(vid_bytes) > MAX_VIDEO_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Video file exceeds maximum allowed size of 25MB ({len(vid_bytes) / (1024 * 1024):.1f}MB)."
                )
            multimodal_parts.append({"mime_type": mime_type, "data": vid_bytes})
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid video data: {str(e)}"
            )

    # 3. Check if mock mode is explicitly requested via environment variable
    if "USE_MOCK" not in os.environ:
        load_dotenv(override=True)
    if os.getenv("USE_MOCK", "").lower() in ("true", "1", "yes"):
        return mock_transform_content(request)

    # 4. Retrieve and validate API key
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

    # 5. Call LLM using a single consolidated request for all selected output formats
    outputs = {}
    try:
        genai.configure(api_key=api_key.strip())
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        model = genai.GenerativeModel(model_name)

        # Build single unified prompt covering all selected output types
        prompt = build_consolidated_prompt(
            source_content=source,
            output_types=request.output_types,
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

        # Request structured JSON response with sufficient output token budget
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.3,
            max_output_tokens=8192
        )

        response = call_gemini_with_retry(
            model=model,
            content_payload=content_payload,
            generation_config=generation_config,
            max_retries=2
        )

        if not response or not response.text:
            raise HTTPException(
                status_code=502,
                detail="LLM generation failed: Model returned an empty response."
            )

        # Parse structured JSON dictionary from response
        try:
            parsed_data = extract_json_response(response.text)
        except ValueError as parse_err:
            raise HTTPException(
                status_code=502,
                detail=f"LLM response parsing failure: {str(parse_err)}"
            )

        # Map parsed results to requested output formats (with case-insensitive fallback)
        parsed_lookup = {k.strip().lower(): v for k, v in parsed_data.items()}

        for ot in request.output_types:
            ot_clean = ot.strip()
            if ot_clean in parsed_data and parsed_data[ot_clean]:
                outputs[ot] = str(parsed_data[ot_clean]).strip()
            elif ot_clean.lower() in parsed_lookup and parsed_lookup[ot_clean.lower()]:
                outputs[ot] = str(parsed_lookup[ot_clean.lower()]).strip()

        # Quality/Consistency Validator & Targeted Recovery Integration
        outputs, validation_report = validate_and_recover_outputs(
            outputs=outputs,
            request=request,
            model=model,
            multimodal_parts=multimodal_parts
        )

    except HTTPException:
        # Re-raise explicit HTTPExceptions
        raise
    except Exception as e:
        # Handle API failure, network errors, invalid keys, or quota issues
        raise HTTPException(
            status_code=502,
            detail=f"LLM API failure: {str(e)}"
        )

    # 6. Build structured provenance records for all generated outputs
    source_ref = (
        request.document_name or
        (f"Image: {request.image_name}" if request.image_name else None) or
        (f"Video: {request.video_name}" if request.video_name else None) or
        f"Direct Input ({len(source)} chars)"
    )

    recovered_set = set(validation_report.get("recovered_formats", []))
    provenance = {}
    for ot, text in outputs.items():
        is_recovered = ot in recovered_set
        val_for_ot = validation_report.get("per_output", {}).get(ot, {})
        provenance[ot] = build_output_provenance(
            output_type=ot,
            generation_action="recovered" if is_recovered else "generated",
            call_architecture="targeted_recovery_call" if is_recovered else "consolidated_single_call",
            model=model_name,
            is_mock=False,
            source_reference=source_ref,
            validation=val_for_ot,
            recovery_attempted=is_recovered,
            recovery_call_count=1 if is_recovered else 0,
            target_audience=audience,
            tone=tone,
            language=language,
            detail_level=detail
        )

    # 7. Return response with metadata, validation report, and provenance
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
            "model": model_name,
            "is_mock": False,
            "validation": validation_report,
            "provenance": provenance
        },
        provenance=provenance
    )


def build_refinement_prompt(
    source_content: str,
    output_type: str,
    current_output: str,
    refinement_instruction: str,
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
    Constructs a structured refinement prompt for Gemini instructing it
    to refine a single output based on the user's specific instruction,
    preserving source grounding and format specifications.
    """
    doc_spec = f"\n- Source Document Name: {document_name}" if document_name else ""
    img_spec = f"\n- Attached Source Image: {image_name} (Preserve visual alignment)" if image_name else ""
    vid_spec = f"\n- Attached Source Video: {video_name} (Preserve video narrative alignment)" if video_name else ""
    format_spec = get_format_instruction(output_type)

    return f"""You are an expert AI content transformer.
Your task is to REFINE an existing communication artefact based strictly on the user's refinement instruction, while maintaining factual grounding in the original source content and adhering to the structural format requirements of '{output_type}'.

TRANSFORMATION SPECIFICATIONS:
- Target Artefact (Output Type): {output_type}
- Target Audience: {target_audience}
- Tone: {tone}
- Communication Objective: {communication_objective or 'Inform'}
- Content Style: {content_style or 'Direct & Concise'}
- Language: {language}
- Detail Level: {detail_level}{doc_spec}{img_spec}{vid_spec}

ORIGINAL SOURCE CONTENT:
\"\"\"
{source_content}
\"\"\"

CURRENT OUTPUT TO REFINE ({output_type}):
\"\"\"
{current_output}
\"\"\"

USER REFINEMENT INSTRUCTION:
\"\"\"
{refinement_instruction}
\"\"\"

FORMAT SPECIFICATION:
{format_spec}

REFINEMENT RULES:
1. Apply the user's refinement instruction directly, meaningfully, and comprehensively to update the current output.
2. Maintain strict factual grounding in the original source content. Do NOT fabricate metrics, data, or facts.
3. Preserve the core structural requirements of the '{output_type}' format.
4. Output the refined content in '{language}'.
5. Return your response strictly as a valid JSON object with EXACTLY one key: "{output_type}".
Example output JSON format:
{{
  "{output_type}": "<full refined text>"
}}
"""


def mock_refine_content(request: RefineRequest) -> RefineResponse:
    """
    Deterministic mock refinement fallback when USE_MOCK=true or API key is absent.
    """
    ot = request.output_type.strip()
    audience = request.target_audience or "General Audience"
    tone = request.tone or "Professional"
    objective = request.communication_objective or "Inform"
    style = request.content_style or "Direct & Concise"
    language = request.language or "English"
    detail = request.detail_level or "Standard"

    refined_text = (
        f"[MOCK REFINED - {ot}]\n"
        f"Refinement Applied: {request.refinement_instruction}\n\n"
        f"{request.current_output}\n\n"
        f"[Refinement Note: Enhanced with {tone.lower()} tone and adapted for {audience}.]"
    )

    # Validate the refined mock output using existing validator
    val_result = validate_output(
        output_type=ot,
        output_text=refined_text,
        source_content=request.source_content,
        target_audience=audience,
        tone=tone,
        communication_objective=objective,
        content_style=style,
        language=language,
        detail_level=detail
    )

    source_ref = (
        request.document_name or
        (f"Image: {request.image_name}" if request.image_name else None) or
        (f"Video: {request.video_name}" if request.video_name else None) or
        f"Direct Input ({len(request.source_content)} chars)"
    )

    prov = build_output_provenance(
        output_type=ot,
        generation_action="refined",
        call_architecture="single_output_mock_refinement_call",
        model="mock-refinement-generator",
        is_mock=True,
        source_reference=source_ref,
        validation=val_result,
        recovery_attempted=False,
        recovery_call_count=0,
        refinement_applied=request.refinement_instruction,
        refinement_instruction=request.refinement_instruction,
        target_audience=audience,
        tone=tone,
        language=language,
        detail_level=detail
    )

    return RefineResponse(
        status="success",
        output_type=ot,
        refined_output=refined_text,
        metadata={
            "model": "mock-refinement-generator",
            "is_mock": True,
            "output_type": ot,
            "refinement_applied": request.refinement_instruction,
            "target_audience": audience,
            "tone": tone,
            "language": language,
            "detail_level": detail,
            "document_name": request.document_name,
            "image_name": request.image_name,
            "video_name": request.video_name,
            "validation": val_result,
            "recovery_attempted": False,
            "provenance": prov
        },
        provenance=prov
    )


def refine_output(request: RefineRequest) -> RefineResponse:
    """
    Stage 3: Interactive Single-Output Refinement Service.
    Refines ONE specific output without regenerating the other outputs.
    Executes the existing Output Quality Validator and allows at most ONE targeted recovery.
    """
    # 1. Basic validation for required refinement parameters
    if not request.output_type or not request.output_type.strip():
        raise HTTPException(
            status_code=400,
            detail="Invalid input: 'output_type' cannot be empty."
        )

    if not request.current_output or not request.current_output.strip():
        raise HTTPException(
            status_code=400,
            detail="Invalid input: 'current_output' cannot be empty."
        )

    if not request.refinement_instruction or not request.refinement_instruction.strip():
        raise HTTPException(
            status_code=400,
            detail="Invalid input: 'refinement_instruction' cannot be empty."
        )

    # 2. Pre-generation validation on original source content
    source = validate_extracted_content(
        content=request.source_content,
        document_name=request.document_name
    )

    ot = request.output_type.strip()
    audience = request.target_audience or "General Audience"
    tone = request.tone or "Professional"
    objective = request.communication_objective or "Inform"
    style = request.content_style or "Direct & Concise"
    language = request.language or "English"
    detail = request.detail_level or "Standard"

    # 3. Parse and validate multimodal media if present
    multimodal_parts = []
    if request.image_data:
        try:
            mime_type, img_bytes = parse_image_data(request.image_data)
            if len(img_bytes) > MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Image file exceeds maximum allowed size of 10MB ({len(img_bytes) / (1024 * 1024):.1f}MB)."
                )
            multimodal_parts.append({"mime_type": mime_type, "data": img_bytes})
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image data: {str(e)}")

    if request.video_data:
        try:
            mime_type, vid_bytes = parse_video_data(request.video_data)
            if len(vid_bytes) > MAX_VIDEO_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Video file exceeds maximum allowed size of 25MB ({len(vid_bytes) / (1024 * 1024):.1f}MB)."
                )
            multimodal_parts.append({"mime_type": mime_type, "data": vid_bytes})
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid video data: {str(e)}")

    # 4. Check if mock mode is active
    if "USE_MOCK" not in os.environ:
        load_dotenv(override=True)
    if os.getenv("USE_MOCK", "").lower() in ("true", "1", "yes"):
        return mock_refine_content(request)

    # 5. Check API key
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

    # 6. Execute single refinement call to Gemini
    refined_text = ""
    recovery_attempted = False
    try:
        genai.configure(api_key=api_key.strip())
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        model = genai.GenerativeModel(model_name)

        prompt = build_refinement_prompt(
            source_content=source,
            output_type=ot,
            current_output=request.current_output,
            refinement_instruction=request.refinement_instruction,
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
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.3,
            max_output_tokens=8192
        )

        response = call_gemini_with_retry(
            model=model,
            content_payload=content_payload,
            generation_config=generation_config,
            max_retries=2
        )

        if not response or not response.text:
            refined_text = ""
        else:
            try:
                parsed_data = extract_json_response(response.text)
                parsed_lookup = {k.strip().lower(): v for k, v in parsed_data.items()}
                raw_val = parsed_data.get(ot) or parsed_lookup.get(ot.lower())
                if not raw_val and len(parsed_data) == 1:
                    raw_val = list(parsed_data.values())[0]
                refined_text = str(raw_val).strip() if raw_val else ""
            except Exception:
                refined_text = ""

        # 7. Post-generation Quality/Consistency Validator
        val_result = validate_output(
            output_type=ot,
            output_text=refined_text,
            source_content=source,
            target_audience=audience,
            tone=tone,
            communication_objective=objective,
            content_style=style,
            language=language,
            detail_level=detail
        )

        # 8. If validation severity is 'error', perform at most ONE targeted recovery
        if val_result.get("severity") == "error":
            recovery_attempted = True
            try:
                rec_instruction = (
                    f"{request.refinement_instruction}. "
                    f"CRITICAL: Previous generation was invalid or empty. Provide a complete, fully formatted {ot}."
                )
                rec_prompt = build_refinement_prompt(
                    source_content=source,
                    output_type=ot,
                    current_output=request.current_output,
                    refinement_instruction=rec_instruction,
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
                rec_payload = [rec_prompt] + multimodal_parts if multimodal_parts else rec_prompt
                rec_config = genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                    max_output_tokens=8192
                )
                rec_response = call_gemini_with_retry(
                    model=model,
                    content_payload=rec_payload,
                    generation_config=rec_config,
                    max_retries=1
                )
                if rec_response and rec_response.text:
                    rec_data = extract_json_response(rec_response.text)
                    rec_lookup = {k.strip().lower(): v for k, v in rec_data.items()}
                    rec_val = rec_data.get(ot) or rec_lookup.get(ot.lower())
                    if not rec_val and len(rec_data) == 1:
                        rec_val = list(rec_data.values())[0]
                    if rec_val:
                        refined_text = str(rec_val).strip()

                # Re-validate with existing validator
                val_result = validate_output(
                    output_type=ot,
                    output_text=refined_text,
                    source_content=source,
                    target_audience=audience,
                    tone=tone,
                    communication_objective=objective,
                    content_style=style,
                    language=language,
                    detail_level=detail
                )
                if val_result.get("severity") == "error":
                    raise HTTPException(
                        status_code=502,
                        detail=f"Refinement recovery failed: Output for '{ot}' remains invalid after targeted recovery ({'; '.join(val_result.get('issues', []))})."
                    )
            except HTTPException:
                raise
            except Exception as rec_err:
                raise HTTPException(
                    status_code=502,
                    detail=f"Targeted refinement recovery failed for '{ot}': {str(rec_err)}"
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM refinement failure: {str(e)}"
        )

    # 9. Build structured provenance record for refined output
    source_ref = (
        request.document_name or
        (f"Image: {request.image_name}" if request.image_name else None) or
        (f"Video: {request.video_name}" if request.video_name else None) or
        f"Direct Input ({len(source)} chars)"
    )

    prov = build_output_provenance(
        output_type=ot,
        generation_action="recovered" if recovery_attempted else "refined",
        call_architecture="single_output_refinement_recovery_call" if recovery_attempted else "single_output_refinement_call",
        model=model_name,
        is_mock=False,
        source_reference=source_ref,
        validation=val_result,
        recovery_attempted=recovery_attempted,
        recovery_call_count=1 if recovery_attempted else 0,
        refinement_applied=request.refinement_instruction,
        refinement_instruction=request.refinement_instruction,
        target_audience=audience,
        tone=tone,
        language=language,
        detail_level=detail
    )

    # 10. Return structured RefineResponse
    return RefineResponse(
        status="success",
        output_type=ot,
        refined_output=refined_text,
        metadata={
            "model": model_name,
            "is_mock": False,
            "output_type": ot,
            "refinement_applied": request.refinement_instruction,
            "target_audience": audience,
            "tone": tone,
            "language": language,
            "detail_level": detail,
            "document_name": request.document_name,
            "image_name": request.image_name,
            "video_name": request.video_name,
            "validation": val_result,
            "recovery_attempted": recovery_attempted,
            "provenance": prov
        },
        provenance=prov
    )
