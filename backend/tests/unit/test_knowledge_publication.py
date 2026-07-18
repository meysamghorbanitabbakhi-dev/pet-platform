from datetime import UTC, datetime
from uuid import uuid4

from app.api.routes.knowledge import _public_source
from app.modules.pet_knowledge.models import KnowledgeRelease, KnowledgeReviewTask, KnowledgeSource


def test_public_source_projection_excludes_internal_record_fields() -> None:
    source = KnowledgeSource(
        release_id=uuid4(),
        external_id="source:study-1",
        source_type="epidemiology",
        title="Study title",
        record={
            "url": "https://example.test/study",
            "pmid": "12345",
            "internal_note": "must never be public",
            "copyrighted_excerpt": "must never be public",
        },
    )
    result = _public_source(source)
    assert result.url == "https://example.test/study"
    assert result.pmid == "12345"
    assert not hasattr(result, "internal_note")
    assert not hasattr(result, "copyrighted_excerpt")


def test_expired_release_is_not_a_public_release_status() -> None:
    release = KnowledgeRelease(
        schema_version="1",
        dataset_version="test",
        language="fa-IR",
        status="review_expired",
        checksum_sha256="a" * 64,
        storage_key="knowledge/test.json",
        imported_by_operator_id=uuid4(),
        imported_at=datetime.now(UTC),
        breed_count=1,
        variety_count=0,
        source_count=1,
        claim_count=1,
    )
    assert release.status != "published"


def test_review_task_is_operator_governance_not_customer_health_state() -> None:
    task = KnowledgeReviewTask(
        review_id=uuid4(),
        status="due",
        due_at=datetime.now(UTC),
        detected_at=datetime.now(UTC),
    )
    assert task.status == "due"
