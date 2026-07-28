"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Logged so a real issue is visible in server/deployment logs, not just
    // silently swallowed by the fallback UI below.
    console.error("Unhandled error caught by error boundary:", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-navy flex items-center justify-center px-6">
      <div className="max-w-md w-full bg-parchment rounded-sm shadow-2xl shadow-black/40 px-8 py-9 text-center">
        <p className="font-mono text-[10px] tracking-[0.15em] text-red uppercase mb-3">
          Something Went Wrong
        </p>
        <h1 className="font-display text-2xl text-ink mb-3">
          The ledger hit a snag
        </h1>
        <p className="font-body text-[14px] text-grey leading-relaxed mb-7">
          This wasn&apos;t caused by your data — it&apos;s an issue in the
          application itself. Trying again usually resolves it; if it keeps
          happening, the uploaded files or backend connection may need a look.
        </p>
        <button
          onClick={reset}
          className="w-full rounded-sm bg-gold text-navy-deep font-body font-semibold text-[14px] py-3 hover:bg-gold-bright transition-colors"
        >
          Try again
        </button>
        {error.digest && (
          <p className="font-mono text-[10px] text-grey/60 mt-5">
            Reference: {error.digest}
          </p>
        )}
      </div>
    </div>
  );
}