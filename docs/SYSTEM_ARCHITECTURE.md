# SYSTEM ARCHITECTURE DOCUMENT
## AI Content Transformer — Enterprise Multimodal Content Synthesis & Factual Grounding Platform
**Smart India Hackathon (SIH) Technical Submission | Formal System Architecture Specification**

---

# [PAGE 1] System Overview & Core Architecture

### 1. Executive Summary & Problem Formulation
The **AI Content Transformer** is a modular monolithic system designed to resolve information asymmetry and communication bottlenecks in multi-stakeholder enterprise environments. Complex raw material—such as technical incident reports, compliance filings, or multimedia debriefs—must typically be tailored for disparate audiences (e.g., C-Suite, engineering teams, compliance auditors, and external public channels). Traditional generative workflows suffer from **factual drift, inconsistent cross-format metrics, hallucinated qualitative extrapolation, and excessive token/latency overhead** caused by repeated, uncoordinated LLM calls. 

This platform resolves these challenges by introducing an upstream **Canonical Content Model (CCM)**, executing **Consolidated Single-Pass Generation** via Google Gemini (`gemini-3.5-flash-lite`), and enforcing downstream **Deterministic Factual Grounding & Targeted Self-Healing** without relying on secondary nondeterministic LLM judges.

---

### 2. High-Level Architecture Diagram

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               PRESENTATION / CLIENT LAYER                              │
│  React 18 + Vite SPA · 5-Stage Transformation Workflow · State-Isolated UI             │
│  Visualizers: Slide Deck Carousel · KPI Card Layout · 3-Column Video Storyboard        │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ HTTP / REST (JSON & Multipart)
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               API & GATEWAY LAYER (FastAPI)                            │
│  Starlette Middleware: 35 MB Request Body Protection · 60 req/min IP Rate Limiter      │
│  Configurable CORS · Pydantic v2 Contracts (TransformRequest, RefineRequest)           │
└───────────────────────┬────────────────────────────────────────┬───────────────────────┘
                        ▼                                        ▼
┌──────────────────────────────────────────────┐  ┌──────────────────────────────────────┐
│        INPUT / DOCUMENT PROCESSING           │  │       CANONICAL CONTENT MODEL        │
│  - Text, Markdown, PDF (pypdf), DOCX (docx)  │  │  - Atomic Claims & Key Messages      │
│  - Image/Video MIME & Base64 Data URI parser │  │  - Quantifiable Metrics & Dates      │
│  - Pre-flight binary sanitization            │  │  - Entities, Events & Certifications │
└───────────────────────┬──────────────────────┘  └──────────────────┬───────────────────┘
                        │                                            │
                        └──────────────────────┬─────────────────────┘
                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        CONSOLIDATED GENERATION ENGINE (Gemini)                         │
│  Unified Structured Prompt · Gemini 3.5 Flash Lite (Temp=0.3, MaxTokens=8192)          │
│  Consolidated Single-Pass Generation → Simultaneous Extraction of up to 7 Formats      │
└──────────────────────────────────────────────┬─────────────────────────────────────────┘
                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                       DETERMINISTIC FACTUAL GROUNDING ENGINE                           │
│  Multi-Scale Source Windows (Sentence + Paragraph) · Morphological Stemming Engine     │
│  Normalized Metric & Currency Evaluator · Factual Event & Compound Entity Validator    │
│  Structural Scaffolding Exclusion · Contradiction Matrix · Composite Quality Gate      │
└───────────────────────┬────────────────────────────────────────┬───────────────────────┘
                        │ Gate Passed (Score >= 0.80)            │ Gate Failed / Unsafe Claim
                        ▼                                        ▼
┌──────────────────────────────────────────────┐  ┌──────────────────────────────────────┐
│        PROVENANCE REGISTRY & RESULTS         │  │     TARGETED SELF-HEALING LOOP       │
│  - Per-format claim coverage & verification  │  │  - Isolates ONLY failing format      │
│  - Explainable quality score vector          │  │  - Injects negative feedback prompt  │
│  - JSON / Markdown bundle export             │  │  - Single targeted regeneration call │
└──────────────────────────────────────────────┘  └──────────────────┬───────────────────┘
                        ▲                                            │ Re-validated
                        └────────────────────────────────────────────┘
