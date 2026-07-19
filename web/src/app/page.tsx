"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Car, LayoutGrid, Loader2 } from "lucide-react";
import {
  Assumptions,
  DEFAULT_ASSUMPTIONS,
  EvaluationResult,
  Options,
  VehicleInput,
  evaluate,
  fetchOptions,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { InputRail } from "@/components/InputRail";
import { VerdictCard } from "@/components/VerdictCard";
import { PriceComparison } from "@/components/PriceComparison";
import {
  FinancialSummary,
  PredictionConfidenceCard,
  RiskSummary,
  TopFactors,
} from "@/components/Summaries";
import { BatchView } from "@/components/BatchView";
import { DataQualityFlag } from "@/lib/api";

const DEFAULT_VEHICLE: VehicleInput = {
  year: 2015,
  make: "kia",
  model: "sorento",
  odometer: 25000,
  condition: 75, // 0-100 UI scale (converted to the model's 1-49 grade on submit)
  body: "suv",
  transmission: "automatic",
  state: "ca",
  color: "white",
  listing_price: 15000,
};

export default function Home() {
  const [tab, setTab] = useState<"evaluate" | "batch">("evaluate");
  const [options, setOptions] = useState<Options | null>(null);
  const [vehicle, setVehicle] = useState<VehicleInput>(DEFAULT_VEHICLE);
  const [assumptions, setAssumptions] = useState<Assumptions>(DEFAULT_ASSUMPTIONS);
  const [result, setResult] = useState<EvaluationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetchOptions().then(setOptions).catch(() => setError("Could not reach the API. Is it running on :8000?"));
  }, []);

  const run = useCallback(async (v: VehicleInput, a: Assumptions) => {
    if (!v.make || !v.model) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await evaluate(v, a));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounced live recompute whenever inputs change.
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => run(vehicle, assumptions), 350);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [vehicle, assumptions, run]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <Header tab={tab} setTab={setTab} loading={loading} />

      {error && (
        <div className="mb-4 rounded-lg border border-pass-ring bg-pass-soft px-4 py-2 text-sm text-pass">
          {error}
        </div>
      )}

      {tab === "evaluate" ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[380px_1fr]">
          <InputRail
            options={options}
            vehicle={vehicle}
            setVehicle={setVehicle}
            assumptions={assumptions}
            setAssumptions={setAssumptions}
          />
          <div className="space-y-6">
            {result ? (
              <>
                {result.coverage_warning && (
                  <div className="flex items-start gap-2 rounded-xl border border-caution-ring bg-caution-soft px-4 py-3 text-sm text-caution">
                    <span className="mt-0.5 font-bold">!</span>
                    <span>{result.coverage_warning}</span>
                  </div>
                )}
                {result.data_quality_flags?.map((f, i) => (
                  <FlagBanner key={i} flag={f} />
                ))}
                <VerdictCard r={result} />
                <PriceComparison r={result} listingPrice={vehicle.listing_price ?? null} />
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                  <FinancialSummary r={result} />
                  <RiskSummary r={result} />
                </div>
                <PredictionConfidenceCard r={result} />
                <TopFactors r={result} />
              </>
            ) : (
              <div className="card flex h-64 items-center justify-center text-slate-400">
                {loading ? "Evaluating…" : "Enter a vehicle to see a recommendation"}
              </div>
            )}
          </div>
        </div>
      ) : (
        <BatchView assumptions={assumptions} />
      )}

      <footer className="mt-10 text-center text-xs text-slate-400">
        Decision support only — estimates value at the wholesale level from 2014–2015 auction
        data. A human buyer makes the final call.
      </footer>
    </main>
  );
}

function Header({
  tab,
  setTab,
  loading,
}: {
  tab: "evaluate" | "batch";
  setTab: (t: "evaluate" | "batch") => void;
  loading: boolean;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          <span className="text-gradient">Used Vehicle IDSS</span>
        </h1>
        <p className="text-sm text-slate-500">
          Should you buy this car, and what&apos;s the most you should pay?
        </p>
      </div>
      <div className="flex items-center gap-3">
        {loading && <Loader2 className="animate-spin text-brand-500" size={18} />}
        <div className="inline-flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
          <TabButton active={tab === "evaluate"} onClick={() => setTab("evaluate")}>
            <Car size={15} /> Evaluate
          </TabButton>
          <TabButton active={tab === "batch"} onClick={() => setTab("batch")}>
            <LayoutGrid size={15} /> Batch
          </TabButton>
        </div>
      </div>
    </header>
  );
}

function FlagBanner({ flag }: { flag: DataQualityFlag }) {
  const styles: Record<DataQualityFlag["severity"], string> = {
    alert: "border-pass-ring bg-pass-soft text-pass",
    warn: "border-caution-ring bg-caution-soft text-caution",
    info: "border-slate-200 bg-slate-50 text-slate-600",
  };
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-xl border px-4 py-3 text-sm",
        styles[flag.severity] ?? styles.info
      )}
    >
      <span className="mt-0.5 font-bold">{flag.severity === "alert" ? "⚠" : "!"}</span>
      <span>{flag.message}</span>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition",
        active
          ? "bg-brand-600 text-white shadow-sm"
          : "text-slate-600 hover:bg-slate-100"
      )}
    >
      {children}
    </button>
  );
}
