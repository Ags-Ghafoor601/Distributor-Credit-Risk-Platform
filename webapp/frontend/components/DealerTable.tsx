"use client";

import { useMemo, useState } from "react";
import { Dealer, tierOf } from "@/lib/api";

interface Props {
  dealers: Dealer[];
  onSelect: (d: Dealer) => void;
  selectedId?: string;
}

type SortKey = "credit_score" | "dealer_name" | "city";
type TierFilter = "ALL" | "RED" | "AMBER" | "GREEN";

const tierStyle: Record<string, string> = {
  RED: "bg-red/10 text-red border-red/30",
  AMBER: "bg-amber/10 text-amber border-amber/30",
  GREEN: "bg-green/10 text-green border-green/30",
};

export default function DealerTable({ dealers, onSelect, selectedId }: Props) {
  const [query, setQuery] = useState("");
  const [tierFilter, setTierFilter] = useState<TierFilter>("ALL");
  const [sortKey, setSortKey] = useState<SortKey>("credit_score");
  const [favoritesOnly, setFavoritesOnly] = useState(false);

  const filtered = useMemo(() => {
    let rows = dealers;
    if (tierFilter !== "ALL") rows = rows.filter((d) => tierOf(d.risk_flag) === tierFilter);
    if (favoritesOnly) rows = rows.filter((d) => d.is_salesman_favorite);
    if (query.trim()) {
      const q = query.toLowerCase();
      rows = rows.filter(
        (d) =>
          d.dealer_name.toLowerCase().includes(q) ||
          d.dealer_id.toLowerCase().includes(q) ||
          d.city.toLowerCase().includes(q)
      );
    }
    return [...rows].sort((a, b) => {
      if (sortKey === "credit_score") return a.credit_score - b.credit_score;
      if (sortKey === "dealer_name") return a.dealer_name.localeCompare(b.dealer_name);
      return a.city.localeCompare(b.city);
    });
  }, [dealers, query, tierFilter, sortKey, favoritesOnly]);

  return (
    <div className="bg-white/60 border border-parchment-line rounded-sm">
      <div className="flex flex-wrap items-center gap-3 px-5 py-4 border-b border-parchment-line">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search dealer, city, or ID…"
          className="font-body text-[13px] bg-transparent border border-parchment-line rounded-sm px-3 py-1.5 outline-none focus:border-navy/40 flex-1 min-w-[180px]"
        />
        <select
          value={tierFilter}
          onChange={(e) => setTierFilter(e.target.value as TierFilter)}
          className="font-mono text-[11px] bg-transparent border border-parchment-line rounded-sm px-2 py-1.5 outline-none"
        >
          <option value="ALL">All tiers</option>
          <option value="RED">Red only</option>
          <option value="AMBER">Amber only</option>
          <option value="GREEN">Green only</option>
        </select>
        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
          className="font-mono text-[11px] bg-transparent border border-parchment-line rounded-sm px-2 py-1.5 outline-none"
        >
          <option value="credit_score">Sort: score (risky first)</option>
          <option value="dealer_name">Sort: name</option>
          <option value="city">Sort: city</option>
        </select>
        <label className="flex items-center gap-1.5 font-mono text-[11px] text-grey cursor-pointer select-none">
          <input
            type="checkbox"
            checked={favoritesOnly}
            onChange={(e) => setFavoritesOnly(e.target.checked)}
            className="accent-gold"
          />
          favorites only
        </label>
      </div>

      <div className="max-h-[480px] overflow-y-auto overflow-x-auto">
        <table className="w-full text-left min-w-[560px]">
          <thead className="sticky top-0 bg-parchment/95 backdrop-blur-sm">
            <tr className="font-mono text-[10px] uppercase tracking-wide text-grey">
              <th className="px-5 py-2.5 font-medium">Dealer</th>
              <th className="px-3 py-2.5 font-medium">City</th>
              <th className="px-3 py-2.5 font-medium">Salesman</th>
              <th className="px-3 py-2.5 font-medium text-right">Score</th>
              <th className="px-5 py-2.5 font-medium">Tier</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((d) => {
              const tier = tierOf(d.risk_flag);
              const selected = d.dealer_id === selectedId;
              return (
                <tr
                  key={d.dealer_id}
                  onClick={() => onSelect(d)}
                  className={`cursor-pointer border-t border-parchment-line transition-colors ${
                    selected ? "bg-ice/40" : "hover:bg-navy/[0.03]"
                  }`}
                >
                  <td className="px-5 py-3">
                    <p className="font-body text-[13px] text-ink">{d.dealer_name}</p>
                    {d.is_salesman_favorite && (
                      <span className="font-mono text-[9px] uppercase tracking-wide text-gold bg-gold/10 border border-gold/30 rounded-sm px-1.5 py-0.5">
                        ★ favorite
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-3 font-body text-[13px] text-grey">{d.city}</td>
                  <td className="px-3 py-3 font-body text-[13px] text-grey">{d.salesman_id}</td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2 justify-end">
                      <span className="font-mono text-[13px] text-ink">{Math.round(d.credit_score)}</span>
                      <div className="w-10 h-1 bg-parchment-line rounded-full overflow-hidden shrink-0">
                        <div
                          className={`h-full rounded-full ${tier === "RED" ? "bg-red" : tier === "AMBER" ? "bg-amber" : "bg-green"}`}
                          style={{ width: `${((d.credit_score - 300) / (900 - 300)) * 100}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`inline-block font-mono text-[10px] uppercase tracking-wide border rounded-sm px-2 py-0.5 ${tierStyle[tier]}`}
                    >
                      {tier}
                    </span>
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-10 text-center font-body text-[13px] text-grey">
                  No accounts match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
