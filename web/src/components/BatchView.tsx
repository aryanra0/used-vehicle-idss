"use client";

import { useState } from "react";
import { UploadCloud, AlertTriangle } from "lucide-react";
import { Card, SectionLabel, Badge, Select } from "@/components/ui/primitives";
import { Assumptions, BatchResponse, evaluateBatch } from "@/lib/api";
import { cn, currency, percent } from "@/lib/utils";

export function BatchView({ assumptions }: { assumptions: Assumptions }) {
  const [data, setData] = useState<BatchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [objective, setObjective] = useState("profit");
  const [fileName, setFileName] = useState<string>("");

  async function onFile(file: File) {
    setFileName(file.name);
    setLoading(true);
    setError(null);
    try {
      setData(await evaluateBatch(file, assumptions, objective));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <SectionLabel>Bulk evaluation</SectionLabel>
            <p className="text-sm text-slate-500">
              Upload a CSV of listings (columns: make, model, year, odometer, condition;
              optional: body, transmission, state, color, mmr, listing_price).
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Rank by</span>
            <Select
              options={["profit", "roi", "risk"]}
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
            />
          </div>
        </div>

        <label className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50/60 px-6 py-10 text-center transition hover:border-brand-400 hover:bg-brand-50/40">
          <UploadCloud className="mb-2 text-brand-500" size={28} />
          <span className="text-sm font-medium text-slate-700">
            {fileName || "Click to upload a CSV"}
          </span>
          <span className="mt-1 text-xs text-slate-400">
            Processes valid rows and reports errors for the rest
          </span>
          <input
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
          />
        </label>
        {loading && <p className="mt-3 text-sm text-brand-600">Evaluating…</p>}
        {error && <p className="mt-3 text-sm text-pass">{error}</p>}
      </Card>

      {data && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <Stat label="Evaluated" value={String(data.summary.evaluated)} />
            <Stat label="Buy" value={String(data.summary.buy)} tone="buy" />
            <Stat label="Errors" value={String(data.summary.errors)} tone="pass" />
          </div>

          <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <Th>Vehicle</Th>
                    <Th>Verdict</Th>
                    <Th>Conf.</Th>
                    <Th>Resale</Th>
                    <Th>Max price</Th>
                    <Th>Profit</Th>
                    <Th>ROI</Th>
                    <Th>Days band</Th>
                    <Th>Risk</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((row) => (
                    <tr
                      key={row.row}
                      className="border-b border-slate-100 transition hover:bg-brand-50/40"
                    >
                      <Td className="font-medium capitalize text-slate-800">
                        {row.year} {row.make} {row.model}
                      </Td>
                      <Td>
                        <Badge tone={row.recommendation === "Buy" ? "buy" : "pass"}>
                          {row.recommendation}
                        </Badge>
                      </Td>
                      <Td className="font-mono">{percent(row.confidence, 0)}</Td>
                      <Td className="font-mono">{currency(row.predicted_resale)}</Td>
                      <Td className="font-mono">{currency(row.max_purchase_price)}</Td>
                      <Td
                        className={cn(
                          "font-mono",
                          row.expected_gross_profit >= 0 ? "text-buy" : "text-pass"
                        )}
                      >
                        {currency(row.expected_gross_profit)}
                      </Td>
                      <Td className="font-mono">{percent(row.roi)}</Td>
                      <Td>{row.days_to_sell_band}</Td>
                      <Td>{row.risk_level}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {data.errors.length > 0 && (
            <Card>
              <SectionLabel>
                <span className="flex items-center gap-1 text-caution">
                  <AlertTriangle size={13} /> Skipped rows
                </span>
              </SectionLabel>
              <ul className="space-y-1 text-sm text-slate-600">
                {data.errors.map((e) => (
                  <li key={e.row}>
                    Row {e.row}: <span className="text-pass">{e.error}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "buy" | "pass";
}) {
  return (
    <Card className="card-gradient">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </div>
      <div
        className={cn(
          "mt-1 font-mono text-2xl font-bold",
          tone === "buy" && "text-buy",
          tone === "pass" && "text-pass",
          !tone && "text-slate-900"
        )}
      >
        {value}
      </div>
    </Card>
  );
}

const Th = ({ children }: { children: React.ReactNode }) => (
  <th className="px-4 py-3 font-semibold">{children}</th>
);
const Td = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => <td className={cn("px-4 py-3", className)}>{children}</td>;
