# Module boundaries

The backend is a modular monolith. A module owns its tables and write model. Another module
may invoke an explicit command, consume a published event, or use an approved query port; it
must not update the owner's tables directly.

## Launch ownership rules

- Household owns account access, addresses, payments, wallet, orders, and physical inventory.
- Pet owns personalization, assignments, estimates, journeys, diary, memories, and Garden.
- Inventory represents physical truth; food estimation is a replaceable calculation over it.
- Journey definitions are immutable once published. Enrollments pin one approved version.
- Diary is durable history. Garden is an emotional projection and never the source of history.
- Orders keep financial, sourcing, fulfillment, SLA, cancellation, and resolution dimensions.
- Provider payloads are evidence, not canonical domain status.

## Forbidden dependencies

- Garden cannot write journey or diary truth.
- Food estimation cannot create or duplicate inventory.
- Notifications cannot decide business eligibility.
- Redis cannot hold authoritative business state.
- Operator endpoints cannot expose generic database CRUD.
- Catalog edits cannot rewrite paid order snapshots.
- Provider SDK objects cannot enter domain interfaces.

