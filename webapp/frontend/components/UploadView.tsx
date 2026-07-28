"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface UploadViewProps {
  onSubmit: (dealers: File, salesmen: File, transactions: File) => void;
  loading: boolean;
  error: string | null;
}

interface SlotProps {
  index: string;
  label: string;
  hint: string;
  file: File | null;
  onSelect: (f: File) => void;
}

function FileSlot({ index, label, hint, file, onSelect }: SlotProps) {
  const [dragging, setDragging] = useState(false);
  const inputId = `file-upload-${label.toLowerCase()}`;

  return (
    <label
      htmlFor={inputId}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onSelect(f);
      }}
      className={`group cursor-pointer flex items-center gap-4 border-b border-parchment-line px-1 py-4 transition-colors last:border-b-0 focus-within:ring-2 focus-within:ring-gold focus-within:ring-offset-2 focus-within:ring-offset-parchment rounded-sm ${
        dragging ? "bg-gold/10" : "hover:bg-navy/[0.025]"
      }`}
    >
      <input
        id={inputId}
        type="file"
        accept=".csv"
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onSelect(f);
        }}
      />
      <span
        className={`font-mono text-[11px] shrink-0 w-6 h-6 rounded-full flex items-center justify-center border transition-colors ${
          file ? "border-gold bg-gold text-navy-deep" : "border-ink/20 text-grey"
        }`}
      >
        {file ? "✓" : index}
      </span>
      <div className="flex-1 min-w-0">
        <p className="font-body text-[14px] font-medium text-ink">{label}</p>
        <p className="font-mono text-[10.5px] text-grey truncate">{hint}</p>
      </div>
      <div className="shrink-0">
        {file ? (
          <span className="font-mono text-[11px] text-navy truncate max-w-[140px] inline-block">
            {file.name}
          </span>
        ) : (
          <span className="font-mono text-[11px] text-grey/60 group-hover:text-navy transition-colors">
            attach →
          </span>
        )}
      </div>
    </label>
  );
}

export default function UploadView({ onSubmit, loading, error }: UploadViewProps) {
  const [dealers, setDealers] = useState<File | null>(null);
  const [salesmen, setSalesmen] = useState<File | null>(null);
  const [transactions, setTransactions] = useState<File | null>(null);

  const ready = dealers && salesmen && transactions;

  return (
    <div className="relative min-h-screen bg-navy overflow-hidden">
      {/* Signature: visible ruled ledger lines, animating slowly upward like
          entries scrolling through a physical register */}
      <motion.div
        className="absolute inset-0 opacity-[0.12]"
        style={{
          backgroundImage:
            "repeating-linear-gradient(to bottom, transparent, transparent 42px, #E0C477 42px, #E0C477 43px)",
        }}
        animate={{ backgroundPositionY: [0, 43] }}
        transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
      />
      <div className="absolute -left-40 top-0 w-[600px] h-[600px] rounded-full bg-gold/[0.07] blur-3xl" />
      <div className="absolute right-0 bottom-0 w-[500px] h-[500px] rounded-full bg-ice/[0.05] blur-3xl" />

      <div className="relative z-10 min-h-screen grid lg:grid-cols-2 gap-0">
        {/* Left: the pitch */}
        <div className="flex items-center px-8 md:px-16 py-20 min-w-0">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: "easeOut" }}
            className="max-w-lg"
          >
            <p className="font-mono text-[11px] tracking-[0.25em] text-gold-bright uppercase mb-5">
              Distributor Credit Risk · The Ledger
            </p>
            <h1 className="font-display text-5xl md:text-6xl font-medium text-white leading-[1.04] mb-6 tracking-tight">
              Every account,
              <br />
              <span className="italic text-ice">weighed against</span>
              <br />
              its own history.
            </h1>
            <p className="font-body text-[16px] text-ice/70 leading-relaxed max-w-md">
              Upload your dealer ledger, salesman roster, and payment
              history. Get back a defensible risk score for every account —
              including the ones your sales team already trusts.
            </p>

            <div className="flex flex-wrap items-center gap-x-6 gap-y-4 mt-10 pt-8 border-t border-white/10">
              <div>
                <p className="font-display text-2xl text-gold-bright">300–900</p>
                <p className="font-mono text-[10px] text-ice/50 uppercase tracking-wide">score range</p>
              </div>
              <div className="hidden sm:block w-px h-8 bg-white/10" />
              <div>
                <p className="font-display text-2xl text-gold-bright">6</p>
                <p className="font-mono text-[10px] text-ice/50 uppercase tracking-wide">Pakistan-specific signals</p>
              </div>
              <div className="hidden sm:block w-px h-8 bg-white/10" />
              <div>
                <p className="font-display text-2xl text-gold-bright">0</p>
                <p className="font-mono text-[10px] text-ice/50 uppercase tracking-wide">black boxes</p>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Right: the ledger page itself, a solid document sitting on the navy */}
        <div className="flex items-center justify-center px-8 md:px-16 py-20 min-w-0">
          <motion.div
            initial={{ opacity: 0, y: 24, rotate: -0.6 }}
            animate={{ opacity: 1, y: 0, rotate: -0.6 }}
            transition={{ duration: 0.7, delay: 0.15, ease: "easeOut" }}
            className="w-full max-w-md bg-parchment rounded-sm shadow-2xl shadow-black/40 px-8 py-9 relative"
          >
            <div className="absolute top-0 left-8 right-8 h-[3px] bg-gradient-to-r from-gold via-gold-bright to-gold rounded-b-sm" />

            <p className="font-mono text-[10px] tracking-[0.15em] text-grey uppercase mb-1">
              New Entry
            </p>
            <h2 className="font-display text-2xl text-ink mb-6">Score a Portfolio</h2>

            <div className="mb-2">
              <FileSlot index="01" label="Dealers" hint="dealer_id, city, sector, credit_limit_pkr…" file={dealers} onSelect={setDealers} />
              <FileSlot index="02" label="Salesmen" hint="salesman_id, salesman_name…" file={salesmen} onSelect={setSalesmen} />
              <FileSlot index="03" label="Transactions" hint="messy exports are fine — we clean them" file={transactions} onSelect={setTransactions} />
            </div>

            <AnimatePresence>
              {error && (
                <motion.p
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="font-body text-[13px] text-red bg-red/10 border border-red/20 rounded-sm px-4 py-3 mt-4"
                >
                  {error}
                </motion.p>
              )}
            </AnimatePresence>

            <button
              disabled={!ready || loading}
              onClick={() => ready && onSubmit(dealers, salesmen, transactions)}
              className="w-full mt-6 rounded-sm bg-gold text-navy-deep font-body font-semibold text-[14px] py-3.5 transition-all disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gold-bright hover:shadow-[0_0_24px_rgba(201,162,75,0.35)] active:scale-[0.99]"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-navy-deep animate-pulse" />
                  Reading the ledger…
                </span>
              ) : (
                "Score the portfolio"
              )}
            </button>

            <p className="font-mono text-[10px] text-grey/70 mt-5 text-center">
              Nothing is stored beyond this session · logistic scorecard, not a black box
            </p>
          </motion.div>
        </div>
      </div>
    </div>
  );
}