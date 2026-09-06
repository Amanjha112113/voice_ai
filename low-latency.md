# Low-Latency Engineering

## Primary metric

### TTFA — Time to First Audio

`TTFA = first AI audio played - user turn completion`

The user perceives responsiveness through TTFA, not total response completion time.

## Target

Initial optimization target:

- TTFA P50 < 700 ms under favorable conditions
- interruption stop < 200 ms

These are engineering targets, not SLAs.

## Latency budget

```text
User turn end
   |
   +--> ASR finalization
   |
   +--> LLM TTFT
   |
   +--> TTS first audio
   |
   +--> Agora playback
   |
   v
First AI audio
```

Instrument every boundary.

## Optimization rules

### 1. Stream everything

- streaming ASR
- streaming LLM
- streaming TTS
- incremental playback

### 2. Start downstream work early

Use partial ASR only when it is safe and supported.

Do not require full response generation before TTS.

### 3. Keep prompts small

Do not send the entire transcript forever.

Use:

- recent dialogue
- compact structured deal state
- only relevant product context

### 4. Cache static knowledge

Cache:

- vehicle specifications
- feature descriptions
- dealership metadata

Do not cache volatile pricing/availability without freshness controls.

### 5. Avoid synchronous chains

Bad:

```text
CRM → Pricing → Inventory → Calendar → LLM
```

Better:

```text
LLM
 ├── retrieve needed catalog facts
 └── speak early
       |
       +── async CRM/dashboard updates
```

Only block the response on a tool when the customer explicitly needs that tool result.

### 6. Cancellation beats waiting

If customer interrupts:

Do not wait for the old response to finish.

Cancel it.

### 7. Connection reuse

Reuse HTTP clients and provider connections.

Do not create a new TCP/TLS connection for every turn.

### 8. Region awareness

Deploy the realtime runtime near the primary user/provider regions when possible.

Measure network RTT instead of guessing.

## Benchmark suite

Run:

- 20 warm-up sessions
- 100+ measured turns
- repeated interruptions
- long responses
- short responses
- tool calls
- provider failures

Record P50/P95/P99.

## Dashboard

Display:

- TTFA
- ASR final latency
- LLM TTFT
- TTS first-audio
- interruption detection
- interruption stop
- response completion
