"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Summary } from "@/lib/api";

function useCountUp(target: number, durationMs = 700) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    let start: number | null = null;
    let frame: number;
    const step = (t: number) => {
      if (start === null) start = t;
      const progress = Math.min((t - start) / durationMs, 1);
      setValue(Math.round(progress * target));
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, durationMs]);
  return value;
}

export default function SummaryBar({ summary }: { summary: Summary }) {
  const items = [
    { label: "Accounts Scored", value: useCountUp(summary.total_dealers), color: "text-white" },
    { label: "High Risk", value: useCountUp(summary.red_count), color: "text-red" },
    { label: "Moderate", value: useCountUp(summary.amber_count), color: "text-amber" },
    { label: "Reliable", value: useCountUp(summary.green_count), color: "text-green" },
  ];

  return (
    <div className="bg-navy px-6 md:px-10 py-6">
      <div className="max-w-6xl mx-auto flex flex-wrap items-end justify-between gap-6">
        <div className="flex flex-wrap gap-x-10 gap-y-4">
          {items.map((it) => (
            <div key={it.label}>
              <p className={`font-display text-3xl font-medium ${it.color}`}>{it.value}</p>
              <p className="font-mono text-[10px] uppercase tracking-wide text-ice/50 mt-1">
                {it.label}
              </p>
            </div>
          ))}
        </div>
        {summary.salesman_favorite_red_count > 0 && (
          <motion.div
            animate={{ boxShadow: ["0 0 0px rgba(179,57,44,0)", "0 0 16px rgba(179,57,44,0.35)", "0 0 0px rgba(179,57,44,0)"] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
            className="rounded-sm border border-red/40 bg-red/10 px-4 py-2.5"
          >
            <p className="font-body text-[13px] text-white">
              <span className="font-semibold">{summary.salesman_favorite_red_count}</span> trusted{" "}
              {summary.salesman_favorite_red_count === 1 ? "account" : "accounts"} flagged high risk
            </p>
          </motion.div>
        )}
      </div>
    </div>
  );
}
