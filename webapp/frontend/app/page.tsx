"use client";

import { useState } from "react";
import UploadView from "@/components/UploadView";
import Dashboard from "@/components/Dashboard";
import { scorePortfolio, ScoreResponse, ApiError } from "@/lib/api";

export default function Home() {
  const [data, setData] = useState<ScoreResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(dealers: File, salesmen: File, transactions: File) {
    setLoading(true);
    setError(null);
    try {
      const result = await scorePortfolio(dealers, salesmen, transactions);
      setData(result);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong while scoring the portfolio.");
    } finally {
      setLoading(false);
    }
  }

  if (data) {
    return <Dashboard data={data} onReset={() => setData(null)} />;
  }

  return <UploadView onSubmit={handleSubmit} loading={loading} error={error} />;
}
