import { API, http } from "@/lib/api";
import { populateForm, setExtraction, setField } from "@/store";

/**
 * Streams extracted fields into Redux one by one via Server-Sent Events.
 * mode: "file" | "text"
 */
export async function streamExtraction(mode, payload, dispatch) {
  dispatch(
    setExtraction({
      status: "extracting",
      progress: 5,
      message: "Streaming extraction from AI...",
    }),
  );

  const fd = new FormData();
  if (mode === "file") fd.append("file", payload);
  else fd.append("text", payload);

  const res = await fetch(`${API}/complaints/extract/stream`, {
    method: "POST",
    body: fd,
  });

  if (!res.ok || !res.body) {
    const detail = await res
      .json()
      .then((j) => j.detail)
      .catch(() => `HTTP ${res.status}`);
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let seen = 0;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    // Split on double newline (SSE frame boundary)
    let idx;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 2);
      if (!frame.startsWith("data:")) continue;
      const jsonStr = frame.slice(5).trim();
      if (!jsonStr) continue;
      let event;
      try {
        event = JSON.parse(jsonStr);
      } catch {
        continue;
      }
      if (event.type === "field") {
        dispatch(setField({ key: event.key, value: event.value }));
        seen += 1;
        const pct = Math.min(10 + seen * 7, 92);
        dispatch(
          setExtraction({
            progress: pct,
            message: `Extracting ${event.key.replace(/_/g, " ")}...`,
          }),
        );
      } else if (event.type === "error") {
        throw new Error(event.message || "Extraction error");
      } else if (event.type === "done") {
        dispatch(
          setExtraction({
            status: "done",
            progress: 100,
            message: "Extraction complete. Fields populated.",
          }),
        );
        return;
      }
    }
  }

  dispatch(
    setExtraction({
      status: "done",
      progress: 100,
      message: "Extraction complete.",
    }),
  );
}

export async function duplicateCheck(batch) {
  if (!batch || !batch.trim()) return { count: 0, matches: [] };
  const { data } = await http.get("/complaints/duplicate-check", {
    params: { batch },
  });
  return data;
}

// re-export helpers used elsewhere
export { populateForm };
