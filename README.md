# China_project

AI-powered healthcare communication assistant that converts speech to text, translates clinical communication into English, simplifies complex medical language, and generates clear summaries for deaf and hard-of-hearing patients.

This prototype supports communication only. It does not diagnose, recommend treatment, or replace confirmation by a healthcare professional.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .\.env.example .\.env
```

Add your OpenAI API key to `.env`.

## Process Medical Text

Use this to test the cloud language layer without audio:

```powershell
.\.venv\Scripts\python.exe .\process_medical_text.py "The patient presents with hypertension and intermittent tachycardia." -o .\example.patient.json
```

The pipeline:

1. Translates the text to English.
2. Retrieves matching terms from `data/medical_glossary.json`.
3. Uses the cloud model to simplify the text for patient display.
4. Returns structured JSON with critical details for doctor confirmation.

## Transcribe Audio

```powershell
.\.venv\Scripts\python.exe .\transcribe.py "C:\path\to\audio.m4a"
```

To transcribe and then create the patient-friendly version:

```powershell
.\.venv\Scripts\python.exe .\transcribe.py "C:\path\to\audio.m4a" --explain
```
