"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Dealer, tierOf, recommendedAction, riskCardUrl } from "@/lib/api";

interface Props {
  dealer: Dealer | null;
  sessionId: string;
  onClose: () => void;
}

const tierColor: Record<string, string> = { RED: "text-red", AMBER: "text-amber", GREEN: "text-green" };
const tierBg: Record<string, string> = { RED: "bg-red/10", AMBER: "bg-amber/10", GREEN: "bg-green/10" };

export default function DealerDetail({ dealer, sessionId, onClose }: Props) {
  return (
    <AnimatePresence>
      {dealer && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-navy-deep/40 z-40"
          />
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 260 }}
            className="fixed right-0 top-0 h-full w-full max-w-md bg-parchment border-l border-parchment-line z-50 overflow-y-auto"
          >
            <div className="p-7">
              <button
                onClick={onClose}
                className="font-mono text-[11px] text-grey hover:text-ink mb-6 flex items-center gap-1"
              >
                ← close
              </button>

              <p className="font-mono text-[10px] uppercase tracking-wide text-grey mb-1">
                {dealer.dealer_id} · {dealer.city} · {dealer.sector}
              </p>
              <h2 className="font-display text-2xl text-ink mb-1">{dealer.dealer_name}</h2>
              <p className="font-body text-[13px] text-grey mb-6">
                Salesman: {dealer.salesman_id}
                {dealer.is_salesman_favorite && (
                  <span className="text-red font-medium"> · marked as trusted / favorite account</span>
                )}
              </p>

              <div className={`rounded-sm ${tierBg[tierOf(dealer.risk_flag)]} px-5 py-5 mb-6 flex items-end justify-between`}>
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-wide text-grey mb-1">Credit Score</p>
                  <p className={`font-display text-5xl font-medium ${tierColor[tierOf(dealer.risk_flag)]}`}>
                    {Math.round(dealer.credit_score)}
                  </p>
                  <p className="font-mono text-[10px] text-grey mt-1">out of 300–900</p>
                </div>
                <p className={`font-body font-semibold text-[15px] ${tierColor[tierOf(dealer.risk_flag)]}`}>
                  {dealer.risk_flag}
                </p>
              </div>

              <h3 className="font-display italic text-lg text-ink mb-3">Why this score</h3>
              <div className="space-y-4 mb-7">
                {dealer.top_reasons.map((r, i) => {
                  const maxWeight = Math.abs(dealer.top_reasons[0]?.weight ?? 1) || 1;
                  const barPct = r.weight !== null ? (Math.abs(r.weight) / maxWeight) * 100 : 0;
                  const barColor = r.direction === "increases_risk" ? "bg-red" : r.direction === "reduces_risk" ? "bg-green" : "bg-grey";
                  return (
                    <div key={i} className="border-l-2 border-parchment-line pl-4">
                      <p className="font-body text-[13px] text-ink mb-1.5">
                        {r.direction === "increases_risk" && <span className="text-red">↑ </span>}
                        {r.direction === "reduces_risk" && <span className="text-green">↓ </span>}
                        {r.factor}
                      </p>
                      {r.weight !== null && (
                        <div className="h-1 bg-parchment-line rounded-full overflow-hidden w-full max-w-[180px]">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${barPct}%` }}
                            transition={{ duration: 0.5, delay: 0.1 + i * 0.08, ease: "easeOut" }}
                            className={`h-full rounded-full ${barColor}`}
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <h3 className="font-display italic text-lg text-ink mb-3">Recommended action</h3>
              <p className="font-body text-[13px] text-ink leading-relaxed bg-white/60 border border-parchment-line rounded-sm px-4 py-3.5 mb-6">
                {recommendedAction(tierOf(dealer.risk_flag), dealer.is_salesman_favorite)}
              </p>

              
              <a
                href={riskCardUrl(sessionId, dealer.dealer_id)}
                className="flex items-center justify-center gap-2 w-full rounded-sm border border-gold text-navy font-body font-medium text-[13px] py-3 hover:bg-gold/10 transition-colors"
              >
                Download Risk Card (.docx)
              </a>

              <p className="font-mono text-[10px] text-grey/70 mt-8 leading-relaxed">
                This score is generated from historical payment behavior only and
                does not replace human judgment. Tier reflects the model&apos;s
                relative ranking within this portfolio.
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
