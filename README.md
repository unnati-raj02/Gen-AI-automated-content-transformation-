# AI Content Transformer

> **Smart India Hackathon (SIH) Technical Submission**  
> An intelligent, full-stack content transformation platform that converts raw multimodal inputs into structured, tailored, and verified communication artefacts with deterministic factual grounding and targeted self-healing recovery.

---

## ⚡ Quick Start (Evaluator 3-Minute Run)

To run the complete verified application locally from scratch:

### 1. Backend (Terminal 1)
```bash
# Navigate to backend directory
cd backend

# Create & activate Python virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env from template
# Windows:
copy .env.example .env
# macOS / Linux:
cp .env.example .env

# Configure backend/.env with your Gemini API key (or set USE_MOCK=true for offline demo)
# GEMINI_API_KEY=your_key_here
# GEMINI_MODEL=gemini-3.5-flash-lite
# USE_MOCK=false

# Start FastAPI backend (port 8000)
uvicorn main:app --reload --port 8000
```
*Backend verification: Visit `http://127.0.0.1:8000/health` (returns `{"status":"ok"}`).*

### 2. Frontend (Terminal 2)
```bash
# In a separate terminal, navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server (port 3000)
npm run dev
```

### 3. Open Application
- Open your browser at: **`http://localhost:3000`**
- Click the **🛡️ CyberShield Incident Pilot** preset banner to populate sample enterprise data.
- Click **Transform Content** to execute a live multi-format transformation (~7 seconds).

---

## 1. Project Overview & Problem Statement

In enterprise, government, and institutional environments, high-value source information (such as incident reports, audit logs, strategy memos, policy updates, and research papers) must be communicated to diverse stakeholders with conflicting requirements:
- **Executives & C-Suite** require high-level, actionable summaries with strategic risk implications.
- **Technical & Engineering Teams** require precise root-cause analysis, metrics, and technical advisories.
- **Public & Social Stakeholders** require engaging, accessible posts (LinkedIn, Twitter/X).
- **Creative & Visual Media Teams** require structured infographics, slide decks, and video production storyboards.

**The Problem:**
Manual cross-format authoring is slow, labor-intensive, and introduces human error. Generic Large Language Model (LLM) prompts frequently suffer from **hallucinations, unverified statistical extrapolations, inconsistent metrics across formats, and catastrophic regeneration costs** when a single output needs revision.

**The Solution:**
**AI Content Transformer** solves this with a **Consolidated Transformation Architecture** backed by an upstream **Canonical Content Model (CCM)** and a deterministic downstream **Factual Grounding Engine**. The system ingests multimodal sources (text, PDF, DOCX, images, video) and simultaneously produces up to 7 distinct communication formats in a single request (~7 seconds), verifies factual consistency against source truth, detects unsupported claims, and enables isolated single-format refinement without perturbing the rest of the generated suite.

---

## 2. Key Differentiators

Unlike generic AI wrapper apps, this system provides enterprise-grade reliability and architectural depth:

1. **Consolidated Single-Pass Generation (~7s Latency):** Rather than triggering 7 sequential LLM calls (taking 25–35s), the system executes a single structured Gemini call that generates all selected outputs concurrently while maintaining cross-format context.
2. **Canonical Content Model (CCM):** Upstream extraction creates a ground-truth representation of source claims, quantifiable metrics, temporal dates, and named entities with a cryptographic SHA-256 source hash.
3. **Deterministic Factual Grounding Engine:** Post-generation validation inspects each generated output against the CCM using morphological stemming, multi-scale source windowing, normalized currency/number matching, and factual event verification.
4. **Targeted Self-Healing / Negative Recovery:** When an individual format fails the quality gate (e.g., an ungrounded statistic), the system triggers an isolated targeted recovery for *only* that format with explicit negative constraints, leaving valid outputs intact.
5. **Interactive Single-Output Refinement (`/refine`):** Users can iteratively modify any single format (e.g., adjust tone or add a hook) in ~1.9s without regenerating or mutating unaffected outputs.
6. **Rich Visualizers & Multimodal UI:** Interactive Presentation slide carousel with speaker notes, Infographic KPI card layouts, Video Package 3-column scene storyboards, and one-click JSON/Markdown provenance exports.