```

---

### 3. Major Architectural Subsystems

1. **Presentation Layer (React 18 + Vite):** A lightweight client orchestrating a 5-stage sequential workflow (`Source` $\rightarrow$ `Configure` $\rightarrow$ `Generate` $\rightarrow$ `Validate` $\rightarrow$ `Results`). Manages domain visualizers (Slide carousel with speaker notes, KPI cards, Video scene storyboard) and provides isolated in-place refinement controls.
2. **API & Gateway Layer (FastAPI on Uvicorn):** Modular monolithic ASGI gateway providing strict schema enforcement via Pydantic v2, streaming request body size protection (35 MB), in-memory sliding-window rate limiting (60 req/min), and configurable CORS isolation.
3. **Ingestion & Document Processing Layer:** Processes documents entirely in-memory using `pypdf` and `python-docx`. Performs multi-step pre-generation sanitization: rejecting null bytes (`\x00`), Unicode decoding corruption (`\ufffd`), unprintable control characters, repetitive character spam, and binary garbage.
4. **Core AI & Grounding Engine (`transform_service.py`):** Coordinates upstream Canonical Content Model extraction, single-pass consolidated prompt compilation, Gemini API invocation with exponential backoff, deterministic factual verification, quality gate enforcement, and targeted self-healing.

---

### 4. End-to-End Data Pipeline

The end-to-end transformation lifecycle executes in 7 linear phases:
- **Phase 1: Input Ingestion & Sanitization:** Source text or files are received via `POST /extract-text` or `POST /transform`. Extracted text is checked against deterministic viability rules (minimum viable length, character encoding integrity).
- **Phase 2: Upstream Factual Canonicalization:** The backend constructs a `CanonicalContentModel` capturing verifiable source ground truth before LLM invocation.
- **Phase 3: Consolidated AI Synthesis:** A single unified prompt containing the canonical ground truth and format-specific blueprints is submitted to Google Gemini (`gemini-3.5-flash-lite`), returning all requested formats in a single structured JSON payload.
- **Phase 4: Output Decomposition & Structural Validation:** Raw JSON is parsed, mapped to requested formats, and checked for mandatory structural markers (e.g., slide markers, scene divisions, hashtags).
- **Phase 5: Factual Grounding & Cross-Format Auditing:** Output claims are extracted and checked against multi-scale source windows, normalized metrics, events, and entities. Cross-format facts are cross-referenced to eliminate contradictions.
- **Phase 6: Quality Gate & Targeted Self-Healing:** Outputs meeting quality thresholds ($\ge 0.80$) pass directly. Failing formats trigger an isolated negative-constraint recovery call.
- **Phase 7: Provenance Compilation & Delivery:** Formats are bound with claim-level audit metadata, displayed via interactive visualizers, and made available for selective refinement or bundle export.

---

### 5. Canonical Content Model (CCM)

The Canonical Content Model is defined as a Pydantic schema (`CanonicalContentModel`) representing the reference ground truth extracted from source material before generation:
- **`source_reference` & `source_text`:** Preserves origin metadata (filename or character count) and full verbatim text for audit traceability.
- **`claims`:** Atomic propositional assertions split along sentence boundaries.
- **`metrics`:** Normalized quantitative values (percentages, multipliers, data rates, measured physical units).
- **`dates`:** Temporal anchors (quarters like `Q1 2026`, calendar dates, ISO formats, standalone years).
- **`entities`:** Compound enterprise nouns and platform identifiers extracted via regex patterns.
- **`events`:** Factual milestones (acquisitions, certifications, deployments, launches) identified via `FACTUAL_EVENT_PATTERNS`.
- **`standards_and_certifications`:** Explicit compliance frameworks (`SOC 2 Type II`, `ISO/IEC 27001`, `NIST CSF`, `Zero-Trust`).
- **`risks_and_impacts`:** Threat vectors, vulnerabilities, and latency impacts distilled from source claims.
- **`key_messages` & `terminology`:** Prioritized core themes and specialized domain acronyms (`CI/CD`, `API`, `ML`).

*Architectural Role:* The CCM acts as an unalterable factual anchor. It is serialized into prompt context (`to_canonical_context()`) to constrain LLM generation, and used downstream by the grounding engine to detect fabrications.

---

### 6. Consolidated AI Generation Architecture

Rather than executing 7 disconnected, sequential LLM calls (which compound latency to 25–35s and cause factual drift), the system uses a **Consolidated Generation Architecture**:
- **Prompt Structure:** Constructs a single prompt embedding the source content, CCM ground truth, audience/tone parameters, and strict JSON output schemas for all requested formats.
- **Model Configuration:** Configured to `gemini-3.5-flash-lite` with `temperature=0.3`, `max_output_tokens=8192`, and `response_mime_type="application/json"`.
- **Structured Parsing:** `extract_json_response()` strips code fences, parses JSON, and falls back to bracket scanning and case-insensitive key lookups.
- **Performance:** Generates all 7 formats simultaneously in ~6.9 seconds (~0.99s per format).

---

### 7. Multimodal Ingestion Specifications

| Modality | Formats | Limit | Ingestion Mechanism | Security & Validation Safeguards |
|---|---|---|---|---|
| **Direct Text** | UTF-8 Text | 35 MB | Form payload string | Null byte stripping; min-length check ($\ge 5$ chars, $\ge 2$ words) |
| **Documents** | `.txt`, `.md`, `.pdf`, `.docx` | **35 MB** | In-memory stream (`pypdf`, `python-docx`) | Rejects null bytes, `\ufffd` artifacts, control chars, binary noise |
| **Images** | `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif` | **10 MB** | Base64 Data URI $\rightarrow$ inline Gemini part | Client pre-flight check + `MAX_IMAGE_SIZE_BYTES`; MIME validation |
| **Videos** | `.mp4`, `.webm`, `.mov` | **25 MB** | Base64 Data URI $\rightarrow$ inline Gemini part | Client pre-flight check + `MAX_VIDEO_SIZE_BYTES`; MIME validation |

---

# [PAGE 2] Validation, Recovery, Security & Technical Design

### 8. Deterministic Factual Grounding Engine

Because LLMs can produce plausible but ungrounded claims, the architecture **strictly decouples generation from validation**. Validation is performed deterministically by application logic in `transform_service.py`:

```text
Generated Output Text
       │
       ▼ [Structural Scaffolding Exclusion]
       │ Strips non-factual markup (Slide 1:, Scene 2:, Header Metric:) via _is_scaffolding_or_boilerplate()
       │
       ▼ [Claim Candidate Splitting]
       │ Deconstructs output into atomic proposition sentences via _split_into_claim_candidates()
       │
       ▼ [Multi-Dimensional Factual Verification] (_verify_claims_against_source)
       ├─► 1. Normalized Currency/Metric Matcher: Equates $12M to 12 million dollars via normalize_currency_token()
       ├─► 2. Factual Event & Relation Checker: Rejects ungrounded corporate actions via FACTUAL_EVENT_PATTERNS
       ├─► 3. Compound Entity Validator: Validates multi-word entities; title-case aware
       └─► 4. Morphological Suffix-Stripper: Stemming engine resolves grammatical variations (reduces = reducing)
       │
       ▼ [Multi-Scale Source Context Containment]
       │ Evaluates stem intersection against sentence windows and 3-sentence sliding chunks (_build_source_windows)
       │
       ▼ [Cross-Format Consistency Matrix]
       │ Compares canonical metrics across all 7 formats; identifies cross-format metric contradictions
       │
       ▼ [Deterministic Composite Quality Score]
          Score = 0.35 * Grounding + 0.25 * Structure + 0.25 * Consistency + 0.15 * Compliance
