# TEN Framework Reference Analysis for EchoDrive

This document provides a comprehensive technical analysis of the `reference/ten-framework-main` repository, evaluating its architecture, components, patterns, and suitability for the **EchoDrive** low-latency realtime voice sales agent.

---

## 1. Overview of the Reference Repository

The `ten-framework-main` repository is the open-source multimodal conversational AI framework created by Agora and contributors. It organizes real-time voice agents into graphs of modular C++, Go, and Python extensions that communicate via typed message passing (Commands, Data, and Audio/Video frames).

### Key Architectural Pillars in TEN:
1. **Extension-based Micro-pipeline**: Decoupled nodes for RTC, VAD, ASR, LLM, TTS, and Tool dispatch.
2. **Unified Data Bus**: IPC/RPC layer passing audio frames (`AudioFrame`), control messages (`Cmd`), and textual/JSON payloads (`Data`).
3. **Full-Duplex Async Event Loop**: Non-blocking asynchronous event processing with task cancellation.

---

## 2. Deep Dive: Key Components & File Paths

### A. Agora RTC & Media Connectivity
- **Relevant File Paths**:
  - `ai_agents/server/internal/http_server.go`: HTTP control plane generating Agora RTC tokens (`rtctokenbuilder2`), allocating channels, and managing agent worker instances.
  - `ai_agents/server/internal/config.go`: Maps Agora App ID, Certificate, Channel, and Stream IDs across extensions.
  - `ai_agents/agents/examples/voice-assistant-with-ten-vad/tenapp/property.json`: Manifest declaring `agora_rtc` extension configuration and graph topology.
  - `ai_agents/agents/examples/http-control/tenapp/scripts/start.sh`: Runtime initialization linking shared C/C++ libraries (`agora_rtc_sdk`).
- **What It Does**:
  - Acts as the RTC gateway between browser/mobile clients and the agent backend.
  - Ingests PCM audio frames (16kHz, 16-bit mono) from user microphones via Agora audio streams.
  - Receives synthesized audio from TTS extensions and renders it back to the customer's Agora audio stream.
  - Handles `flush` commands to immediately abort client-side playback buffer during interruption.
- **Reusable Patterns**:
  - Token-based room allocation on `POST /sessions`.
  - Immediate `flush` signal to RTC audio sink on barge-in.
  - 16kHz 16-bit PCM 20ms frame chunking (640 bytes per 20ms).
- **Dependencies**: C++ Agora RTC SDK binaries (`agora_rtc_sdk/lib`), Go RTC token builder (`AgoraDynamicKey/go/src/rtctokenbuilder2`).
- **Reuse / Adapt / Reimplement**: **Adapt / Reimplement**. In Python/FastAPI, implement pure-Python Agora RTC token generation and an Agora RTC / WebRTC audio streaming adapter without dragging in binary C++ framework bindings.

---

### B. Voice Activity Detection (VAD)
- **Relevant File Paths**:
  - `ai_agents/agents/ten_packages/extension/ten_vad_python/extension.py`: Python VAD wrapper with probe windows.
  - `ai_agents/agents/ten_packages/extension/ten_vad_python/config.py`: Thresholds, hop size, prefix padding, silence duration.
  - `packages/example_extensions/webrtc_vad_cpp`: C++ WebRTC VAD extension.
- **What It Does**:
  - Processes raw PCM audio chunks continuously (10ms–20ms hops).
  - Maintains a sliding probe window (`probe_window`).
  - Detects voice onset (`prefix_window_size` above threshold) and emits `start_of_sentence` / `speech_start`.
  - Detects trailing silence (`silence_window_size` below threshold) and emits `end_of_sentence` / `speech_end`.
- **Reusable Patterns**:
  - Dual-window thresholding (prefix window for fast onset detection < 60ms; silence window for stable turn completion ~300-500ms).
  - Audio passthrough buffer keeping audio flowing to ASR while performing non-destructive VAD calculation.
