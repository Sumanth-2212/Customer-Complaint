import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, FileText, RefreshCw, Clock, Loader2 } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { http, API } from "@/lib/api";
import SeverityHeatmap from "@/components/SeverityHeatmap";

function severityBadge(severity) {
  const map = {
    Critical: "bg-red-50 text-red-700 border-red-200",
    High: "bg-orange-50 text-orange-700 border-orange-200",
    Medium: "bg-amber-50 text-amber-700 border-amber-200",
    Low: "bg-emerald-50 text-emerald-700 border-emerald-200",
  };
  const cls = map[severity] || "bg-gray-50 text-gray-600 border-gray-200";
  return (
    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${cls}`}>
      {severity || "—"}
    </span>
  );
}

export default function HistoryDrawer({ trigger }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await http.get("/complaints", { params: { limit: 10 } });
      setItems(data);
    } catch (err) {
      toast.error("Failed to load history");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) load();
  }, [open]);

  const downloadPdf = (id) => {
    const url = `${API}/complaints/${id}/pdf`;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>{trigger}</SheetTrigger>
      <SheetContent
        side="right"
        className="w-full sm:max-w-md p-0 flex flex-col bg-white"
      >
        <SheetHeader className="px-6 py-4 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <SheetTitle className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-600" />
              Recent Complaints
            </SheetTitle>
            <button
              onClick={load}
              className="text-gray-500 hover:text-blue-600 transition-colors"
              data-testid="history-refresh"
              aria-label="Refresh"
            >
              <RefreshCw
                className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
              />
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Last 10 complaints — spot repeat batches at a glance.
          </p>
        </SheetHeader>

        <div className="px-4 pt-4">
          <SeverityHeatmap />
        </div>

        <div className="flex-1 overflow-y-auto chat-scroll px-4 py-3 space-y-3">
          {loading && !items.length ? (
            <div className="flex items-center justify-center py-16 text-gray-400 text-sm">
              <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Loading…
            </div>
          ) : items.length === 0 ? (
            <div className="text-center text-sm text-gray-400 py-16">
              No complaints saved yet.
            </div>
          ) : (
            items.map((c) => (
              <div
                key={c.id}
                data-testid={`history-item-${c.id}`}
                className="border border-gray-200 rounded-lg p-3 hover:border-blue-200 hover:bg-blue-50/30 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-gray-900 truncate">
                      {c.product_name || "Unnamed product"}
                      {c.product_strength ? ` · ${c.product_strength}` : ""}
                    </div>
                    <div className="text-xs text-gray-500 truncate">
                      {c.customer_name || "Unknown customer"} ·{" "}
                      {c.complaint_type || "—"}
                    </div>
                  </div>
                  {severityBadge(c.initial_severity)}
                </div>
                <div className="flex items-center justify-between mt-2">
                  <div className="text-[11px] text-gray-500 font-mono">
                    Batch {c.batch_number || "—"} · #{c.id}
                  </div>
                  <button
                    onClick={() => downloadPdf(c.id)}
                    data-testid={`history-pdf-${c.id}`}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" /> PDF
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="border-t border-gray-100 px-6 py-3 text-[11px] text-gray-400 flex items-center gap-2">
          <FileText className="w-3.5 h-3.5" />
          PDFs open in a new tab — printable QA record with signatures.
        </div>
      </SheetContent>
    </Sheet>
  );
}