```

---

### 9. Composite Quality Gate & Scoring Formulas

The system evaluates output validity using a deterministic, explainable scoring formula:

$$\text{Quality Score} = 0.35 \times G + 0.25 \times S + 0.25 \times C + 0.15 \times K$$

- **Grounding ($G$, Weight 0.35):** Baseline claim grounding score. Deducts $0.35$ per unverified metric, $0.30$ per unsupported event, and $0.25$ per unsupported entity. Capped at $\le 0.50$ if ungrounded.
- **Structure ($S$, Weight 0.25):** $1.0$ for fully compliant formatting; $0.70 - 0.90$ for minor warnings; $< 0.50$ for missing structural blocks.
- **Consistency ($C$, Weight 0.25):** $1.0$ baseline; $-0.20$ penalty per cross-format contradiction.
- **Compliance ($K$, Weight 0.15):** Penalized if audience, tone, or length specifications deviate.
- **Quality Gate Evaluation:** Evaluated in `evaluate_quality_gate()`. Passes if $\text{Score} \ge 0.80$ and zero fatal structural or grounding failures exist.

---

### 10. Targeted Self-Healing / Recovery Architecture

When an output format fails validation, the system avoids restarting the entire generation pipeline:
1. **Defect Isolation:** Identifies the specific failing format (`should_trigger_recovery()` detects structural faults, unverified metrics, or unsupported events).
2. **Targeted Negative Prompt Compilation:** `build_recovery_prompt()` bundles the source ground truth, the failing draft text, the itemized defect report, and explicit negative constraints (e.g., *"Eliminate unverified metric 15%; ground all claims in source"*).
3. **Isolated Recovery Call:** `targeted_recover_missing_output()` dispatches a single Gemini request for *only that format*.
4. **Re-Validation:** The recovered text is re-evaluated by the grounding engine.
5. **State Merging:** The verified replacement is swapped into the outputs dictionary, leaving all already-valid formats untouched.

---

### 11. Selective Single-Output Refinement (`/refine`)

The system enables interactive user revisions without cascading side-effects:
- **API Endpoint:** `POST /refine` accepts `RefineRequest` containing the target `output_type`, `current_output`, user `refinement_instruction`, and original source material.
- **Execution:** Synthesizes an updated draft via `build_refinement_prompt()` in ~1.89 seconds.
- **Grounding & State Isolation:** Evaluates factual grounding on the refined output. On the frontend, React selectively mutates `result.outputs[type]` and `result.provenance[type]` while preserving all sibling outputs.

---

### 12. Security, Isolation & Reliability Controls

- **API Key & Secret Isolation:** Server-side `python-dotenv` boundary. Zero keys are exposed to the client bundle or tracked in git (`backend/.env` is git-ignored; `.env.example` contains sanitized placeholders).
- **Request Size Defense:** Starlette middleware enforces a 35 MB request ceiling before buffering, mitigating memory exhaustion attacks.
- **In-Memory Rate Limiting:** Sliding-window per-IP limiter (`RATE_LIMIT_PER_MINUTE=60`) on transformation endpoints prevents quota flooding.
- **Safe In-Memory Document Processing:** All uploaded documents are parsed in-memory using `pypdf` and `python-docx` without writing to temporary disk files, preventing path traversal and arbitrary execution.
- **Deterministic Mock Fallback:** Setting `USE_MOCK=true` redirects calls to `mock_transform_content()`, enabling full offline demonstrations with realistic, schema-compliant data when external APIs are unreachable.

---

### 13. System API Specifications

```text
POST /transform
  ├─ Request:  TransformRequest { source_content, output_types, target_audience?, tone?, language?,
  │                               detail_level?, document_name?, image_data?, video_data? }
  └─ Response: TransformResponse { status, outputs: { format: text }, metadata, provenance,
                                   canonical_content, cross_format_consistency, quality_score, quality_gate }

