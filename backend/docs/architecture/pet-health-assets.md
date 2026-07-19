# Pet health assets and consent

Pet body photographs and medical records are private pet-owned assets. They use the approved local
filesystem volume under `pet-assets/{pet_id}/...`, while PostgreSQL stores authorization, purpose,
checksum, provenance and lifecycle metadata. Trust evidence is a separate operator-owned boundary.

An active, purpose-matching, versioned consent is required before upload. A pet may have at most one
active consent per purpose. Withdrawing consent immediately removes linked assets from customer use
and download, but does not physically erase bytes: irreversible deletion remains blocked until the
medical-retention and backup-expiry policy is approved.

Customer uploads are limited to signature-checked JPEG, PNG and PDF content. Access requires an
authenticated membership in the asset's household. Storage paths are never returned to clients.

Body assessments use the 1–9 BCS scale and preserve MCS separately. Customer submissions are always
owner-reported. The single operator may record an external veterinarian's confirmation only when an
operator evidence file, veterinarian identity/credential and audit reason are supplied.
