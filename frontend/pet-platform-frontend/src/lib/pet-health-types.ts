// These backend operations return `dict[str, object]` / `additionalProperties: true`
// in the OpenAPI (not yet fully typed server-side). Shapes below are transcribed
// directly from the backend route/service implementations in
// backend/app/api/routes/pet_health.py, pet_assets.py, and knowledge.py, not invented.

export type MeasurementItem = {
  id: string;
  measurement_type: string;
  value: number;
  unit: string;
  measured_at: string;
  source: string;
  measurement_method: string | null;
  confidence: string;
  notes: string | null;
};

export type WeightTrendChange = {
  baseline_weight_kg: number;
  change_percent: number;
} | null;

export type WeightTrendResponse =
  | { state: "no_measurements"; current_weight_kg: null; changes: Record<string, never> }
  | {
      state: "available";
      current_weight_kg: number;
      measured_at: string;
      changes: Record<"7_days" | "30_days" | "90_days", WeightTrendChange>;
      interpretation: "personal_trend_only";
    };

export type PetAssetItem = {
  id: string;
  category: string;
  purpose: string;
  filename: string;
  media_type: string;
  size_bytes: number;
  checksum_sha256: string;
  captured_at: string | null;
  created_at: string;
};

export type BodyAssessmentItem = {
  id: string;
  bcs_score: number;
  bcs_scale: number;
  muscle_condition: string;
  assessment_source: string;
  answers: Record<string, unknown>;
  assessed_at: string;
  veterinarian_name: string | null;
  veterinarian_confirmed_at: string | null;
};

export type BreedListItem = {
  id: string;
  species: string;
  name_fa: string;
  name_en: string;
};

export type BreedSearchItem = BreedListItem & {
  aliases_fa: string[];
  matched_field: string;
};

export type KnowledgeSourceItem = {
  id: string;
  type: string;
  title: string;
  url?: string;
  doi?: string;
  pmid?: string;
  publication_date?: string;
  retrieved_at?: string;
  retrieval_date?: string;
};

export type KnowledgeClaimItem = {
  id: string;
  claim_type: string;
  text_fa: string;
  variety_id: string | null;
  review_status: string;
  reviewer_disclosure: string;
  sources: KnowledgeSourceItem[];
};

export type KnowledgeGuidanceItem = {
  id: string;
  domain: string;
  text_fa: string;
  variety_id: string | null;
  supporting_claim_ids: string[];
  reviewer_disclosure: string;
};

export type BreedDetailResponse = {
  release: { dataset_version: string; checksum_sha256: string; published_at: string };
  breed: BreedListItem;
  varieties: { id: string; name_fa: string; name_en: string }[];
  claims: KnowledgeClaimItem[];
  guidance: KnowledgeGuidanceItem[];
};

export type PetKnowledgeResponse =
  | {
      pet_id: string;
      status: "breed_not_recorded";
      claims: [];
      disclaimer_fa: string;
    }
  | {
      pet_id: string;
      status: "available";
      breed_identification_source: string;
      release: BreedDetailResponse["release"];
      breed: BreedListItem;
      claims: KnowledgeClaimItem[];
      guidance: KnowledgeGuidanceItem[];
      disclaimer_fa: string;
    };

export type CareGuidanceItem = {
  id: string;
  external_id: string;
  domain: string;
  text_fa: string;
  population_level_explanation_fa: string | null;
  professional_discussion_fa: string | null;
  emergency_classification: string;
  supporting_claim_ids: string[];
  release: { dataset_version: string; checksum_sha256: string };
  reviewer_disclosure: string;
  interpretation: "general_care_guidance_not_individual_medical_advice";
};

export type CareGuidanceResponse = {
  state: "breed_specific_guidance_unavailable" | "no_eligible_guidance" | "available";
  items: CareGuidanceItem[];
  disclaimer_fa: string;
};
