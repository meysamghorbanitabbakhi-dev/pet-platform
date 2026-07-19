# Privacy and retention

The backend supports authenticated customer data export and operator-executed account disablement.
Disablement revokes active sessions and preserves financial, order, trust, and operator audit facts.

Anonymization requests are deliberately stored as `awaiting_policy`. They must not be executed until
Iranian legal/accounting retention requirements, fraud controls, data-field classification, and the
approved irreversible transformation are documented. There is no broad customer hard-delete API.

Before launch, Product/Legal must approve:

- retention periods by table and evidence category;
- which identifiers may be pseudonymized and when;
- export response-time and identity-verification procedure;
- rejection/escalation wording;
- backup expiry behavior after anonymization.

Every operator privacy decision requires a reason and is written to the immutable audit stream.
