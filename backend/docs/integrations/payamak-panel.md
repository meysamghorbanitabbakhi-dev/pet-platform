# Payamak Panel OTP delivery

The attached reference implementation established the current provider contract:

- endpoint: `POST https://rest.payamak-panel.com/api/SendSMS/SendSMS`;
- form fields: `username`, `password`, `to`, `from`, `text`, and `isFlash`;
- success is represented by `RetStatus == 1`;
- `Value` is retained as the provider message reference or diagnostic value.

## Security correction

The reference file contained credentials in source code. None of those values are copied into
this repository. They must be rotated before reuse. The production adapter reads username,
password, and sender number from environment/secret configuration and never logs the payload.

## OTP ownership

The platform—not Payamak Panel—generates and validates OTPs:

- six digits generated with Python's cryptographic `secrets` module;
- two-minute default expiry;
- 60-second resend cooldown;
- five verification attempts;
- single-use challenge;
- only an HMAC-SHA256 digest is stored;
- digest is bound to challenge ID and normalized mobile number;
- provider receives the plaintext code only for delivery;
- a successful SMS response is not authentication;
- successful local verification creates or resolves the customer identity.

Real credentials must never be committed or placed in support logs.