- **Dependencies**: `ten_vad` C extension / `numpy`.
- **Reuse / Adapt / Reimplement**: **Adapt**. Reimplement the dual-window sliding probe algorithm in pure Python using energy/amplitude + WebRTC VAD / Silero heuristics for zero-overhead, ultra-low-latency speech boundary detection.

---

### C. Turn Detection & Turn-Taking
- **Relevant File Paths**:
  - `ai_agents/agents/ten_packages/extension/ten_turn_detection/extension.py`: Evaluates conversational turns from streaming text.
  - `ai_agents/agents/ten_packages/extension/ten_turn_detection/turn_detector.py`: Async LLM/heuristic turn-evaluation engine with cancellation.
  - `ai_agents/agents/ten_packages/extension/ten_turn_detection/utils.py`: Text normalization and punctuation filters.
- **What It Does**:
  - Evaluates intermediate & final ASR transcripts to determine if the user finished speaking or paused mid-thought.
  - Employs a fast completion check or timeout fallback (`eval_force_chat_task`).
  - If unfinished, waits; if finished, seals the turn and triggers response generation.
- **Reusable Patterns**:
  - Turn state tracker (`turn_id`, `new_turn_started`).
  - Dynamic silence timeout: Short timeout if sentence ends with terminal punctuation; longer timeout if ending mid-clause.
  - Cancellable turn evaluation task (`cancel_eval()`).
- **Dependencies**: `openai` Async client, `httpx` connection pool.
- **Reuse / Adapt / Reimplement**: **Adapt**. Implement deterministic turn-boundary logic (hybrid punctuation + silence timer) that requires no extraneous network hop on every syllable.

---

### D. Interruption & Barge-In
- **Relevant File Paths**:
  - `ai_agents/agents/examples/voice-assistant-with-ten-vad/tenapp/ten_packages/extension/main_python/extension.py` (lines 204–215): `_interrupt()` implementation.
  - `ai_agents/agents/examples/voice-assistant-with-ten-vad/tenapp/ten_packages/extension/main_python/agent/agent.py` (lines 194–217): `flush_llm()`.
- **What It Does**:
  - When `VadStartOfSentenceEvent` fires while the agent is generating or speaking:
    1. Flushes & cancels the active LLM generation task (`_llm_active_task.cancel()`).
    2. Clears the LLM token queue.
    3. Emits `tts_flush` with a unique UUID to abort in-flight audio synthesis.
    4. Emits `flush` to `agora_rtc` to clear hardware playback buffers.
    5. Clears active sentence fragments.
- **Reusable Patterns**:
  - 3-point simultaneous flush: LLM stream + TTS synthesis queue + RTC playback sink.
  - Drain queues with `get_nowait()` to prevent stuck memory.
- **Dependencies**: `asyncio`.
- **Reuse / Adapt / Reimplement**: **Reuse & Elevate**. EchoDrive will elevate this with **Generation IDs (UUIDs)** so that any chunk already in flight with an obsolete ID is discarded instantaneously at playback time, guaranteeing zero stale audio.

---

### E. Streaming Audio & Progressive Response Pipeline
- **Relevant File Paths**:
  - `ai_agents/agents/ten_packages/extension/deepgram_ws_asr_python/extension.py`: Real-time bidirectional WebSocket streaming ASR.
  - `ai_agents/agents/ten_packages/extension/openai_llm2_python/extension.py`: Token streaming via OpenAI chat completions.
  - `ai_agents/agents/examples/voice-assistant-with-ten-vad/tenapp/ten_packages/extension/main_python/helper.py`: `parse_sentences` sentence chunker.
- **What It Does**:
  - Streams raw audio upstream to ASR.
  - As LLM tokens arrive incrementally, `parse_sentences` accumulates text and yields full clauses/sentences upon encountering punctuation delimiters (`.`, `!`, `?`, `,`).
  - Immediately dispatches complete sentences to TTS, allowing the first audio to play while the LLM is still generating subsequent sentences.
- **Reusable Patterns**:
  - Punctuation-based sentence streaming chunker (`parse_sentences`).
  - Non-blocking async queue between LLM token consumer and TTS synthesis worker.
  - Dedicated request IDs for TTS chunk ordering (`tts-request-{turn_id}-{chunk_id}`).