---

## 3. System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                 REACT 18 + VITE FRONTEND                                │
│    [01 SOURCE]        [02 CONFIGURE]       [03 GENERATE]      [04 VALIDATE]   [05 RESULTS]│
│  Text/Docs/Media  →  Audience/Tone/Lang  →  Format Chips  →  Quality Gate  → Visualizers │
└────────────────────────────────────────────┬────────────────────────────────────────────┘
                                             │ HTTP (JSON / Multipart)
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                             FASTAPI BACKEND API GATEWAY                                 │
│  - Configurable CORS Middleware            - 35 MB Request Body Protection Middleware    │
│  - Sliding-Window In-Memory Rate Limiter   - Structured Schema Validation (Pydantic v2) │
└──────────────────────┬───────────────────────────────────────────────────┬──────────────┘
                       │                                                   │
                       ▼                                                   ▼
┌──────────────────────────────────────────────┐  ┌───────────────────────────────────────┐
│          DOCUMENT & MEDIA INGESTION          │  │       CANONICAL CONTENT MODEL         │
│  - .pdf (pypdf), .docx (python-docx)         │  │  - Atomic Claims & Key Messages       │
│  - .txt, .md, OCR noise/corruption checks    │  │  - Normalized Metrics & Currencies    │
│  - Images/Videos (Base64 Data URI)           │  │  - Dates, Entities, SHA-256 Hash      │
└──────────────────────┬───────────────────────┘  └───────────────────┬───────────────────┘
                       │                                              │
                       └──────────────────────┬───────────────────────┘
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        CONSOLIDATED TRANSFORMATION ENGINE                               │
│            Google Gemini (Configured Model: gemini-3.5-flash-lite / Mock Fallback)     │
│            Consolidated Structured Prompt → 7 Output Formats Generated in 1 Pass        │
└─────────────────────────────────────────────┬───────────────────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        FACTUAL GROUNDING & AUDIT ENGINE                                 │
│  - Multi-Scale Windowing Containment       - Normalized Metric & Currency Verifier       │
│  - Morphological Stemming Engine            - Factual Event & Relation Validator         │
│  - Structural Scaffolding Exclusion         - Unsupported Claim / Extrapolation Detector │
└──────────────────────┬───────────────────────────────────────────────────┬──────────────┘
                       │ Gate Passed                                       │ Gate Failed
                       ▼                                                   ▼
