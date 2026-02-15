# Guru Speech Engine

A custom speech recognition system built around the Whisper small model with optimized settings, noise reduction capabilities, and command detection layer.

## Features

- **Speech Transcription**: Uses faster-whisper with int8 quantization for efficient inference
- **Noise Reduction**: Pre-processes audio using noisereduce library
- **Multi-language Support**: English, Hindi, and Punjabi
- **Command Detection**: Maps transcriptions to agent actions
- **Real-time Processing**: Supports both microphone input and file-based audio

## Installation

```bash
pip install -r requirements.txt
```

## Project Structure

```
guru_speech/
├── __init__.py           # Package initialization
├── engine.py             # Main GuruSpeechEngine facade
├── speech.py             # WhisperTranscriber for transcription
├── noise.py              # NoiseCleaner for audio pre-processing
├── commands.py           # CommandInterpreter for command detection
├── capture.py            # Audio capture components
├── models.py             # Data models and dataclasses
├── exceptions.py         # Exception classes
├── model/                # Directory for model files
└── requirements.txt      # Package dependencies
```

## Usage

(Examples will be added after implementation)

## Development

Run tests:
```bash
pytest tests/ -v --cov=guru_speech
```

Run property-based tests:
```bash
pytest tests/ -v -k "property"
```

## Requirements

See [requirements.txt](requirements.txt) for full dependency list.
