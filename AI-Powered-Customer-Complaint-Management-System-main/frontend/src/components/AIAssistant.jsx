import { useEffect, useRef, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { toast } from "sonner";
import {
  UploadCloud,
  FileText,
  Info,
  Sparkles,
  Send,
  Bot,
  History,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  addChat,
  setExtraction,
} from "@/store";
import { chatWithAssistant } from "@/lib/api";
import { streamExtraction } from "@/lib/stream";
import HistoryDrawer from "@/components/HistoryDrawer";

const ACCEPT = ".pdf,.docx,.txt,.eml";
const MAX_MB = 10;

export default function AIAssistant() {
  const dispatch = useDispatch();
  const form = useSelector((s) => s.complaint.form);
  const extraction = useSelector((s) => s.complaint.extraction);
  const chat = useSelector((s) => s.complaint.chat);

  const fileInputRef = useRef(null);
  const chatScrollRef = useRef(null);

  const [dragActive, setDragActive] = useState(false);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pastedText, setPastedText] = useState("");
  const [chatText, setChatText] = useState("");
  const [chatBusy, setChatBusy] = useState(false);

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [chat.length]);

  const runExtract = async (mode, payload) => {
    try {
      await streamExtraction(mode, payload, dispatch);
      // build a quick summary from Redux state after stream finishes
      dispatch(
        addChat({
          role: "assistant",
          text:
            "Extraction complete. Review the auto-filled fields on the left, then save the complaint.",
        }),
      );
      toast.success("Fields extracted and populated");
    } catch (err) {
      dispatch(
        setExtraction({ status: "error", progress: 0, message: "Extraction failed" }),
      );
      const msg = err?.message || "Extraction failed";
      toast.error(msg);
      dispatch(addChat({ role: "assistant", text: `Error: ${msg}` }));
    }
  };

  const handleFiles = (files) => {
    if (!files || !files.length) return;
    const file = files[0];
    const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
    if (!ACCEPT.split(",").includes(ext)) {
      toast.error(`Unsupported file type: ${ext}`);
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      toast.error(`File exceeds ${MAX_MB}MB limit`);
      return;
    }
    runExtract("file", file);
  };

  const handlePasteSubmit = () => {
    if (!pastedText.trim()) {
      toast.error("Paste some complaint text first");
      return;
    }
    setPasteOpen(false);
    runExtract("text", pastedText);
    setPastedText("");
  };

  const sendChat = async () => {
    const msg = chatText.trim();
    if (!msg || chatBusy) return;
    dispatch(addChat({ role: "user", text: msg }));
    setChatText("");
    setChatBusy(true);
    try {
      const { reply } = await chatWithAssistant(msg, form);
      dispatch(addChat({ role: "assistant", text: reply }));
    } catch (err) {
      dispatch(
        addChat({
          role: "assistant",
          text: `Sorry, chat failed: ${
            err?.response?.data?.detail || err.message
          }`,
        }),
      );
    } finally {
      setChatBusy(false);
    }
  };

  const showProgress =
    extraction.status === "extracting" || extraction.status === "done";

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-blue-600" />
          <h2 className="text-[15px] font-semibold text-gray-900">
            AI Complaint Intake Assistant
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <HistoryDrawer
            trigger={
              <button
                type="button"
                data-testid="btn-open-history"
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-gray-500 hover:text-blue-600 border border-gray-200 hover:border-blue-200 rounded-md px-2 py-1 transition-colors"
                aria-label="Open recent complaints"
              >
                <History className="w-3.5 h-3.5" />
                History
              </button>
            }
          />
          <span
            data-testid="badge-beta"
            className="inline-flex items-center px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 text-[10px] font-bold tracking-wider border border-blue-100"
          >
            BETA
          </span>
        </div>
      </div>

      {/* Upload zone */}
      <div
        data-testid="dropzone"
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg px-4 py-6 flex items-center gap-4 cursor-pointer transition-colors ${
          dragActive
            ? "border-blue-400 bg-blue-50/60"
            : "border-gray-200 hover:border-blue-300 hover:bg-blue-50/30"
        }`}
      >
        <UploadCloud className="w-9 h-9 text-gray-400 shrink-0" />
        <div className="text-sm text-gray-700 leading-snug">
          <div>Drag &amp; drop complaint document here</div>
          <div className="text-gray-500">
            or{" "}
            <span className="text-blue-600 font-semibold hover:underline">
              click to browse
            </span>
          </div>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          data-testid="file-input"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* OR divider */}
      <div className="flex items-center gap-3 my-4">
        <div className="flex-1 h-px bg-gray-200" />
        <span className="text-xs font-medium text-gray-400">OR</span>
        <div className="flex-1 h-px bg-gray-200" />
      </div>

      {/* Paste text button */}
      <Dialog open={pasteOpen} onOpenChange={setPasteOpen}>
        <DialogTrigger asChild>
          <button
            type="button"
            data-testid="btn-paste-text"
            className="w-full flex items-center justify-center gap-2 h-10 rounded-md border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <FileText className="w-4 h-4 text-gray-500" />
            Paste Complaint Text / Email
          </button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Paste Complaint Text or Email</DialogTitle>
          </DialogHeader>
          <Textarea
            data-testid="paste-textarea"
            value={pastedText}
            onChange={(e) => setPastedText(e.target.value)}
            placeholder="Paste the full email or complaint text here..."
            rows={10}
            className="resize-none"
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setPasteOpen(false)}
              data-testid="btn-paste-cancel"
            >
              Cancel
            </Button>
            <Button
              onClick={handlePasteSubmit}
              data-testid="btn-paste-submit"
              className="bg-blue-600 hover:bg-blue-700"
            >
              Extract
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Supported formats info */}
      <div
        data-testid="info-formats"
        className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-emerald-800 text-xs flex items-start gap-2"
      >
        <Info className="w-4 h-4 mt-0.5 shrink-0" />
        <div>
          <div>
            <span className="font-semibold">Supported formats:</span> PDF, DOCX,
            TXT, EML
          </div>
          <div>Max file size: 10MB</div>
        </div>
      </div>

      {/* Extraction progress */}
      {showProgress ? (
        <div className="mt-6" data-testid="progress-block">
          <div className="text-[11px] font-bold tracking-[0.15em] text-gray-500 uppercase mb-2">
            Extraction Progress
          </div>
          <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-600 rounded-full transition-all duration-300"
              style={{ width: `${extraction.progress}%` }}
              data-testid="progress-bar"
            />
          </div>
          <div className="flex items-center justify-between mt-2">
            <p className="text-xs text-gray-600">{extraction.message}</p>
            <span className="text-xs font-semibold text-gray-700">
              {extraction.progress}%
            </span>
          </div>
          {extraction.status === "extracting" ? (
            <p className="text-xs text-gray-500 mt-1">
              Please wait, this may take a few moments.
            </p>
          ) : null}
        </div>
      ) : null}

      {/* AI Assistant chat card */}
      <div className="mt-6">
        <div className="text-[11px] font-bold tracking-[0.15em] text-gray-500 uppercase mb-2">
          AI Assistant
        </div>
        <div
          ref={chatScrollRef}
          className="chat-scroll rounded-lg border border-blue-100 bg-blue-50/60 p-3 space-y-2 overflow-y-auto"
          style={{ maxHeight: 220, minHeight: 140 }}
          data-testid="chat-history"
        >
          {chat.map((m, i) => (
            <div
              key={i}
              className={`flex gap-2 ${
                m.role === "user" ? "justify-end" : ""
              }`}
            >
              {m.role === "assistant" ? (
                <div className="w-7 h-7 rounded-md bg-white border border-blue-100 flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 text-blue-600" />
                </div>
              ) : null}
              <div
                className={`text-sm leading-relaxed whitespace-pre-wrap px-3 py-2 rounded-md max-w-[85%] ${
                  m.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-800 border border-blue-100"
                }`}
              >
                {m.text}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Chat input */}
      <div className="mt-auto pt-4">
        <div className="flex items-center gap-2 border border-gray-200 rounded-md bg-white px-3 py-1.5 focus-within:border-blue-400 focus-within:ring-1 focus-within:ring-blue-200 transition-colors">
          <input
            type="text"
            data-testid="chat-input"
            value={chatText}
            onChange={(e) => setChatText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") sendChat();
            }}
            placeholder="Ask me anything about this complaint..."
            className="flex-1 bg-transparent outline-none text-sm placeholder:text-gray-400"
          />
          <button
            type="button"
            onClick={sendChat}
            disabled={chatBusy || !chatText.trim()}
            data-testid="chat-send"
            className="w-8 h-8 rounded-md bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white flex items-center justify-center transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-[11px] text-gray-400 text-center mt-2">
          AI responses may contain errors. Please verify information.
        </p>
      </div>
    </div>
  );
}