┌──────────────────────────────────────────────┐  ┌───────────────────────────────────────┐
│             PROVENANCE REGISTRY              │  │      TARGETED SELF-HEALING LOOP       │
│  - Per-format Grounding Score (0.0 to 1.0)   │  │  Isolates ONLY failing format          │
│  - Coverage Ratios & Verification Logs       │  │  Injects negative constraint feedback  │
│  - Traceable Audit Metadata                  │  │  Heals output without full regenerate │
└──────────────────────────────────────────────┘  └───────────────────────────────────────┘
```

---

## 4. Supported Input Modalities

The system supports diverse input modalities with in-memory validation and strict pre-flight limits:

| Modality | Supported Formats | Max File Size | Processing Method |
|---|---|---|---|
| **Direct Text** | Plain text, pasted raw notes, transcripts | Unbounded (within payload limit) | Direct ingestion & UTF-8 normalization |
| **Documents** | `.txt`, `.md`, `.pdf`, `.docx` | **35 MB** | In-memory extraction via `pypdf` & `python-docx` with null-byte, control-character, and binary corruption detection |
| **Images** | `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif` | **10 MB** | Base64 Data URI parsing; passed to Gemini vision understanding pipeline |
| **Videos** | `.mp4`, `.webm`, `.mov` | **25 MB** | Base64 Data URI parsing; passed to Gemini multimodal video understanding pipeline |

*Note: File upload limits are enforced on both client-side pre-flight and backend middleware. Video files are checked for payload size; no synthetic duration constraints are claimed.*

---

## 5. Output Communication Formats

The platform transforms source material into 7 distinct communication formats:

1. **Executive Summary:** High-level TL;DR, core factual pillars, strategic implications, and clear decision takeaways for senior management.
2. **Advisory:** Severity/risk rating, threat vector or policy context, immediate operational impacts, and structured mitigation checklists.
3. **LinkedIn Post:** Professional thought-leadership framing, bold metric highlights, conversational hooks, and industry hashtags.
4. **Twitter/X Post:** High-impact, concise micro-post designed for character limits with a compelling lead, core statistic, and topic tags.
5. **Infographic Layout:** Structured KPI data callouts, hierarchical flow steps, and visual card specifications ready for design handoff.
6. **Presentation Slide Deck:** Multi-slide structure with slide titles, bullet points, key takeaways, and dedicated presenter speaker notes.
7. **Video Production Package:** Complete 3-column scene storyboard detailing Visual Scene Directions, Narration / Voiceover Script, and On-Screen Text / Chyrons.

---

## 6. Granular Configuration Controls

Users can tailor the transformation across 6 axes:

- **Target Audience:** C-Suite & Executive Leadership, Engineering & Technical Teams, Product & Project Managers, Compliance & Legal Stakeholders, Marketing & Communications, Investors & Financial Analysts, General Audience.
- **Tone:** Professional, Urgent, Casual, Inspiring, Informative, Persuasive.
- **Communication Objective:** Inform, Persuade, Educate, Call to Action, Inspire, Decision Support.
- **Content Style:** Direct & Concise, Analytical & Data-Driven, Storytelling & Narrative, Technical & Precise, Conversational.
- **Detail Level:** Brief, Moderate, Detailed.
- **Language:** English, Hindi (हिन्दी), Spanish (Español), French (Français), German (Deutsch).

---

## 7. Factual Grounding, CCM & Provenance

### Canonical Content Model (CCM)
Before generation, the backend builds an in-memory Canonical Content Model:
- **Core Claims:** Extracted atomic factual statements.
- **Quantifiable Metrics:** Normalized percentages, counts, units, and currencies (e.g., `$12M` equates to `12 million dollars` or `$12,000,000`).
- **Critical Dates:** Quarter, year, and specific temporal references.
- **Named Entities:** Key organizational, product, and standard identifiers (e.g., `SOC2 Type II`, `ISO/IEC 27001`).
- **Source Integrity Hash:** SHA-256 digest of the raw source content.

### Factual Grounding Engine
Following generation, the engine verifies every candidate claim:
- **Hard-Fail Metric Checks:** Rejects unverified numbers, percentages, or financial amounts not grounded in the source.
- **Event / Relation Verification:** Checks that critical verbs (e.g., acquired, certified, deployed, launched) match source context.
- **Compound Entity Verification:** Validates multi-word organizational entities against source tokens.
- **Morphological Stemming:** Suffix-stripping algorithm prevents false rejections on grammatical variants (`reduces`, `reduced`, `reduction`).
- **Scaffolding Exclusion:** Excludes structural labels (`Slide 1:`, `Narration:`, `Scene 2:`) to avoid false-positive warnings.
- **Quality Gate Calculation:** Computes a composite grounding score (0.0 to 1.0). Gate passes when claims are verified and unsupported metrics equal zero.

### Targeted Self-Healing / Single-Format Recovery
If an output fails validation, the system does **not** re-execute the entire pipeline. Instead, `targeted_recover_missing_output`:
1. Isolates the specific failing format.
2. Formulates a targeted prompt containing the previous draft, the exact defect report, and negative constraints.
3. Requests Gemini to correct that single format.
4. Updates the result set while preserving already-verified outputs.

### Provenance & Export
- **Provenance Tray:** Visual inspection card displaying verified claim count, coverage ratio, and grounding score per format.
- **Deliverables Export:** Download full Markdown bundle (`.md`) with embedded audit data or export standalone Provenance JSON (`.json`).

---

## 8. Technology Stack

- **Frontend:**
  - React 18 (Functional components, custom hooks)
  - Vite 5 (Lightning-fast build and HMR)
  - Vanilla CSS3 (Custom design system, glassmorphism, responsive grid, visual slide carousels)
- **Backend:**
  - Python 3.10+
  - FastAPI (High-performance async web framework)
  - Uvicorn (ASGI web server)
  - Pydantic v2 (Strict request/response validation schemas)
  - `pypdf` & `python-docx` (In-memory document extraction)
  - `google-generativeai` (Google Gemini SDK)
- **Security & Infrastructure:**
  - Starlette HTTP Middleware (Payload size guards, in-memory rate limiting)
  - `python-dotenv` (Strict environment separation)

---

## 9. Project Directory Structure

```text
ai-content-transformer/
├── .env.example                     # Root environment configuration template
├── .gitignore                       # Git ignore rules (node_modules, venv, .env)
├── README.md                        # Master SIH submission documentation
├── backend/
│   ├── .env.example                 # Backend environment template
│   ├── main.py                      # FastAPI application, middleware, CORS, rate limits
│   ├── requirements.txt             # Backend dependencies (FastAPI, pypdf, docx, etc.)
│   ├── test_grounding.py            # Automated test suite (133 tests)
│   ├── routers/
│   │   ├── __init__.py
│   │   └── transform.py             # API routes: /health, /transform, /refine, /extract-text
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── transform_schema.py      # Pydantic models (CCM, TransformRequest/Response, etc.)
│   └── services/
│       ├── __init__.py
│       ├── document_service.py      # Ingestion & sanitization (.pdf, .docx, .txt, .md)
│       └── transform_service.py     # Gemini engine, CCM, Grounding Engine, Targeted Recovery
└── frontend/
    ├── index.html                   # HTML entry point
    ├── package.json                 # Node dependencies and scripts
    ├── vite.config.js               # Vite bundler configuration (Port 3000)
    └── src/
        ├── main.jsx                 # React root mounting
        ├── App.jsx                  # Main SPA component (5-stage flow, visualizers, drawers)
        └── App.css                  # Custom styling system and animations
