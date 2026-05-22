/** Shared API shapes for SSR pages (mirror backend DTOs). */

export type ClaimListItem = {
  id: string;
  public_slug: string;
  canonical_claim_text: string;
  status: string;
  confidence_score: number;
  evidence_count: number;
  discovery_score: number;
  updated_at: string;
  processing_status?: string | null;
  visibility_label?: string | null;
  scores?: SearchScoreBreakdown;
};

export type SearchScoreBreakdown = {
  semantic_similarity: number;
  text_relevance: number;
  evidence_quality: number;
  confidence_score: number;
  freshness_score: number;
  relationship_density: number;
  final_score: number;
};

export type EvidenceItem = {
  id: string;
  title: string;
  url: string | null;
  publisher: string | null;
  stance: string;
  credibility_score: number;
  summary: string | null;
  retrieval_timestamp: string | null;
};

export type AIAnalysisItem = {
  id: string;
  analysis_type: string;
  model_name: string;
  provider: string;
  generated_text: string;
  created_at: string;
};

export type ClaimDetail = {
  id: string;
  public_slug: string;
  canonical_claim_text: string;
  status: string;
  confidence_score: number;
  controversy_score: number;
  evidence_score: number;
  freshness_score: number;
  evidence_count: number;
  discovery_score: number;
  aliases: string[];
  evidence_supporting: EvidenceItem[];
  evidence_contradicting: EvidenceItem[];
  evidence_contextual: EvidenceItem[];
  ai_analyses: AIAnalysisItem[];
  related_slugs: string[];
  processing_status?: string | null;
  pipeline_stage_key?: string | null;
  pipeline_stage_label?: string | null;
  live_ai_summary?: string | null;
  visibility_label?: string | null;
  moderation_reviewed?: boolean;
  truth_label?: "supported" | "refuted" | "unclear" | null;
};

export type UserProfile = {
  id: string;
  username: string;
  role: string;
  reputation_score: number;
  email_verified_at: string | null;
};

export type GraphNode = {
  id: string;
  type: "claim" | "evidence_cluster";
  position: { x: number; y: number };
  data: {
    label: string;
    slug: string | null;
    is_focus: boolean;
    stance?: string | null;
    count?: number | null;
    confidence_score?: number | null;
  };
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  type: "relationship" | "evidence_cluster";
  label?: string | null;
  data?: {
    relationship_type?: string | null;
    strength?: number | null;
    explanation?: string | null;
  };
};

export type ClaimGraph = {
  focus_claim_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  available_relationship_types: string[];
  truncated: boolean;
};

export type TimelineEvent = {
  id: string;
  event_type:
    | "confidence_evolution"
    | "moderation"
    | "evidence"
    | "contradiction_emergence"
    | "freshness_decay";
  timestamp: string;
  title: string;
  description: string | null;
  payload: Record<string, unknown>;
};

export type ClaimTimeline = {
  claim_id: string;
  events: TimelineEvent[];
};

export type CursorMeta = {
  next_cursor?: string | null;
  previous_cursor?: string | null;
  has_more?: boolean;
  sort?: string;
};

export type ClaimAtlasPoint = {
  id: string;
  public_slug: string;
  label: string;
  status: string;
  confidence_score: number;
  controversy_score: number;
  evidence_score: number;
  freshness_score: number;
  evidence_count: number;
  x: number;
  y: number;
  z: number;
};

export type ClaimAtlasData = {
  points: ClaimAtlasPoint[];
  method: string;
  embedding_dimensions: number;
  total_indexed: number;
  projected_count: number;
  computed_at: string;
  note: string;
};
