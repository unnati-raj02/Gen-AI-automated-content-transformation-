# AI Content Transformer (SIH Project)

An AI-powered content transformation platform where a user provides source information and selects one or more output formats. The system transforms the source into requested communication artefacts such as Executive Summaries, Advisories, and LinkedIn Posts.

---

## High-Level Architecture

```text
React frontend (Port 3000)
        ↓
FastAPI backend (Port 8000)
        ↓
Input processing
        ↓
Transformation engine
        ↓
LLM service
        ↓
Output validation
        ↓
React results
```

---

## Project Structure

```text
ai-content-transformer/
├── backend/
│   ├── main.py              # FastAPI application entry point
│   └── requirements.txt     # Python backend dependencies
├── frontend/
│   ├── index.html           # HTML entry point
│   ├── package.json         # Node dependencies and scripts
│   ├── vite.config.js       # Vite configuration
│   └── src/
│       ├── App.jsx          # Placeholder React root component
│       └── main.jsx         # React DOM mounting
├── .gitignore               # Git ignore file (prevents secrets like .env from being committed)
└── README.md                # Project documentation
```

---

## Getting Started

### 1. Backend Setup (FastAPI)

Navigate to the `backend` directory:
```bash
cd backend
```

Create and activate a virtual environment (optional but recommended):
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

Install backend dependencies:
```bash
pip install -r requirements.txt
```

Run the backend server:
```bash
uvicorn main:app --reload --port 8000
```
- API will be accessible at: `http://localhost:8000`
- Interactive API docs will be at: `http://localhost:8000/docs`

---

### 2. Frontend Setup (React + Vite)

In a separate terminal, navigate to the `frontend` directory:
```bash
cd frontend
```

Install frontend dependencies:
```bash
npm install
```

Start the Vite development server:
```bash
npm run dev
```
- Frontend application will be accessible at: `http://localhost:3000`