```

---

## 10. Complete Step-by-Step Local Setup

Follow these exact steps for a clean, verified evaluator setup:

### Step 1: Prerequisites
Ensure the following are installed on your machine:
- **Python:** Version 3.10 or higher (`python --version`)
- **Node.js:** Version 18.0 or higher (`node --version`)
- **npm:** (`npm --version`)
- **Git:** (`git --version`)

### Step 2: Clone the Repository
```bash
git clone <repository-url>
cd ai-content-transformer
```

### Step 3: Set Up Backend Virtual Environment
Navigate to the `backend/` directory and create an isolated virtual environment:
```bash
cd backend

# Create virtual environment named .venv
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (Command Prompt):
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate
```

### Step 4: Install Backend Dependencies
With the virtual environment activated:
```bash
pip install -r requirements.txt
```

### Step 5: Create and Configure `backend/.env`
Copy the included `.env.example` file to `.env`:
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `backend/.env` in any text editor and configure:
```env
# =======================================================
# AI Content Transformer - Backend Environment Variables
# =======================================================

# 1. Google Gemini API Key
# Get a free key at: https://aistudio.google.com/
GEMINI_API_KEY=your_actual_gemini_api_key_here

# 2. Configured Gemini Model (Must match codebase configuration: gemini-3.5-flash-lite)
GEMINI_MODEL=gemini-3.5-flash-lite

# 3. Execution Mode:
# Set to false for live Gemini inference
# Set to true for offline deterministic mock fallback (no API key needed)
USE_MOCK=false

# 4. Deployment & Security Settings
ALLOWED_ORIGINS=*
RATE_LIMIT_PER_MINUTE=60
MAX_REQUEST_BODY_SIZE_BYTES=36700160
```

### Step 6: Start the Backend Server
From the `backend/` directory (with `.venv` active):
```bash
uvicorn main:app --reload --port 8000
```
- API Base URL: `http://127.0.0.1:8000`
- API Health Check: `http://127.0.0.1:8000/health` (verify returns `{"status":"ok"}`)
- Swagger Documentation: `http://127.0.0.1:8000/docs`

### Step 7: Install Frontend Dependencies
Open a **new separate terminal** window and navigate to the `frontend/` directory:
```bash
cd frontend
npm install
```

### Step 8: Start the Frontend Development Server
From the `frontend/` directory:
```bash
npm run dev
```
The console will display:
```text
  VITE v5.4.x  ready in ~300 ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: use --host to expose
```

