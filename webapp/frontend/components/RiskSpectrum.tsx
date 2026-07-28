"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Dealer, tierOf } from "@/lib/api";

interface Props {
  dealers: Dealer[];
  onSelect: (d: Dealer) => void;
  selectedId?: string;
}

const MIN = 300;
const MAX = 900;

function pct(score: number) {
  return ((score - MIN) / (MAX - MIN)) * 100;
}

const tierColor: Record<string, string> = {
  RED: "var(--red)",
  AMBER: "var(--amber)",
  GREEN: "var(--green)",
};

export default function RiskSpectrum({ dealers, onSelect, selectedId }: Props) {
  const [hovered, setHovered] = useState<Dealer | null>(null);

  return (
    <div className="bg-white/60 border border-parchment-line rounded-sm px-6 py-7">
      <div className="flex items-baseline justify-between mb-6">
        <h2 className="font-display text-lg italic text-ink">The Spectrum</h2>
        <p className="font-mono text-[10px] text-grey uppercase tracking-wide">
          {dealers.length} accounts, scored 300–900
        </p>
      </div>

      {/* Zone labels */}
      <div className="relative h-2 rounded-full overflow-hidden flex mb-1 mt-14">
        <div className="bg-red/25" style={{ width: `${pct(580) - pct(300)}%` }} />
        <div className="bg-amber/25" style={{ width: `${pct(700) - pct(580)}%` }} />
        <div className="bg-green/25" style={{ width: `${pct(900) - pct(700)}%` }} />

        {/* Dealer dots, absolutely positioned along the line, rendered above via negative margin trick below */}
      </div>

      <div className="relative h-0">
        {dealers.map((d, i) => {
          const tier = tierOf(d.risk_flag);
          const isSelected = d.dealer_id === selectedId;
          return (
            <motion.button
              key={d.dealer_id}
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.004, 0.6), duration: 0.3 }}
              onClick={() => onSelect(d)}
              onMouseEnter={() => setHovered(d)}
              onMouseLeave={() => setHovered(null)}
              style={{
                left: `${pct(d.credit_score)}%`,
                top: "-28px",
                backgroundColor: tierColor[tier],
              }}
              className={`absolute -translate-x-1/2 rounded-full transition-all cursor-pointer ${
                isSelected
                  ? "w-3.5 h-3.5 ring-2 ring-gold ring-offset-2 ring-offset-parchment z-20"
                  : d.is_salesman_favorite && tier === "RED"
                  ? "w-2.5 h-2.5 ring-2 ring-navy/50 z-10"
                  : "w-1.5 h-1.5 opacity-70 hover:opacity-100 hover:scale-150 z-0"
              }`}
            />
          );
        })}

        <AnimatePresence>
          {hovered && (
            <motion.div
              initial={{ opacity: 0, y: 4, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 4, scale: 0.96 }}
              transition={{ duration: 0.12 }}
              style={{ left: `${pct(hovered.credit_score)}%`, top: "-72px" }}
              className="absolute -translate-x-1/2 z-30 pointer-events-none whitespace-nowrap bg-navy-deep text-white rounded-sm px-3 py-2 shadow-lg"
            >
              <p className="font-body text-[12px] font-medium">{hovered.dealer_name}</p>
              <p className="font-mono text-[10px] text-gold-bright">
                {Math.round(hovered.credit_score)} · {hovered.city}
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="flex justify-between font-mono text-[10px] text-grey mt-4">
        <span>300</span>
        <span className="text-red/70">580</span>
        <span className="text-amber/70">700</span>
        <span>900</span>
      </div>

      <div className="flex items-center gap-5 mt-5 pt-5 border-t border-parchment-line">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full ring-2 ring-navy/50 inline-block bg-red" />
          <span className="font-mono text-[10px] text-grey">salesman-favorite, flagged high risk</span>
        </div>
      </div>
    </div>
  );
}
