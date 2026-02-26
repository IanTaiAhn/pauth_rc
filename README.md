# P-Auth RC — Prior Authorization Readiness Checker

A policy compiler for Medicare total joint arthroplasty. Converts Medicare LCD policy documents into structured prior authorization checklist JSONs.

## Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

#### Option 1: Using uv (Recommended - 10-100x faster)

```bash
# Install uv (one-time setup)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or on Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Clone the repository
git clone https://github.com/IanTaiAhn/pauth_rc.git
cd pauth_rc/backend

# Create virtual environment and install dependencies (one command!)
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On macOS/Linux
# Or on Windows: .venv\Scripts\activate

# Run the application
uvicorn app.main:app --reload --port 8000
```

Alternatively, run without activating the venv:
```bash
uv run uvicorn app.main:app --reload --port 8000
```

#### Option 2: Using pip (Traditional method)

```bash
# Clone the repository
git clone https://github.com/IanTaiAhn/pauth_rc.git
cd pauth_rc/backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# Or on Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn app.main:app --reload --port 8000
```

### Environment Variables
Create a `.env` file in the `backend` directory with the following variables:

```
GROQ_API_KEY=your_groq_api_key
TEMPLATES_DIR=./templates
LOG_LEVEL=INFO
```

## API

```
POST /api/compile
  multipart/form-data:
    policy_file: PDF or TXT   (Medicare LCD policy document)
    payer: string             (e.g., "medicare")
    lcd_code: string          (e.g., "L36007")
  Returns: PolicyTemplate JSON
```

## Scope

This MVP targets **Medicare total joint arthroplasty** LCD policies. Add more LCD policy documents to `policies/` and run the compiler — no Python changes needed.
