# Deploying EchoDrive Voice AI to Render (render.com)

This repository is pre-configured with all essential configuration files for zero-configuration, 1-click deployment on [Render](https://render.com).

---

## Deployment Options

### Option 1: Automatic Blueprint Deployment (Recommended)
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** $\rightarrow$ **Blueprint**.
3. Connect your GitHub repository: `https://github.com/Amanjha112113/voice_ai.git`.
4. Render will automatically detect [`render.yaml`](render.yaml) and configure the web service with all build and start commands.
5. In the **Environment Variables** prompt, fill in your secret API keys:
   - `AGORA_APP_ID`
   - `AGORA_APP_CERTIFICATE`
   - `GROQ_API_KEY`
   - `DEEPGRAM_API_KEY`
   - `ELEVENLABS_API_KEY`
   - `OPENAI_API_KEY`
6. Click **Apply**.

---

### Option 2: Manual Web Service Deployment
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** $\rightarrow$ **Web Service**.
3. Connect the repository `https://github.com/Amanjha112113/voice_ai.git`.
4. Fill in the following service settings:
   - **Name**: `echodrive-voice-ai`
   - **Runtime**: `Python` (or `Docker`)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/health`
5. Under **Environment Variables**, add:
   | Key | Value / Source |
   | :--- | :--- |
   | `PYTHON_VERSION` | `3.11.7` |
   | `APP_ENV` | `production` |
   | `LOG_LEVEL` | `INFO` |
   | `GROQ_MODEL` | `openai/gpt-oss-120b` |
   | `OPENAI_MODEL` | `gpt-4o-mini` |
   | `ELEVENLABS_VOICE_ID` | `oO7sLA3dWfQXsKeSAjpA` |
   | `AGORA_APP_ID` | *(Your Agora App ID)* |
   | `AGORA_APP_CERTIFICATE` | *(Your Agora App Certificate)* |
   | `GROQ_API_KEY` | *(Your Groq API Key)* |
   | `DEEPGRAM_API_KEY` | *(Your Deepgram API Key)* |
   | `ELEVENLABS_API_KEY` | *(Your ElevenLabs API Key)* |
   | `OPENAI_API_KEY` | *(Your OpenAI API Key)* |
6. Click **Deploy Web Service**.

---

## Included Essential Deployment Files

- [`requirements.txt`](requirements.txt): Python dependencies for FastAPI, Groq, Deepgram, OpenAI, WebSockets, and Pydantic.
- [`render.yaml`](render.yaml): Infrastructure-as-Code blueprint specification for Render.
- [`Procfile`](Procfile): Standard web entrypoint running `uvicorn` with `$PORT`.
- [`runtime.txt`](runtime.txt): Pinning Python runtime version to 3.11.7.
- [`Dockerfile`](Dockerfile) & [`.dockerignore`](.dockerignore): Containerized deployment support.
