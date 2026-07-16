# Knowledge activation runs

## Purpose

An activation run converts a verified but inactive release into the single public release without
requiring the operator to coordinate hundreds of claim and guidance actions manually.

The run stores the target and previous releases, approval evidence, exact release checksum, review
dates, expected guidance and benchmark-candidate counts, preflight result, execution result and
timestamps. One run exists per immutable release.

## State model

- `blocked`: preflight found one or more hard inconsistencies;
- `ready`: counts, checksum, state and review dates are consistent;
- `running`: execution has begun within the current transaction;
- `completed`: approval, publication and materialization committed together;
- `rolled_back`: the activated release was withdrawn and a valid predecessor restored;
- `failed`: reserved for persisted operational failure handling.

Creation and preflight do not publish content. A blocked or failed run can refresh preflight after
the operator corrects missing guidance or other inputs. Replaying execute on a completed run returns
the stored result without duplicating reviews or benchmarks.

## Atomic execution

Execution locks the run and target release, verifies the checksum again, records separate certified
anonymous reviews for every claim and guidance record, creates the release review, supersedes the
current release, publishes the target, and materializes structured benchmarks. One commit makes the
entire transition visible.

For collector 1.6.1 the operator should set expected guidance to 705 and expected benchmark
candidates to 101. The preflight also requires all 906 stored claims to match the release count.

## Guarded rollback

Rollback is allowed only while the activated release is still the current published release. If a
predecessor exists, it is restored only when it has a non-expired release-level approval. The new
release is withdrawn, its claims and guidance become ineligible, and its benchmark definitions are
withdrawn. History and review evidence are retained.

Rollback to “no published release” is possible for a first activation. This is safer than retaining
content that the operator explicitly withdrew.
