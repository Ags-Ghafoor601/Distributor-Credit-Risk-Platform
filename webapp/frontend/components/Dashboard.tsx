"use client";

import { useState } from "react";
import { ScoreResponse, exportCsvUrl } from "@/lib/api";
import SummaryBar from "./SummaryBar";
import RiskSpectrum from "./RiskSpectrum";
import DealerTable from "./DealerTable";
import DealerDetail from "./DealerDetail";
import ReliabilityBanner from "./ReliabilityBanner";
import type { Dealer } from "@/lib/api";

export default function Dashboard({ data, onReset }: { data: ScoreResponse; onReset: () => void }) {
  const [selected, setSelected] = useState<Dealer | null>(null);
  const q = data.quality_report;

  return (
    <div className="min-h-screen bg-parchment">
      <SummaryBar summary={data.summary} />

      <div className="max-w-6xl mx-auto px-6 md:px-10 py-8">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <button
            onClick={onReset}
            className="font-mono text-[11px] text-grey hover:text-navy transition-colors"
          >
            ← score another portfolio
          </button>
          <a
            href={exportCsvUrl(data.session_id)}
            className="font-body text-[13px] font-semibold bg-gold text-navy-deep rounded-sm px-4 py-2 hover:bg-gold-bright hover:shadow-[0_0_20px_rgba(201,162,75,0.3)] transition-all"
          >
            Download full risk table (CSV)
          </a>
        </div>
        <ReliabilityBanner
          reliability={data.reliability}
          cutoffInfo={data.cutoff_info}
          inputNotes={data.input_notes}
        />
        {q.retention_rate < 1 && (
          <div className="mb-6 border border-amber/30 bg-amber/5 rounded-sm px-5 py-3.5">
            <p className="font-body text-[13px] text-ink">
              <span className="font-semibold">{Math.round(q.retention_rate * 100)}% of uploaded rows</span>{" "}
              were used ({q.output_rows} of {q.input_rows}). Rows were dropped for: missing dealer codes
              ({q.dropped_missing_dealer}), unrecognized dealer codes ({q.dropped_orphan_dealer}),
              unparseable dates ({q.dropped_bad_dates}), unparseable amounts ({q.dropped_bad_amount}),
              ambiguous bounce flags ({q.dropped_bad_bounce_flag}), or logical inconsistencies
              ({q.dropped_logical_inconsistency}).
            </p>
          </div>
        )}

        <div className="mb-8">
          <RiskSpectrum dealers={data.dealers} onSelect={setSelected} selectedId={selected?.dealer_id} />
        </div>

        <DealerTable dealers={data.dealers} onSelect={setSelected} selectedId={selected?.dealer_id} />
      </div>

      <DealerDetail dealer={selected} sessionId={data.session_id} onClose={() => setSelected(null)} />
    </div>
  );
}
