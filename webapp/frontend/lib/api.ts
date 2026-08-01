export interface Reason {
  factor: string;
  direction: "increases_risk" | "reduces_risk" | null;
  weight: number | null;
}

export interface Dealer {
  dealer_id: string;
  dealer_name: string;
  city: string;
  sector: string;
  salesman_id: string;
  is_salesman_favorite: boolean;
  credit_limit_pkr: number;
  credit_score: number;
  risk_flag: string;
  risk_probability: number | null;
  scoring_method: string;
  top_reasons: Reason[];
}

export interface QualityReport {
  input_rows: number;
  output_rows: number;
  retention_rate: number;
  dropped_missing_dealer: number;
  dropped_orphan_dealer: number;
  dropped_bad_dates: number;
  dropped_bad_amount: number;
  dropped_bad_bounce_flag: number;
  dropped_logical_inconsistency: number;
}

export interface Summary {
  total_dealers: number;
  red_count: number;
  amber_count: number;
  green_count: number;
  salesman_favorite_red_count: number;
}

export interface DistributionShift {
  severity: "low" | "moderate" | "high";
  max_displacement_sds: number;
  per_feature_displacement_sds: Record<string, number>;
}

export interface ScoreSaturation {
  severity: "low" | "high";
  clipped_at_floor: number;
  clipped_at_ceiling: number;
  pct_clipped: number;
}

export interface TrainingReport {
  attempted: boolean;
  trained: boolean;
  reason: string;
  training_pool_size?: number;
  base_rate?: number;
  cv_auc_mean?: number;
  cv_auc_std?: number;
  cv_ks_mean?: number;
  feature_window_ends?: string;
  outcome_window_months?: number;
  history_span_months?: number;
  late_threshold_days?: number;
  late_threshold_basis?: string;
}

export interface Reliability {
  verdict: "scores_reliable" | "scores_indicative" | "use_ranking_only";
  guidance: string;
  distribution_shift: DistributionShift;
  score_saturation: ScoreSaturation;
  model_source?: "pretrained" | "trained_on_your_data";
  training_report?: TrainingReport;
  pretrained_fit_check?: DistributionShift;
}

export interface CutoffInfo {
  cutoff_date: string;
  strategy: string;
  data_range?: string;
}

export interface ScoreResponse {
  session_id: string;
  summary: Summary;
  quality_report: QualityReport;
  dealers: Dealer[];
  // Optional: an older backend deployment won't send these. Everything
  // downstream must tolerate them being absent.
  reliability?: Reliability;
  cutoff_info?: CutoffInfo;
  input_notes?: string[];
}

function resolveApiUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (configured) return configured;

  if (process.env.NODE_ENV !== "production") {
    // Local dev fallback -- safe, since this file only runs on the
    // developer's own machine where localhost:8000 is meaningful.
    return "http://127.0.0.1:8000";
  }

  // Production build with no backend URL configured. Returning "" rather
  // than a silent localhost fallback means any fetch below will be caught
  // and reported clearly, instead of every visitor's browser quietly (and
  // uselessly) trying to reach their OWN localhost.
  console.error(
    "NEXT_PUBLIC_API_URL is not set in this production build. " +
    "Set it in the deployment platform's environment variables and redeploy."
  );
  return "";
}

const API_URL = resolveApiUrl();

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function scorePortfolio(
  dealersFile: File,
  salesmenFile: File,
  transactionsFile: File
): Promise<ScoreResponse> {
  if (!API_URL) {
    throw new ApiError(
      "This deployment is missing its backend configuration (NEXT_PUBLIC_API_URL). " +
      "This is a setup issue, not something you can fix by retrying -- contact the site administrator."
    );
  }

  const form = new FormData();
  form.append("dealers_file", dealersFile);
  form.append("salesmen_file", salesmenFile);
  form.append("transactions_file", transactionsFile);

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/score`, { method: "POST", body: form });
  } catch {
    throw new ApiError(
      "Could not reach the scoring service. Check that the backend is running and reachable."
    );
  }

  if (!res.ok) {
    let detail = `Scoring failed (${res.status}).`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // response wasn't JSON, keep default message
    }
    throw new ApiError(detail);
  }

  return res.json();
}

export function exportCsvUrl(sessionId: string): string {
  return `${API_URL}/api/session/${sessionId}/export-csv`;
}

/** Normalizes the risk_flag string (which can be RED / AMBER / GREEN /
 * AMBER-CAUTION / AMBER-STANDARD for cold-start dealers) into one of three
 * display tiers, so the UI has one consistent vocabulary. */
export function tierOf(riskFlag: string): "RED" | "AMBER" | "GREEN" {
  if (riskFlag.startsWith("RED")) return "RED";
  if (riskFlag.startsWith("GREEN")) return "GREEN";
  return "AMBER";
}

export function recommendedAction(tier: "RED" | "AMBER" | "GREEN", isFavorite: boolean): string {
  if (tier === "RED") {
    return isFavorite
      ? "Do not increase credit limit. Consider cash-on-delivery terms. This account's trusted status contradicts its payment record — recommend a direct conversation with the assigned salesman."
      : "Do not increase credit limit. Consider requiring partial upfront payment or cash-on-delivery terms on future orders.";
  }
  if (tier === "AMBER") {
    return "Maintain current credit limit. Monitor closely and reassess in 3 months.";
  }
  return "Eligible for credit limit review or increase based on strong payment history.";
}

export function riskCardUrl(sessionId: string, dealerId: string): string {
  return `${API_URL}/api/session/${sessionId}/dealer/${dealerId}/risk-card`;
}