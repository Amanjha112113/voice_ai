# Tools and Integrations

## Tool contract rules

Every tool must have:

- typed input
- typed output
- timeout
- structured error
- authorization policy
- idempotency behavior for mutations
- observability

## Catalog tools

### search_vehicles

Inputs:

- budget
- seating
- body_type
- fuel
- transmission
- features
- brand
- model

Returns verified vehicle records.

### get_vehicle_details

Returns authoritative details.

### compare_vehicles

Returns side-by-side facts.

## Pricing

### get_current_price

Must return:

- vehicle
- variant
- price
- currency
- source
- last_updated

Never fabricate price.

## Inventory

### check_availability

Returns:

- dealership
- vehicle/variant
- status
- freshness timestamp

## CRM

### create_lead

Use idempotency key.

### update_lead

Use structured deal state.

### get_lead

Used when resuming an existing conversation.

## Calendar

### find_test_drive_slots

Returns available slots.

### book_test_drive

Must be idempotent.

Require explicit customer confirmation before final booking.

## Human escalation

### escalate_to_sales_rep

Payload:

```json
{
  "customer_summary": "...",
  "requirements": {},
  "objections": [],
  "recommended_vehicles": [],
  "requested_action": "..."
}
```

## Tool latency

Tools must expose timing.

If a tool is slow:

- timeout
- speak a short progress/fallback response when appropriate
- avoid blocking unrelated conversation work

## Tool security

Never let the LLM directly construct arbitrary HTTP requests.

Expose only allowlisted tool functions.
