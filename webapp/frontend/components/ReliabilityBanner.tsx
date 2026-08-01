"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Reliability, CutoffInfo } from "@/lib/api";

interface Props {
  reliability?: Reliability;
  cutoffInfo?: CutoffInfo;
  inputNotes?: string[];
}

const VERDICT_STYLE = {
  scores_reliable: {
    border: "border-green/30", bg: "bg-green/[0.06]", dot: "bg-green",
    accent: "text-green", label: "Scores reliable",
  },
  scores_indicative: {
    border: "border-amber/40", bg: "bg-amber/[0.07]", dot: "bg-amber",
    accent: "text-amber", label: "Scores indicative only",
  },
  use_ranking_only: {
    border: "border-red/40", bg: "bg-red/[0.07]", dot: "bg-red",
    accent: "text-red", label: "Use ranking, not exact scores",
  },
} as const;

export default function ReliabilityBanner({ reliability, cutoffInfo, inputNotes }: Props) {
  const [expanded, setExpanded] = useState(false);

  // Older backend deployments omit this block entirely -- render nothing
  // rather than showing a misleading placeholder.
  if (!reliability) return null;

  const style = VERDICT_STYLE[reliability.verdict] ?? VERDICT_STYLE.scores_indicative;
  const tr = reliability.training_report;
  const sat = reliability.score_saturation;
  const notes = inputNotes ?? [];
  const trainedOnYourData = reliability.model_source === "trained_on_your_data";
  const saturated = sat && sat.severity === "high";

  const hasDetails =
    notes.length > 0 || !!cutoffInfo || trainedOnYourData ||
    !!(tr && tr.attempted) || !!saturated;

  return (
    <div className={`rounded-sm border ${style.border} ${style.bg} px-5 py-4 mb-6`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${style.dot}`} />
          <div className="min-w-0">
            <p className={`font-body text-[13px] font-semibold ${style.accent}`}>
              {style.label}
            </p>
            <p className="font-body text-[13px] text-ink leading-relaxed mt-0.5">
              {reliability.guidance}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {trainedOnYourData && (
            <span className="font-mono text-[9.5px] uppercase tracking-wide text-gold bg-gold/10 border border-gold/30 rounded-sm px-2 py-1">
              ★ model trained on your data
            </span>
          )}
          {hasDetails && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="font-mono text-[10.5px] text-grey hover:text-navy transition-colors whitespace-nowrap"
            >
              {expanded ? "hide details ▲" : "details ▼"}
            </button>
          )}
        </div>
      </div>

      <AnimatePresence>
        {expanded && hasDetails && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="mt-4 pt-4 border-t border-parchment-line space-y-3">

              {trainedOnYourData && tr && (
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-wide text-grey mb-1">
                    Model
                  </p>
                  <p className="font-body text-[12.5px] text-ink">
                    Trained on {tr.training_pool_size ?? "?"} of your dealers
                    {typeof tr.cv_auc_mean === "number" && (
                      <> · cross-validated AUC{" "}
                        <span className="font-mono">
                          {tr.cv_auc_mean.toFixed(3)}
                          {typeof tr.cv_auc_std === "number" && ` ± ${tr.cv_auc_std.toFixed(3)}`}
                        </span>
                      </>
                    )}
                    {typeof tr.outcome_window_months === "number" &&
                      ` · outcomes measured over the last ${tr.outcome_window_months} months`}
                  </p>
                  {tr.late_threshold_basis && (
                    <p className="font-body text-[12.5px] text-grey mt-1">
                      Counted a dealer as late past{" "}
                      <span className="font-mono">{tr.late_threshold_days}</span> days —{" "}
                      {tr.late_threshold_basis}
                    </p>
                  )}
                </div>
              )}

              {!trainedOnYourData && tr && tr.attempted && !tr.trained && (
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-wide text-grey mb-1">
                    Model
                  </p>
                  <p className="font-body text-[12.5px] text-ink">
                    Scored with the pre-trained model. A model specific to your
                    portfolio was not used because {tr.reason}
                  </p>
                </div>
              )}

              {saturated && sat && (
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-wide text-grey mb-1">
                    Score compression
                  </p>
                  <p className="font-body text-[12.5px] text-ink">
                    {(sat.pct_clipped * 100).toFixed(1)}% of dealers sit at the
                    extreme ends of the scale ({sat.clipped_at_floor} at the floor,{" "}
                    {sat.clipped_at_ceiling} at the ceiling), so the model cannot
                    separate them from one another.
                  </p>
                </div>
              )}

              {cutoffInfo && (
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-wide text-grey mb-1">
                    Payment history used
                  </p>
                  <p className="font-body text-[12.5px] text-ink">
                    Everything up to {cutoffInfo.cutoff_date} — {cutoffInfo.strategy}
                    {cutoffInfo.data_range && ` · your file spans ${cutoffInfo.data_range}`}
                  </p>
                </div>
              )}

              {notes.length > 0 && (
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-wide text-grey mb-1">
                    Columns substituted
                  </p>
                  <ul className="space-y-1">
                    {notes.map((n, i) => (
                      <li key={i} className="font-body text-[12.5px] text-ink">• {n}</li>
                    ))}
                  </ul>
                </div>
              )}

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}