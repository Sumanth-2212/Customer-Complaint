import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { toast } from "sonner";
import { AlertTriangle, RotateCcw, Save, Siren } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { resetForm, setField, setSavedId } from "@/store";
import { saveComplaint } from "@/lib/api";
import { duplicateCheck } from "@/lib/stream";
import EvidencePanel from "@/components/EvidencePanel";
import RecallDialog from "@/components/RecallDialog";

const PLACEHOLDER = "Awaiting AI extraction...";

const labelCls = "text-[13px] font-semibold text-gray-800";
const sectionNumCls =
  "text-[11px] font-bold tracking-[0.15em] text-gray-400 uppercase mb-4";
const inputCls =
  "h-10 rounded-md border-gray-200 bg-white text-sm placeholder:text-gray-400 focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:border-blue-500";

function Field({ children }) {
  return <div className="space-y-1.5">{children}</div>;
}

function TextField({ id, label, type = "text", suffix = null }) {
  const dispatch = useDispatch();
  const value = useSelector((s) => s.complaint.form[id]);
  return (
    <Field>
      <label htmlFor={id} className={labelCls}>
        {label}
      </label>
      <div className="relative">
        <Input
          id={id}
          data-testid={`field-${id}`}
          type={type}
          value={value}
          placeholder={PLACEHOLDER}
          onChange={(e) =>
            dispatch(setField({ key: id, value: e.target.value }))
          }
          className={`${inputCls} ${suffix ? "pr-10" : ""}`}
        />
        {suffix ? (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-500 font-medium">
            {suffix}
          </span>
        ) : null}
      </div>
    </Field>
  );
}

