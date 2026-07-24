import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Paperclip, Trash2, Loader2, FileText, ImageIcon } from "lucide-react";
import { API, http } from "@/lib/api";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.csv,.docx,.xlsx";
const MAX_MB = 10;

function iconFor(mime = "") {
  if (mime.startsWith("image/")) return ImageIcon;
  return FileText;
}

function kb(bytes) {
  if (!bytes) return "0 KB";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

export default function EvidencePanel({ complaintId }) {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);

  const load = async () => {
    if (!complaintId) return;
    try {
      const { data } = await http.get(`/complaints/${complaintId}/evidence`);
      setItems(data);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    if (complaintId) load();
    else setItems([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [complaintId]);

  const upload = async (file) => {
    if (!complaintId) return;
    const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
    if (!ACCEPT.split(",").includes(ext)) {
      toast.error(`Unsupported file type: ${ext}`);
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      toast.error(`File exceeds ${MAX_MB}MB`);
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    setBusy(true);
    try {
      await http.post(`/complaints/${complaintId}/evidence`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Evidence attached");
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    if (!complaintId) return;
    try {
      await http.delete(`/complaints/${complaintId}/evidence/${id}`);
      toast.success("Evidence removed");
      setItems((prev) => prev.filter((x) => x.id !== id));
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Delete failed");
    }
  };

  if (!complaintId) return null;

  return (
    <section className="pt-8" data-testid="evidence-panel">
      <div className="text-[11px] font-bold tracking-[0.15em] text-gray-400 uppercase mb-4">
        5. Evidence Attachments
      </div>
      <div
        onClick={() => inputRef.current?.click()}
        className="border-2 border-dashed border-gray-200 hover:border-blue-300 hover:bg-blue-50/30 rounded-lg px-4 py-5 flex items-center gap-3 cursor-pointer transition-colors"
      >
        {busy ? (
          <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
        ) : (
          <Paperclip className="w-6 h-6 text-gray-400" />
        )}
        <div className="text-sm text-gray-700 leading-snug">
          <div>Attach photos or lab reports for complaint #{complaintId}</div>
          <div className="text-xs text-gray-500">
            Images and docs up to 10MB — inlined into the PDF export.
          </div>
        </div>
        <input
          ref={inputRef}
          type="file"
          data-testid="evidence-input"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload(f);
            e.target.value = "";
          }}
        />
      </div>

      {items.length > 0 ? (
        <ul className="mt-4 space-y-2" data-testid="evidence-list">
          {items.map((ev) => {
            const Icon = iconFor(ev.mime_type);
            const url = `${API}/complaints/${complaintId}/evidence/${ev.id}/file`;
            return (
              <li
                key={ev.id}
                className="flex items-center gap-3 border border-gray-200 rounded-md px-3 py-2 hover:bg-gray-50 transition-colors"
                data-testid={`evidence-item-${ev.id}`}
              >
                <Icon className="w-4 h-4 text-blue-600 shrink-0" />
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 min-w-0 text-sm text-gray-800 hover:text-blue-700 truncate"
                >
                  {ev.filename}
                </a>
                <span className="text-xs text-gray-500 whitespace-nowrap">
                  {kb(ev.size_bytes)}
                </span>
                <button
                  type="button"
                  onClick={() => remove(ev.id)}
                  data-testid={`evidence-delete-${ev.id}`}
                  className="text-gray-400 hover:text-red-600 transition-colors"
                  aria-label="Delete evidence"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}
