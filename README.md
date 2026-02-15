# DUB5 Chatbot Project

## Overview
DUB5 Chatbot is an advanced AI system with multiple personalities and capabilities, designed for deployment on Vercel.

## Features
- **Multiple Personalities**: General, Coder, Teacher, Writer
- **Dual AI Backend**: Primary g4f with Pollinations AI fallback
- **Streaming Responses**: Real-time streaming for better UX
- **File Processing**: Support for document uploads and parsing
- **Web Search**: Real-time information retrieval
- **Image Generation**: Integrated image creation capabilities

## Project Structure
```
chatbot/
├── api/                    # Core AI functionality
│   ├── index.py            # Main FastAPI application
│   ├── chatbot_backup.py   # AI streaming logic
│   ├── config.py           # Configuration settings
│   ├── models.py           # Data models
│   ├── personalities.py    # Personality definitions
│   └── ...               # Other API modules
├── docs/                  # Documentation
│   ├── phase1_diagnosis.md
│   ├── phase2_reliability_enhancements.md
│   ├── phase3_professionalism_and_trustworthiness.md
│   ├── phase4_scalability_and_performance.md
│   ├── plan.md
│   ├── DUB5_AI_Integration.md
│   ├── SYSTEMPROMPT.md
│   └── DEPLOYMENT_GUIDE.md
├── scripts/               # Utility scripts
│   ├── send_message.py
│   ├── list_providers.py
│   └── test_dub5.ps1
├── tests/                 # Test files
│   ├── test_coder_personality.py
│   ├── test_general_personality.py
│   ├── debug_test.py
│   └── test_new_features.py
├── data/                  # Data storage
├── chatbot.html           # Main frontend
├── image.html             # Image generation interface
├── api-key-generator.html # API key utility
├── requirements.txt        # Python dependencies
└── vercel.json           # Vercel configuration
```

## Quick Start

### Local Development
1. Install dependencies: `pip install -r requirements.txt`
2. Start server: `python -m uvicorn api.index:app --host 0.0.0.0 --port 8001 --reload`
3. Open browser: `http://localhost:8001`

### Testing
- Coder personality: `python tests/test_coder_personality.py`
- General personality: `python tests/test_general_personality.py`

### Deployment
Ready for Vercel deployment with all configurations in place.

## AI Backend Architecture

1. **Primary**: g4f providers (multiple fallback options)
2. **Fallback**: Pollinations AI (reliable for coder personality)
3. **Circuit Breaker**: Prevents cascading failures
4. **Retry Logic**: Automatic retries with exponential backoff

## Personalities

- **General**: Helpful AI assistant for general queries
- **Coder**: Specialized for code generation and web development
- **Teacher**: Patient educational explanations
- **Writer**: Creative writing and storytelling

## Technologies Used

- **Backend**: FastAPI, Python 3.9+
- **AI**: g4f, Pollinations AI
- **Frontend**: HTML, CSS, JavaScript
- **Deployment**: Vercel Serverless Functions
- **Streaming**: Server-Sent Events (SSE)
