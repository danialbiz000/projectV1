"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MarketMetricPoint } from "@/lib/api";

const gridColor = "rgba(148, 163, 184, 0.25)";

export function PriceTrendChart({ series }: { series: MarketMetricPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={series} margin={{ left: 8, right: 8, top: 8 }}>
        <defs>
          <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2a7de1" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#2a7de1" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={gridColor} vertical={false} />
        <XAxis dataKey="period" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(0, 7)} />
        <YAxis
          tick={{ fontSize: 11 }}
          width={56}
          tickFormatter={(v) => `${Math.round(Number(v) / 100) / 10}k`}
        />
        <Tooltip
          formatter={(value) => [`${Number(value).toLocaleString("it-IT")} €/m²`, "Prezzo medio"]}
          labelFormatter={(label) => `Mese: ${String(label).slice(0, 7)}`}
        />
        <Area
          type="monotone"
          dataKey="avg_price_sqm"
          name="€/m² medio"
          stroke="#2a7de1"
          strokeWidth={2}
          fill="url(#priceFill)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function VolumeChart({ series }: { series: MarketMetricPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={series} margin={{ left: 8, right: 8, top: 8 }}>
        <CartesianGrid stroke={gridColor} vertical={false} />
        <XAxis dataKey="period" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(0, 7)} />
        <YAxis tick={{ fontSize: 11 }} width={40} />
        <Tooltip labelFormatter={(label) => `Mese: ${String(label).slice(0, 7)}`} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="new_listings" name="Nuovi annunci" fill="#22a06b" radius={[3, 3, 0, 0]} />
        <Bar dataKey="removed_listings" name="Rimossi" fill="#e2664c" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
