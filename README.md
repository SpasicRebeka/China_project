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

1. Retrieves approved terms from `data/medical_glossary.json`.
2. Uses one cloud request to translate the text to English and simplify it for patient display.
3. Returns structured JSON with critical details for doctor confirmation.

## Transcribe Audio

```powershell
.\.venv\Scripts\python.exe .\transcribe.py "C:\path\to\audio.m4a"
```

To transcribe and then create the patient-friendly version:

```powershell
.\.venv\Scripts\python.exe .\transcribe.py "C:\path\to\audio.m4a" --explain
```

For the fastest live workflow, show raw captions first and call `--explain` only when the patient presses "Explain simply" or when the doctor finishes an important instruction. True real-time captions should use a streaming transcription connection instead of uploading finished audio files.

## Realtime Microphone Captions

List microphones:

```powershell
.\.venv\Scripts\python.exe .\realtime_transcribe.py --list-devices
```

Start realtime Chinese captions with the default microphone:

```powershell
.\.venv\Scripts\python.exe .\realtime_transcribe.py --language zh
```

For English testing, use English mode:

```powershell
.\.venv\Scripts\python.exe .\realtime_transcribe.py --language en
```

Use a specific microphone device index:

```powershell
.\.venv\Scripts\python.exe .\realtime_transcribe.py --device 9 --language zh
```

The default realtime mode is `quiet-room`. It streams audio continuously and lets server voice activity detection commit complete doctor utterances after a short pause.

For a quiet doctor-patient room, start here:

```powershell
.\.venv\Scripts\python.exe .\realtime_transcribe.py --device 9 --language zh --mode quiet-room
```

Speak one full sentence, then pause for about one second. Quiet-room mode favors complete, accurate doctor sentences over word-by-word display while someone is still talking.

By default, realtime transcription uses a medical dictation prompt for doctor-patient vocabulary while still asking the model to transcribe literally. This prompt is used by `gpt-4o-mini-transcribe`; `gpt-realtime-whisper` does not support the `prompt` parameter.

Use `--mode low-latency` only when you want faster but less stable rolling chunks:

```powershell
.\.venv\Scripts\python.exe .\realtime_transcribe.py --device 9 --language zh --mode low-latency --transcription-model gpt-realtime-whisper --delay minimal
```

If no captions appear, first check whether the selected microphone hears you:

```powershell
.\.venv\Scripts\python.exe .\realtime_transcribe.py --device 9 --monitor-levels
```

Speak normally and look for the RMS number to rise. If it barely changes, try another device from `--list-devices` or move the microphone closer.

To enable the local gate in a very noisy room:

```powershell
.\.venv\Scripts\python.exe .\realtime_transcribe.py --device 9 --language zh --debug
```

To print internal commit timing while testing:

```powershell
.\.venv\Scripts\python.exe .\realtime_transcribe.py --device 9 --language zh --max-segment-seconds 1 --debug
```
