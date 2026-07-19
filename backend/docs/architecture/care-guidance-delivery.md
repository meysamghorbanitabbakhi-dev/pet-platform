# Care-guidance delivery

## Eligibility

Care guidance is personalized only when the pet has an explicit `known` breed selection. The item
must belong to the current published release, match the selected breed, remain app-eligible after
independent veterinary review, and match the selected variety when it has variety scope. Mixed and
unknown selections receive no breed-specific guidance.

Age filtering is fail-closed and uses only explicit `minimum_age_days` and `maximum_age_days` from
the approved content. The backend does not invent puppy, adult or senior thresholds. When an item
declares an age range and the pet has no birth date, that item is ineligible.

## Delivery surfaces

`GET /pet-life/pets/{pet_id}/care-guidance` returns a bounded eligible feed and can be filtered by
domain. Every item includes its exact guidance identifier, release version and checksum, population
explanation, source claim identifiers, anonymous-review disclosure and non-diagnostic disclaimer.

Today considers only exercise, grooming, training and home guidance. It returns at most one item,
does not alter `primary_attention`, and does not create a task, alert, streak or Garden reward.
Safety guidance remains available in the deliberate feed but is never selected as a quiet Today
suggestion.

## Owner control

An owner can dismiss, snooze or restore an exact guidance item. Snoozes must end in the future and
are bounded to 365 days. Preferences are release-content-specific: newly reviewed replacement
guidance is not silently suppressed by a decision about an older item.

## Safety boundary

Guidance is approved general information, not an individual diagnosis, treatment plan or health
classification. Emergency classification is reviewed source metadata, not an inference made from
the pet. Guidance never uses owner photographs, measurements or behavior to infer disease, breed or
clinical status. A future clinical workflow requires a separate professional-care contract.
