/**
 * Progress view: listen to SSE and render a stage checklist + live log.
 * On `done` event, call onDone so the router can switch to the player.
 */

interface ServerEvent {
  kind: "stage" | "log" | "warn" | "done" | "error";
  message: string;
  payload?: Record<string, unknown>;
}

const STAGES: Array<{ id: string; label: string }> = [
  { id: "resume",  label: "Stage 1 — レジュメ生成" },
  { id: "speech",  label: "Stage 2 — スピーチ原稿 + 感情タグ" },
  { id: "slides",  label: "Stage 4 — スライド生成" },
  { id: "tts",     label: "TTS — 音声合成" },
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
  const progressSection = document.getElementById("view-progress") as HTMLElement;

  runIdEl.textContent = `run: ${runId}`;
  stagesEl.innerHTML = "";
  logEl.innerHTML = "";

  let shell = progressSection.querySelector(".progress-shell") as HTMLDivElement | null;
  let eyecatch = progressSection.querySelector(".progress-eyecatch") as HTMLDivElement | null;
  if (!shell) {
    shell = document.createElement("div");
    shell.className = "progress-shell";
    stagesEl.parentElement?.insertBefore(shell, stagesEl);
    shell.appendChild(stagesEl);
  }
  if (!eyecatch) {
    eyecatch = document.createElement("div");
    eyecatch.className = "progress-eyecatch";
    eyecatch.innerHTML = `
      <img class="progress-eyecatch-img" src="/assets/loading/Ponchon.png" alt="Loading character" />
    `;
    shell.appendChild(eyecatch);
  }

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
          const when = prev.querySelector(".when");
          if (when && !when.textContent) when.textContent = now();
        }
      }
      node.classList.remove("done", "err");
      node.classList.add("active");
      activeStage = id;
    } else if (state === "done") {
      node.classList.remove("active", "err");
      node.classList.add("done");
      const when = node.querySelector(".when");
      if (when) when.textContent = now();
      if (activeStage === id) activeStage = null;
    } else {
      node.classList.remove("active", "done");
      node.classList.add("err");
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