### Step 9: Open and Test Application
Open your browser and navigate to:
**`http://localhost:3000`**

---

## 11. `USE_MOCK` Fallback Mode Explained

The platform provides a dual-mode execution strategy:

- **`USE_MOCK=false` (Default Live Mode):**  
  Uses the configured `gemini-3.5-flash-lite` model for real-time natural language synthesis, vision processing, video understanding, and interactive single-format refinement.
- **`USE_MOCK=true` (Deterministic Offline / Evaluation Fallback):**  
  Activates an internal deterministic mock generator. This allows evaluators or presenters to demonstrate the entire application flow, all 7 formats, visualizers, and audit cards completely offline without consuming API quota or requiring venue Wi-Fi connectivity.

---

## 12. Testing & Verification Results

The application has undergone rigorous validation:

- **Backend Unit & Integration Suite:**
  ```bash
  cd backend
  python -m unittest test_grounding.py
  ```
  **Result:** `133 / 133 tests passed` in `0.235s` (OK).  
  *Tests verify canonical model extraction, metric normalization, currency matching, compound entity detection, factual event checks, stemming, scaffolding exclusion, quality gate calculation, and extraction sanitization.*
- **Frontend Production Build:**
  ```bash
  cd frontend
  npm run build
  ```
  **Result:** `31 modules transformed`, built in `~564ms`, **0 errors, 0 warnings**.
- **Measured Latency Benchmarks:**
  - `GET /health`: **5.01 ms**
  - `POST /extract-text` (`README.md`): **9.47 ms**
  - `POST /refine` (Single format): **1.89 s**
  - `POST /transform` (All 7 formats concurrent): **6.94 s** (~0.99s per format)

---

## 13. Security & Secret Management

- **Zero Secret Leakage:** No API keys are tracked in git history, committed in repositories, or compiled into frontend assets (`git grep "AIzaSy"` returns 0).
- **Environment Isolation:** Keys are loaded strictly server-side through `dotenv`.
- **Payload & File Size Defense:** Starlette middleware drops requests exceeding 35 MB before loading into RAM with `HTTP 413`.
- **In-Memory Rate Limiting:** Sliding-window IP rate limiter (`RATE_LIMIT_PER_MINUTE=60`) prevents quota exhaustion and API abuse.
- **Safe Document Extraction:** Files are parsed in-memory using `pypdf` and `python-docx` without temporary disk execution, shell invocation, or path traversal vectors.

---

## 14. Recommended Evaluator Demo Flow

Follow this 5-minute walkthrough to evaluate all features:

1. **Preset One-Click Load (0:30):** Click **🛡️ CyberShield Incident Pilot** in the demo presets banner. Notice how source content, document badge, configurations, and formats populate instantly.
2. **Transform (0:45):** Click **Transform Content**. Observe the real-time progress indicators and the consolidated single-pass generation completing in ~7 seconds.
3. **Inspect Grounding & Audit Trail (1:30):**
   - Click **Grounding & Audit Trail** badge.
   - Inspect the Canonical Content Model: 6 claims extracted, metrics verified (`68%`, `99.4%`), dates matched (`Q1 2026`), zero unverified claims.
4. **Interact with Rich Visualizers (2:30):**
   - **Presentation:** Click next/previous controls to flip through slides and view speaker notes.
   - **Infographic:** View structured KPI callouts and flow layout cards.
   - **Video Package:** Inspect the 3-column scene storyboard (Visual Action, Narration, Screen Text).
   - Click **Show Raw Markdown** to inspect underlying structured markdown.
5. **Test Selective Refinement (3:30):**
   - On the **LinkedIn Post** card, click **Refine Output**.
   - Enter instruction: *"Make the hook punchier and emphasize the 68% detection improvement for security engineering leads."*
   - Click **Apply Refinement**.
   - Notice that only the LinkedIn Post updates in ~1.9s; Presentation, Advisory, and Executive Summary remain untouched.
6. **Test Ingestion & Export (4:30):**
   - Upload a sample `.pdf` or attach an image to see immediate multimodal extraction.
   - Click **Download Bundle (.md)** to receive all formatted artefacts and provenance logs in a single deliverable.
