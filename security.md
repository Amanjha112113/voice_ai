# Security and Reliability

## Secrets

Store provider credentials in environment variables or a secret manager.

Never expose permanent API keys to the frontend.

## Authentication

The control plane must authenticate users/sessions in production.

## Authorization

Tools must enforce server-side authorization.

The LLM is never an authorization boundary.

## PII

Minimize collection.

Encrypt sensitive data at rest and in transit.

Apply retention policies.

## Logging

Never log:

- API keys
- access tokens
- passwords
- full payment information

Redact sensitive customer fields where appropriate.

## Appointment safety

Booking requires:

1. valid customer/session
2. valid vehicle/dealership
3. available slot
4. explicit confirmation
5. idempotent mutation

## Reliability

Every session must clean up:

- ASR tasks
- LLM tasks
- TTS tasks
- queues
- subscriptions
- timers

On disconnect, cancellation must propagate.

## Provider failure

The system must degrade gracefully.

Examples:

- TTS failure → retry/fallback provider if configured
- catalog failure → do not invent facts
- CRM failure → preserve lead state locally and retry
- calendar failure → offer manual booking

## Dependency safety

Pin compatible versions.

Run vulnerability checks.

Review licenses before adopting external code.
