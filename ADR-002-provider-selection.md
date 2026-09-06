# ADR-002 — Realtime Voice Provider Selection for MVP

## Status
Accepted

## Context
EchoDrive requires low-latency streaming Speech-to-Text (ASR), Large Language Model (LLM) token generation, and Text-to-Speech (TTS) synthesis to achieve the Time-to-First-Audio (TTFA) target (P50 ≤ 700 ms) and interruption stop latency (P50 ≤ 200 ms).

For Phase 1–5 (MVP core voice loop), introducing multiple competing providers at each layer adds configuration complexity, maintenance overhead, and non-deterministic behavior during benchmarking. We need to evaluate available providers, select exactly ONE primary provider per layer, and encapsulate them behind clean abstract interfaces (`ASRProvider`, `LLMProvider`, `TTSProvider`).

## Evaluation Matrix

### 1. ASR (Speech-to-Text)
| Candidate | Streaming Protocol | Time to Interim / Final | Word Error Rate (WER) | Cancellation / Interruption | Recommendation |
|---|---|---|---|---|---|
| **Deepgram Nova-2** | WebSockets (raw PCM audio chunks) | ~150–250 ms | Excellent on conversational audio | Server handles stream disconnects / immediate flush | **SELECTED PRIMARY** |
| OpenAI Whisper API | HTTP Multipart Chunked | ~600–1200 ms (chunked) | Very Good | Slow chunk boundary turnaround | Rejected for realtime loop |
| Google Cloud Speech-to-Text | gRPC streaming | ~250–350 ms | Very Good | Good | Backup candidate |

**Decision**: **Deepgram Nova-2 (WebSocket streaming)** is selected as the primary ASR provider due to sub-250ms streaming latency, interim results, and native support for 16kHz PCM audio streaming.

---

### 2. LLM (Streaming Generation)
| Candidate | Streaming Protocol | Time to First Token (TTFT) | Conversational Intelligence | Connection Management | Recommendation |
|---|---|---|---|---|---|
| **OpenAI GPT-4o / GPT-4o-mini** | Server-Sent Events (SSE) / HTTP/2 streaming | ~200–350 ms (mini) / ~350–500 ms (4o) | Superior domain understanding, reasoning, and tool accuracy | Persistent HTTP/2 connection pooling | **SELECTED PRIMARY** |
| Groq (Llama 3.3 70B) | SSE streaming | ~120–180 ms | High speed, slightly lower nuance in structured domain state | Good | Fast alternative adapter |
| Anthropic Claude 3.5 Sonnet | SSE streaming | ~350–550 ms | High nuance, slightly higher TTFT | Good | Backup candidate |

**Decision**: **OpenAI (GPT-4o-mini for ultra-low latency, GPT-4o for complex sales reasoning)** is selected as the primary LLM provider.

---

### 3. TTS (Text-to-Speech)
| Candidate | Streaming Protocol | First Audio Latency (TTFA contribution) | Audio Naturalness | Mid-stream Cancellation | Recommendation |
|---|---|---|---|---|---|
| **Cartesia Sonic** | WebSocket / SSE chunked audio | ~90–150 ms | Ultra-realistic conversational human prosody | Native `cancel` / instant socket close | **SELECTED PRIMARY (Primary Low-Latency)** |
| ElevenLabs Flash v2.5 | WebSocket streaming | ~180–280 ms | Exceptional voice cloning / quality | Supports websocket break | High-quality alternative |
| OpenAI TTS-1 | Chunked HTTP streaming | ~300–500 ms | Good | Socket termination | Baseline fallback |

**Decision**: **Cartesia Sonic (with OpenAI TTS-1 as fallback)** is selected as the primary TTS engine due to sub-150ms first-chunk audio synthesis over streaming WebSockets.

---

### 4. Realtime Media Plane (RTC)
- **Agora RTC**: Official SDK / Agora WebRTC Audio Gateway.
- Uses official Agora token generation (`AgoraAccessToken2` / HMAC-SHA256).

---

## Architectural Rule
- All provider integrations MUST implement the standard abstract interfaces in `backend/app/providers/base.py`.
- No vendor-specific SDK objects may leak into the voice runtime state machine or domain objects.
- CI/CD tests run against deterministic mock providers in `backend/app/providers/mock_providers.py`.
