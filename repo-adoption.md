# Reference Repository Adoption

## Repository identified

The uploaded reference material corresponds to the **TEN Framework** ecosystem. Its documentation describes it as an open-source framework for realtime multimodal conversational AI, with agent examples, VAD, turn detection and modular extensions.

The current TEN repository also provides low-latency voice-agent examples and supports Agora credentials in its agent setup.

## Can we reuse it?

### Yes — selectively.

Use it when it gives us a proven implementation for:

- realtime voice orchestration
- VAD
- turn detection
- streaming
- provider adapters
- interruption handling
- agent examples

But do not copy the whole repository into EchoDrive just because it works.

## Preferred strategy

### Option A — recommended for this project

Keep our application architecture centered on:

```text
Agora Conversational AI
        +
EchoDrive Voice Runtime
        +
FastAPI control plane
        +
Sales domain layer
```

Borrow proven patterns from TEN and reuse individual compatible components only when they reduce implementation risk.

### Option B

Use TEN Agent as the voice-runtime foundation and build EchoDrive as the custom application/domain layer around it.

Choose this only if the TEN integration is stable and does not make Agora integration, debugging or hackathon compliance harder.

## Decision rule

Before adopting a TEN component, evaluate:

1. license
2. maintenance status
3. dependency footprint
4. latency
5. cancellation behavior
6. observability
7. Agora compatibility
8. ease of debugging
9. ability to replace it later

## Important

The hackathon requires Agora Conversational AI as a core component. The implementation must make Agora's role clear in the architecture and demo.

Do not replace Agora with another RTC platform.

## License

The TEN repository documents Apache 2.0 licensing with additional restrictions for some portions/components. Review the exact license of every reused file/package before copying or redistributing it.

## What should not be copied

Do not copy:

- unrelated demo applications
- frontend assets unrelated to EchoDrive
- credentials
- vendor-specific configuration that is not needed
- entire framework source trees
- code without understanding its lifecycle/cancellation behavior

## What should be reused conceptually

The most valuable TEN ideas are:

- modular realtime extensions
- dedicated VAD/turn detection
- full-duplex interaction
- streaming pipelines
- provider isolation
- production-oriented agent lifecycle

These align strongly with EchoDrive's low-latency requirements.

## Final recommendation

Do not restart the project around TEN if the current Agora voice core is already working.

First benchmark the existing Agora runtime.

If a TEN component clearly improves latency or interruption reliability, integrate that component behind an adapter rather than coupling the entire sales application to the framework.
