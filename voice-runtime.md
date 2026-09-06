# Voice Runtime Design

## 1. State machine

```text
IDLE
  |
  v
LISTENING
  |
  v
THINKING
  |
  v
SPEAKING
  |
  +---- user starts speaking ----> INTERRUPTING
                                      |
                                      v
                                   LISTENING

Any state ---- failure ----> ERROR
ERROR ---- recoverable ----> LISTENING
```

Keep transitions centralized.

## 2. Turn lifecycle

```text
User starts speaking
       ↓
speech_start
       ↓
stream audio
       ↓
ASR partials
       ↓
turn end detected
       ↓
freeze user turn
       ↓
update conversation state
       ↓
LLM stream
       ↓
TTS stream
       ↓
Agora playback
       ↓
speech_start may interrupt at any time
```

## 3. Generation IDs

Each response receives:

`generation_id = UUID`

Playback checks that the chunk belongs to the active generation.

On interruption:

`active_generation_id = new_generation_id`

Old chunks are ignored.

This is safer than relying only on task cancellation.

## 4. Interruption controller

Responsibilities:

- detect interruption
- stop playback
- cancel TTS
- cancel LLM
- clear queues
- mark generation obsolete
- emit interruption metrics
- return to listening

Operation must be idempotent.

## 5. Conversation context

Maintain two representations:

### Recent dialogue

Short conversational window for natural responses.

### Structured memory

```json
{
  "budget_min": null,
  "budget_max": 1800000,
  "seating": 7,
  "body_type": "SUV",
  "usage": "family",
  "priority_features": ["mileage"],
  "preferred_models": ["Scorpio"],
  "competitors": ["Toyota"],
  "objections": ["price"],
  "intent": "high",
  "next_action": "test_drive"
}
```

Structured memory is authoritative for sales state.

## 6. Provider interfaces

```python
class ASRProvider:
    async def stream_transcription(self, audio_stream): ...

class LLMProvider:
    async def stream_response(self, messages): ...

class TTSProvider:
    async def stream_audio(self, text_stream): ...
```

Do not leak vendor SDK objects into domain code.

## 7. Provider selection

Use benchmarks to select providers.

Do not assume the most famous provider is the fastest.

Measure:

- TTFA
- TTFT
- first TTS audio
- interruption stop
- quality
- stability
