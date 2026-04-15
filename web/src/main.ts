/**
 * Three-view SPA with hash routing:
 *   #/             → setup (PDF upload + pipeline options)
 *   #/run/<id>     → progress (SSE stream)
 *   #/player       → live2d player (reads /run/*)
 *
 * On load, if a run is already active (classic `korgi serve <dir>` mode)
 * we jump straight to the player.
 */

import { mountSetup } from "./ui/setup";
import { mountProgress } from "./ui/progress";
import { bootPlayer } from "./ui/player";

const VIEWS = ["setup", "progress", "player"] as const;
type View = typeof VIEWS[number];

function showView(v: View): void {
  for (const name of VIEWS) {
    const el = document.getElementById(`view-${name}`);
    if (el) (el as HTMLElement).hidden = name !== v;
  }
}

function parseHash(): { view: View; runId?: string } {
  const h = location.hash || "#/";
  const m = h.match(/^#\/run\/([^/]+)/);
  if (m) return { view: "progress", runId: decodeURIComponent(m[1]) };
  if (h.startsWith("#/player")) return { view: "player" };
  return { view: "setup" };
}

function navigate(hash: string): void {
  if (location.hash === hash) window.dispatchEvent(new HashChangeEvent("hashchange"));
  else location.hash = hash;
}

let disposeProgress: (() => void) | null = null;
let setupMounted = false;

async function render(): Promise<void> {
  if (disposeProgress) { disposeProgress(); disposeProgress = null; }

  const { view, runId } = parseHash();
  const statusEl = document.getElementById("status") as HTMLSpanElement;

  if (view === "setup") {
    showView("setup");
    statusEl.textContent = "ready";
    if (!setupMounted) {
      setupMounted = true;
      await mountSetup((id) => navigate(`#/run/${encodeURIComponent(id)}`));
    }
    return;
  }

  if (view === "progress" && runId) {
    showView("progress");
    statusEl.textContent = `running — ${runId}`;
    disposeProgress = mountProgress(runId, () => {
      // Small delay so the user can read the final ✓ line.
      setTimeout(() => navigate("#/player"), 800);
    });
    return;
  }

  if (view === "player") {
    showView("player");
    statusEl.textContent = "player";
    await bootPlayer();
    return;
  }
}

async function init(): Promise<void> {
  // If a run is already active (classic mode: `korgi serve <dir>`), skip setup.
  if (!location.hash || location.hash === "#" || location.hash === "#/") {
    try {
      const res = await fetch("/run/info.json");
      if (res.ok) {
        const info = (await res.json()) as { active?: boolean; slug?: string };
        if (info.active || info.slug) {
          location.hash = "#/player";
        }
      }
    } catch { /* stay on setup */ }
  }
  window.addEventListener("hashchange", () => { void render(); });
  await render();
}

void init().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  const statusEl = document.getElementById("status");
  if (statusEl) statusEl.textContent = `boot error: ${String(err)}`;
});
