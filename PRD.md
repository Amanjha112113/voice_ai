# PRD — EchoDrive

## 1. Product

**EchoDrive — Real-Time Voice AI Sales Agent for Automotive Dealerships**

## 2. Vision

Make car buying conversational.

A customer should be able to speak naturally with EchoDrive, explain what they need, compare vehicles, change requirements, ask follow-up questions, raise objections, and finish with a concrete next action.

## 3. Target user

Primary:

- online car shopper
- dealership lead
- showroom visitor
- prospective test-drive customer

Secondary:

- dealership sales executive
- sales manager

## 4. Core problem

Car buyers often jump between vehicle websites, comparison pages, pricing pages and dealership calls. Traditional chatbots are rigid and scripted. Sales staff also spend time answering repetitive questions and qualifying low-intent leads.

## 5. Product promise

EchoDrive can:

1. understand spoken requirements
2. remember them
3. recommend suitable vehicles
4. retrieve accurate product/pricing information
5. handle objections
6. adapt when requirements change
7. qualify buying intent
8. book a showroom visit/test drive
9. hand off to a human with context

## 6. Example conversation

Customer:
"I need an SUV around 15 lakh."

Agent:
"Sure. Is this mainly for city driving, family trips, or a mix?"

Customer:
"Mostly family. Seven seats are important."

Agent:
"That helps. I can compare suitable seven-seat SUVs."

Customer:
"Wait, compare the Scorpio with a Toyota option."

The agent immediately stops speaking, updates the comparison intent, retrieves current catalog information and continues.

Later:

Customer:
"Actually, my budget can go to 18 lakh if the mileage is good."

The deal state changes.

Finally:

Customer:
"I'd like to see the best option."

Agent:
"Based on your requirements, I recommend these two. I can book a showroom visit or test drive. Which would you prefer?"

## 7. MVP

### Must have

- Agora realtime voice
- streaming ASR
- streaming LLM
- streaming TTS
- VAD/turn detection
- barge-in
- cancellation
- multi-turn context
- structured customer/deal state
- car catalog retrieval
- qualification
- appointment booking
- live dashboard
- latency telemetry

### Should have

- competitor comparison
- CRM lead creation
- human escalation
- multilingual support
- inventory awareness

### Later

- financing/EMI tools
- insurance
- outbound calling
- dealer multi-tenancy
- advanced analytics
- omnichannel messaging

## 8. Success metrics

Voice:

- TTFA P50 target <700 ms under favorable conditions
- interruption stop target <200 ms
- no stale audio after interruption
- no orphan tasks

Sales:

- requirement extraction accuracy
- recommendation grounding rate
- tool-call success rate
- appointment completion rate
- lead qualification accuracy

These are engineering targets, not guaranteed SLAs.

## 9. Non-goals

- autonomous negotiation of legally binding offers
- hallucinated vehicle pricing
- autonomous financial approval
- replacing human sales staff for complex cases
- medical/financial advice