POST /refine
  ├─ Request:  RefineRequest { source_content, output_type, current_output, refinement_instruction, ... }
  └─ Response: RefineResponse { status, output_type, refined_output, metadata, provenance, quality_gate }

POST /extract-text
  ├─ Request:  Multipart FormData { file: UploadFile } (.txt, .md, .pdf, .docx)
  └─ Response: { filename: str, extracted_text: str, character_count: int }

GET /health
  └─ Response: { status: "ok" } (Used for automated container/process liveness probes)
```

---

### 14. Verification Metrics & Empirical Benchmarks

The system implementation has been validated with reproducible automated benchmarks:
- **Automated Test Suite (`backend/test_grounding.py`):** **133 / 133 tests passed in 0.235 seconds** across 18 specialized test classes covering stemmers, metric normalizers, compound entities, formatting structures, recovery loops, and quality gates.
- **Frontend Production Build:** Built with Vite 5.4 in **564 ms** (31 modules, 0 errors, 0 warnings).
- **Latency Benchmarks:**
  - `GET /health`: **5.01 ms**
  - `POST /extract-text` (`README.md`): **9.47 ms**
  - `POST /refine` (Single format live): **1.89 s**
  - `POST /transform` (7 formats live consolidated): **6.94 s** (~0.99s per output format)

---

### 15. Key Architectural Differentiators

1. **Upstream Canonical Content Model (CCM):** Ground-truth extraction precedes generation, providing an unalterable factual reference frame.
2. **Consolidated Single-Pass Generation:** Synthesizes 7 formats in ~7s within a single LLM request, avoiding repeated generation latency and cross-format divergence.
3. **Decoupled Deterministic Grounding:** Uses algorithmic stemming, currency normalization, and multi-scale windowing containment rather than expensive, circular LLM self-evaluation.
4. **Targeted Negative-Feedback Self-Healing:** Recovers only failing outputs with specific defect constraints without perturbing valid deliverables.
5. **Granular Provenance & State Isolation:** Generates transparent claim-level audit trails and enables isolated single-format refinements.
