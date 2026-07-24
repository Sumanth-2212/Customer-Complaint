import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { http } from "@/lib/api";

const COLORS = {
  Low: "#10b981", // emerald-500
  Medium: "#f59e0b", // amber-500
  High: "#f97316", // orange-500
  Critical: "#dc2626", // red-600
};

function TooltipContent({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="rounded-md border border-gray-200 bg-white shadow-md px-2.5 py-2 text-xs">
      <div className="font-semibold text-gray-900">{label}</div>
      {payload
        .filter((p) => p.value > 0)
        .map((p) => (
          <div key={p.dataKey} className="flex items-center gap-2 mt-0.5">
            <span
              className="w-2 h-2 rounded-sm"
              style={{ backgroundColor: p.color }}
            />
            <span className="text-gray-600 capitalize">{p.dataKey}</span>
            <span className="font-semibold text-gray-900 ml-auto">
              {p.value}
            </span>
          </div>
        ))}
    </div>
  );
}

export default function SeverityHeatmap() {
  const [data, setData] = useState([]);
  const [totals, setTotals] = useState({
    Low: 0,
    Medium: 0,
    High: 0,
    Critical: 0,
  });

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const { data: res } = await http.get("/complaints/severity-summary", {
          params: { days: 30 },
        });
        if (ignore) return;
        setData(
          res.series.map((r) => ({
            date: r.date.slice(5), // MM-DD for chart labels
            Low: r.Low,
            Medium: r.Medium,
            High: r.High,
            Critical: r.Critical,
          })),
        );
        setTotals(res.totals);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const total =
    (totals.Low || 0) +
    (totals.Medium || 0) +
    (totals.High || 0) +
    (totals.Critical || 0);

  return (
    <div className="border border-gray-200 rounded-lg p-3" data-testid="severity-heatmap">
      <div className="flex items-center justify-between mb-1">
        <div>
          <div className="text-xs font-semibold text-gray-800">
            Severity Trends
          </div>
          <div className="text-[10px] text-gray-500">
            Last 30 days · {total} complaint{total === 1 ? "" : "s"}
          </div>
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          {["Low", "Medium", "High", "Critical"].map((k) => (
            <div key={k} className="flex items-center gap-1 text-gray-600">
              <span
                className="w-2 h-2 rounded-sm"
                style={{ backgroundColor: COLORS[k] }}
              />
              {totals[k] || 0}
            </div>
          ))}
        </div>
      </div>
      <div style={{ width: "100%", height: 90 }}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 9, fill: "#94a3b8" }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
              minTickGap={20}
            />
            <YAxis hide />
            <Tooltip content={<TooltipContent />} cursor={{ fill: "#f1f5f9" }} />
            <Bar dataKey="Low" stackId="a" fill={COLORS.Low} />
            <Bar dataKey="Medium" stackId="a" fill={COLORS.Medium} />
            <Bar dataKey="High" stackId="a" fill={COLORS.High} />
            <Bar dataKey="Critical" stackId="a" fill={COLORS.Critical} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