- **Dependencies**: `aiohttp`, `openai`, `asyncio`.
- **Reuse / Adapt / Reimplement**: **Reuse & Refine**. Recreate the streaming sentence chunker with adaptive clause splitting (avoiding splitting on small numbers or abbreviations like `Rs. 15.5 Lakh`).

---

### F. Task Cancellation & Async Concurrency
- **Relevant File Paths**:
  - `ai_agents/agents/examples/voice-assistant-with-ten-vad/tenapp/ten_packages/extension/main_python/agent/agent.py`:
    - `_llm_active_task`
    - `_asr_consumer`
    - `_llm_consumer`
    - `flush_llm()`
- **What It Does**:
  - Encapsulates long-running background loops in named `asyncio.Task` instances.
  - When cancellation is requested, calls `task.cancel()`, catches `asyncio.CancelledError`, and cleans up references in `finally` blocks.
- **Reusable Patterns**:
  - Idempotent task cancellation helper.
  - Structured shutdown in `stop()`: Drain queues -> Cancel active tasks -> Await task completion -> Close network sessions.
- **Dependencies**: Standard Python `asyncio`.
- **Reuse / Adapt / Reimplement**: **Reuse**. Apply strict cancellation idioms across all EchoDrive background workers.

---

### G. Agent & Session Lifecycle
- **Relevant File Paths**:
  - `ai_agents/agents/examples/voice-assistant-with-ten-vad/tenapp/ten_packages/extension/main_python/extension.py`: Extension lifecycle (`on_init`, `on_start`, `on_stop`, `on_deinit`).
  - `ai_agents/server/internal/http_server.go`: Worker process orchestration, lifecycle endpoints, worker timeout cleanup.
- **What It Does**:
  - Session startup: Client requests token -> Channel created -> Runtime initialized -> Initial greeting synthesized.
  - Session termination: Client disconnects -> In-flight tasks canceled -> Channels destroyed -> Resources released.
- **Reusable Patterns**:
  - State-driven session container owning all per-session queues, tasks, generation IDs, and metrics.
- **Dependencies**: FastAPI/Go.
- **Reuse / Adapt / Reimplement**: **Adapt**. Implement in FastAPI as pure-Python `VoiceSession` objects managed by a `SessionManager` registry.

---

## 3. License and Dependency Summary

| Component | Upstream Source | License | Assessment |
|---|---|---|---|
| TEN Core & Runtime | `ten-framework-main` | Apache 2.0 | Reference architecture patterns only. No wholesale binary inclusion. |
| Agora Dynamic Key | AgoraIO / DynamicKey | Apache 2.0 / MIT | Compatible. Pure Python token builder used. |
| Deepgram / OpenAI Adapters | TEN extensions | Apache 2.0 | Patterns adapted into EchoDrive provider interfaces. |

---

## 4. Synthesis & Architectural Decisions for EchoDrive

1. **Avoid Framework Sprawl**: TEN relies on C++ binaries, cross-compilation toolchains (`gn`, `ninja`), and Go wrappers. For EchoDrive's hackathon and production goals, we adopt TEN's **design patterns** (sliding-window VAD, 3-point interruption flush, streaming sentence chunker) into a clean, lightweight, pure-Python async architecture using **FastAPI + Agora RTC / Audio Engine**.
2. **First-Class Generation IDs**: Add UUID generation tracking at every stage (VAD → ASR → LLM → Chunker → TTS → Audio Sink) to ensure zero stale audio playback under rapid barge-in conditions.
3. **Explicit State Machine**: Replace ad-hoc booleans with a formal state machine (`IDLE`, `LISTENING`, `THINKING`, `SPEAKING`, `INTERRUPTING`, `ERROR`).
4. **Latency Telemetry**: Integrate precise microsecond timestamps at every boundary (speech onset, speech end, ASR final, LLM TTFT, TTS first chunk, Audio first played, Interruption stop) for real-time TTFA instrumentation.
