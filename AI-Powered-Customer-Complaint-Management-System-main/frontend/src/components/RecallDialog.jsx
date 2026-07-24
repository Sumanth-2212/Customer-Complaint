import { useState } from "react";
import { toast } from "sonner";
import { Siren } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { http } from "@/lib/api";

export default function RecallDialog({
  open,
  onOpenChange,
  batchNumber,
  productName,
  affectedUnits,
  complaintIds,
  onCreated,
}) {
  const [initiator, setInitiator] = useState("");
  const [reason, setReason] = useState("");
  const [units, setUnits] = useState(String(affectedUnits ?? ""));
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!initiator.trim()) {
      toast.error("Please enter your name");
      return;
    }
    setBusy(true);
    try {
      const { data } = await http.post("/recalls", {
        batch_number: batchNumber,
        product_name: productName,
        affected_units: units,
        complaint_ids: complaintIds,
        reason: reason,
        initiated_by: initiator,
      });
      toast.success(`Batch recall #${data.id} initiated`);
      onCreated?.(data);
      onOpenChange(false);
      setInitiator("");
      setReason("");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to initiate recall");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-red-700">
            <Siren className="w-5 h-5" />
            Initiate Batch Recall
          </DialogTitle>
          <DialogDescription>
            This action will mark all complaints for batch{" "}
            <span className="font-mono font-semibold">{batchNumber}</span> as
            "Under Recall" and create a recall record.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-gray-600">
                Batch
              </label>
              <Input value={batchNumber} readOnly className="mt-1 bg-gray-50" />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-600">
                Product
              </label>
              <Input
                value={productName || "—"}
                readOnly
                className="mt-1 bg-gray-50"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-gray-600">
                Affected Units (auto-summed)
              </label>
              <Input
                data-testid="recall-affected-units"
                value={units}
                onChange={(e) => setUnits(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-600">
                Complaints included
              </label>
              <Input
                value={complaintIds.join(", ") || "—"}
                readOnly
                className="mt-1 bg-gray-50"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-gray-600">
              Your name / initials
            </label>
            <Input
              data-testid="recall-initiator"
              value={initiator}
              onChange={(e) => setInitiator(e.target.value)}
              placeholder="e.g. J. Doe (QA Lead)"
              className="mt-1"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-gray-600">
              Reason / notes
            </label>
            <Textarea
              data-testid="recall-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder="Root cause under investigation..."
              className="mt-1 resize-none"
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            data-testid="recall-cancel"
          >
            Cancel
          </Button>
          <Button
            onClick={submit}
            disabled={busy}
            data-testid="recall-submit"
            className="bg-red-600 hover:bg-red-700 text-white"
          >
            {busy ? "Initiating..." : "Initiate Recall"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
