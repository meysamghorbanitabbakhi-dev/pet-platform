"""Import all mapped classes so Alembic sees one complete metadata graph."""

from app.modules.catalog.models import CatalogAvailabilitySubscription, Offer, Product, Supplier
from app.modules.diary.models import DiaryEntry
from app.modules.food_estimation.models import FoodEstimate
from app.modules.garden.models import GardenReward
from app.modules.households.models import Household, HouseholdAddress, HouseholdMembership
from app.modules.identity.models import AuthIdentity, AuthSession, OtpChallenge
from app.modules.identity.privacy import PrivacyRequest
from app.modules.inventory.models import ConsumptionAssignment, InventoryUnit
from app.modules.journeys.models import JourneyCheckIn, JourneyDefinition, PetJourney
from app.modules.notifications.models import (
    Notification,
    NotificationAttempt,
    NotificationPreference,
    NotificationTemplate,
)
from app.modules.orders.fulfillment import FulfillmentEvent
from app.modules.orders.models import Order, OrderDelayAcknowledgement, OrderLine
from app.modules.orders.resolutions import OrderResolution
from app.modules.payments.models import PaymentAttempt
from app.modules.pet_health.models import (
    BenchmarkDefinition,
    BodyAssessment,
    BodyAssessmentAsset,
    HealthMeasurement,
    MeasurementReminder,
    PetAsset,
    PetConsent,
)
from app.modules.pet_knowledge.models import (
    KnowledgeActivationRun,
    KnowledgeBreed,
    KnowledgeClaim,
    KnowledgeClaimSource,
    KnowledgeGuidance,
    KnowledgeGuidancePreference,
    KnowledgeRelease,
    KnowledgeReview,
    KnowledgeReviewTask,
    KnowledgeSource,
    KnowledgeVariety,
)
from app.modules.pets.models import Pet, PetBreedSelection
from app.modules.price_intelligence.models import (
    ExchangeRateSnapshot,
    ExternalCollectionRun,
    ExternalPriceObservation,
    ExternalPriceSource,
    ExternalProduct,
    ExternalProductMatch,
    ExternalSeller,
)
from app.modules.sourcing.models import SourcingJob
from app.modules.support.models import CustomerRequest, CustomerRequestStatusAudit
from app.modules.system.models import (
    IdempotencyRecord,
    OperatorAuditLog,
    OutboxEvent,
    WebhookInboxEvent,
)
from app.modules.trust.files import EvidenceFile
from app.modules.trust.models import (
    ReferencePriceEvidence,
    SourcedUnitEvidence,
    SupplierAssurance,
)
from app.modules.wallet.models import (
    WalletAccount,
    WalletCredit,
    WalletDebit,
    WalletDebitAllocation,
)

__all__ = [
    "AuthIdentity",
    "AuthSession",
    "ConsumptionAssignment",
    "DiaryEntry",
    "CatalogAvailabilitySubscription",
    "ExchangeRateSnapshot",
    "ExternalCollectionRun",
    "ExternalPriceObservation",
    "ExternalPriceSource",
    "ExternalProduct",
    "ExternalProductMatch",
    "ExternalSeller",
    "FoodEstimate",
    "FulfillmentEvent",
    "GardenReward",
    "Household",
    "HouseholdAddress",
    "HouseholdMembership",
    "Offer",
    "Notification",
    "NotificationAttempt",
    "NotificationPreference",
    "NotificationTemplate",
    "Order",
    "OrderDelayAcknowledgement",
    "OrderLine",
    "OrderResolution",
    "PaymentAttempt",
    "HealthMeasurement",
    "MeasurementReminder",
    "PetConsent",
    "PetAsset",
    "BodyAssessment",
    "BodyAssessmentAsset",
    "BenchmarkDefinition",
    "KnowledgeRelease",
    "KnowledgeActivationRun",
    "KnowledgeBreed",
    "KnowledgeVariety",
    "KnowledgeSource",
    "KnowledgeClaim",
    "KnowledgeClaimSource",
    "KnowledgeGuidance",
    "KnowledgeGuidancePreference",
    "KnowledgeReview",
    "KnowledgeReviewTask",
    "Pet",
    "PetBreedSelection",
    "PetJourney",
    "JourneyCheckIn",
    "Product",
    "JourneyDefinition",
    "InventoryUnit",
    "Supplier",
    "SupplierAssurance",
    "SourcedUnitEvidence",
    "ReferencePriceEvidence",
    "EvidenceFile",
    "SourcingJob",
    "IdempotencyRecord",
    "OperatorAuditLog",
    "OtpChallenge",
    "PrivacyRequest",
    "OutboxEvent",
    "WebhookInboxEvent",
    "CustomerRequest",
    "CustomerRequestStatusAudit",
    "WalletAccount",
    "WalletCredit",
    "WalletDebit",
    "WalletDebitAllocation",
]