function SelectField({ id, label, options }) {
  const dispatch = useDispatch();
  const value = useSelector((s) => s.complaint.form[id]);
  return (
    <Field>
      <label htmlFor={id} className={labelCls}>
        {label}
      </label>
      <Select
        value={value || undefined}
        onValueChange={(v) => dispatch(setField({ key: id, value: v }))}
      >
        <SelectTrigger
          id={id}
          data-testid={`field-${id}`}
          className={`${inputCls} data-[placeholder]:text-gray-400`}
        >
          <SelectValue placeholder={PLACEHOLDER} />
        </SelectTrigger>
        <SelectContent>
          {options.map((opt) => (
            <SelectItem key={opt} value={opt}>
              {opt}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
}

function SectionHeader({ number, title }) {
  return (
    <div className={sectionNumCls} data-testid={`section-${number}`}>
      {number}. {title}
    </div>
  );
}

export default function ComplaintForm() {
  const dispatch = useDispatch();
  const form = useSelector((s) => s.complaint.form);
  const savedId = useSelector((s) => s.complaint.savedId);
  const batchNumber = form.batch_number;
  const [duplicates, setDuplicates] = useState([]);
  const [totalAffected, setTotalAffected] = useState(0);
  const [recallOpen, setRecallOpen] = useState(false);

  // Debounced duplicate check whenever batch_number changes
  useEffect(() => {
    const value = (batchNumber || "").trim();
    if (!value) {
      setDuplicates([]);
      setTotalAffected(0);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const res = await duplicateCheck(value);
        setDuplicates(res.matches || []);
        setTotalAffected(res.total_quantity_affected || 0);
      } catch {
        setDuplicates([]);
        setTotalAffected(0);
      }
    }, 400);
    return () => clearTimeout(t);
  }, [batchNumber]);

  const handleReset = () => {
    dispatch(resetForm());
    setDuplicates([]);
    setTotalAffected(0);
    toast.success("Form reset");
  };

  const handleSave = async () => {
    try {
      const saved = await saveComplaint(form);
      dispatch(setSavedId(saved.id));
      toast.success(`Complaint #${saved.id} saved`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to save complaint");
    }
  };

  const recallEligible = duplicates.length >= 3;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 pb-6 border-b border-gray-100">
        <div>
          <h1
            className="text-[28px] leading-tight font-bold text-gray-900 tracking-tight"
            data-testid="page-title"
          >
            Log Customer Complaint
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            API &amp; FDF Quality Assurance Module
          </p>
        </div>
        <span
          data-testid="badge-pending-triage"
          className="inline-flex items-center px-3 py-1 rounded-md border border-amber-200 bg-amber-50 text-amber-700 text-xs font-semibold whitespace-nowrap"
        >
          {savedId ? `Saved · #${savedId}` : "Pending Triage"}
        </span>
      </div>

      {/* Section 1 */}
      <section className="pt-6">
        <SectionHeader number="1" title="ORIGIN & CUSTOMER DETAILS" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5">
          <TextField id="complaint_source" label="Complaint Source" />
          <TextField id="customer_name" label="Customer Name" />
        </div>
      </section>

      {/* Section 2 */}
      <section className="pt-8">
        <SectionHeader number="2" title="PRODUCT & BATCH IDENTIFICATION" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5">
          <TextField id="product_name" label="Product Name" />
          <TextField id="product_strength" label="Product Strength/Grade" />
          <TextField id="batch_number" label="Batch/Lot Number" />
          <TextField
            id="manufacturing_date"
            label="Manufacturing Date"
            type="date"
          />
          <TextField id="expiry_date" label="Expiry Date" type="date" />
          <TextField id="quantity_affected" label="Quantity Affected" suffix="kg" />
        </div>
        {duplicates.length > 0 ? (
          <div
            data-testid="duplicate-warning"
            className={`mt-4 rounded-md border px-3 py-2.5 text-xs flex items-start gap-2 ${
              recallEligible
                ? "border-red-200 bg-red-50 text-red-800"
                : "border-amber-200 bg-amber-50 text-amber-800"
            }`}
          >
            <AlertTriangle
              className={`w-4 h-4 mt-0.5 shrink-0 ${
                recallEligible ? "text-red-600" : "text-amber-600"
              }`}
            />
            <div className="flex-1 min-w-0">
              <div className="font-semibold">
                {recallEligible
                  ? `Recall threshold reached — ${duplicates.length} complaints already open for batch “${batchNumber}”.`
                  : `Duplicate batch detected — ${duplicates.length} existing complaint${
                      duplicates.length > 1 ? "s" : ""
                    } for batch “${batchNumber}”.`}
              </div>
              <ul className="mt-1.5 space-y-1">
                {duplicates.slice(0, 3).map((d) => (
                  <li key={d.id} className="opacity-90">
                    #{d.id} · {d.customer_name || "Unknown"} ·{" "}
                    {d.complaint_type || "—"} · {d.status}
                  </li>
                ))}
              </ul>
              {recallEligible ? (
                <button
                  type="button"
                  data-testid="btn-initiate-recall"
                  onClick={() => setRecallOpen(true)}
                  className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-red-600 hover:bg-red-700 text-white text-xs font-semibold shadow-sm transition-colors"
                >
                  <Siren className="w-3.5 h-3.5" />
                  Initiate Batch Recall
                  <span className="ml-1 opacity-90">
                    ({totalAffected} units)
                  </span>
                </button>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>

      {/* Section 3 */}
      <section className="pt-8">
        <SectionHeader number="3" title="COMPLAINT DETAILS" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5">
          <TextField id="complaint_type" label="Complaint Type" />
          <TextField id="complaint_date" label="Complaint Date" type="date" />
        </div>
        <div className="mt-5">
          <label htmlFor="complaint_description" className={labelCls}>
            Detailed Complaint Description
          </label>
          <Textarea
            id="complaint_description"
            data-testid="field-complaint_description"
            value={form.complaint_description}
            onChange={(e) =>
              dispatch(
                setField({ key: "complaint_description", value: e.target.value }),
              )
            }
            placeholder={PLACEHOLDER}
            rows={4}
            className="mt-1.5 rounded-md border-gray-200 text-sm placeholder:text-gray-400 focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:border-blue-500 resize-none"
          />
        </div>
      </section>

      {/* Section 4 */}
      <section className="pt-8">
        <SectionHeader number="4" title="INITIAL ASSESSMENT & PRIORITY" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5">
          <SelectField
            id="initial_severity"
            label="Initial Severity"
            options={["Low", "Medium", "High", "Critical"]}
          />
          <SelectField
            id="priority"
            label="Priority"
            options={["Low", "Medium", "High", "Urgent"]}
          />
        </div>
      </section>

      {/* Section 5 (evidence) — appears only after save */}
      <EvidencePanel complaintId={savedId} />

      {/* Recall dialog */}
      <RecallDialog
        open={recallOpen}
        onOpenChange={setRecallOpen}
        batchNumber={batchNumber}
        productName={form.product_name}
        affectedUnits={totalAffected}
        complaintIds={duplicates.map((d) => d.id)}
        onCreated={() => {
          // Re-run duplicate check to refresh statuses
          if (batchNumber) {
            duplicateCheck(batchNumber).then((res) => {
              setDuplicates(res.matches || []);
              setTotalAffected(res.total_quantity_affected || 0);
            });
          }
        }}
      />

      {/* Actions */}
      <div className="flex items-center justify-between pt-8 mt-auto">
        <Button
          type="button"
          variant="outline"
          onClick={handleReset}
          data-testid="btn-reset-form"
          className="h-10 rounded-md border-gray-300 text-gray-700 hover:bg-gray-50 font-medium"
        >
          <RotateCcw className="w-4 h-4 mr-2" />
          Reset Form
        </Button>
        <Button
          type="button"
          onClick={handleSave}
          data-testid="btn-save-complaint"
          className="h-10 rounded-md bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-sm px-5"
        >
          <Save className="w-4 h-4 mr-2" />
          Save Complaint
        </Button>
      </div>
    </div>
  );
}
