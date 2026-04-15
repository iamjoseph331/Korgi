/**
 * Progress view: listen to SSE and render a stage checklist + live log.
 * On `done` event, call onDone so the router can switch to the player.
 */

interface ServerEvent {
  kind: "stage" | "log" | "warn" | "done" | "error";
  message: string;
  payload?: Record<string, unknown>;
}

const STAGES: Array<{ id: string; label: string; gif: number }> = [
  { id: "resume",  label: "Stage 1 — レジュメ生成",           gif: 1 },
  { id: "speech",  label: "Stage 2 — スピーチ原稿 + 感情タグ", gif: 2 },
  { id: "slides",  label: "Stage 4 — スライド生成",           gif: 3 },
  { id: "tts",     label: "TTS — 音声合成",                   gif: 4 },
];

function now(): string {
  const d = new Date();
  return d.toTimeString().slice(0, 8);
}

export function mountProgress(
  runId: string,
  onDone: (payload: Record<string, unknown>) => void,
): () => void {
  const runIdEl = document.getElementById("progress-runid") as HTMLParagraphElement;
  const stagesEl = document.getElementById("stages") as HTMLDivElement;
  const logEl = document.getElementById("log") as HTMLDivElement;

  runIdEl.textContent = `run: ${runId}`;
  stagesEl.innerHTML = "";
  logEl.innerHTML = "";

  const stageNodes = new Map<string, HTMLDivElement>();
  for (const s of STAGES) {
    const node = document.createElement("div");
    node.className = "stage";
    node.innerHTML = `
      <div class="pill"></div>
      <div class="label">${s.label}</div>
      <div class="when"></div>
    `;
    stagesEl.appendChild(node);
    stageNodes.set(s.id, node);
  }

  function appendLog(kind: string, text: string): void {
    const p = document.createElement("p");
    p.className = `line ${kind}`;
    p.textContent = `[${now()}] ${text}`;
    logEl.appendChild(p);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function removeGif(node: HTMLDivElement): void {
    node.querySelector(".stage-gif")?.remove();
  }

  function addGif(node: HTMLDivElement, stageId: string): void {
    if (node.querySelector(".stage-gif")) return;
    const stage = STAGES.find((s) => s.id === stageId);
    const n = stage?.gif ?? 0;
    const img = document.createElement("img");
    img.className = "stage-gif";
    img.alt = "";
    img.src = n ? `/assets/loading/stage${n}.gif` : "/assets/loading/default.gif";
    img.addEventListener("error", () => { img.src = "/assets/loading/default.gif"; });
    node.insertBefore(img, node.firstChild);
  }

  let activeStage: string | null = null;
  function markStage(id: string, state: "active" | "done" | "err"): void {
    const node = stageNodes.get(id);
    if (!node) return;
    if (state === "active") {
      if (activeStage && activeStage !== id) {
        const prev = stageNodes.get(activeStage);
        if (prev) {
          prev.classList.remove("active");
          prev.classList.add("done");
          removeGif(prev);
          const when = prev.querySelector(".when");
          if (when && !when.textContent) when.textContent = now();
        }
      }
      node.classList.remove("done", "err");
      node.classList.add("active");
      addGif(node, id);
      activeStage = id;
    } else if (state === "done") {
      node.classList.remove("active", "err");
      node.classList.add("done");
      removeGif(node);
      const when = node.querySelector(".when");
      if (when) when.textContent = now();
      if (activeStage === id) activeStage = null;
    } else {
      node.classList.remove("active", "done");
      node.classList.add("err");
      removeGif(node);
    }
  }

  function handle(ev: ServerEvent): void {
    if (ev.kind === "stage") {
      const id = (ev.payload?.stage as string) ?? "";
      if (STAGES.some((s) => s.id === id)) markStage(id, "active");
      appendLog("", `▶ ${ev.message}`);
    } else if (ev.kind === "log") {
      appendLog("", ev.message);
    } else if (ev.kind === "warn") {
      appendLog("warn", `⚠ ${ev.message}`);
    } else if (ev.kind === "error") {
      appendLog("err", `✗ ${ev.message}`);
      if (activeStage) markStage(activeStage, "err");
    } else if (ev.kind === "done") {
      if (activeStage) markStage(activeStage, "done");
      for (const s of STAGES) {
        const node = stageNodes.get(s.id);
        if (node && !node.classList.contains("done") && !node.classList.contains("err")) {
          // Leave un-triggered stages neutral (e.g. --no-slides skips "slides").
        }
      }
      appendLog("done", `✓ ${ev.message}`);
      onDone(ev.payload ?? {});
    }
  }

  const es = new EventSource(`/api/runs/${encodeURIComponent(runId)}/events`);
  es.onmessage = (msg) => {
    try {
      handle(JSON.parse(msg.data) as ServerEvent);
    } catch (err) {
      appendLog("err", `bad event: ${String(err)}`);
    }
  };
  es.onerror = () => {
    // EventSource auto-retries; just note it.
    appendLog("warn", "(stream disconnected — retrying)");
  };

  return () => es.close();
}
