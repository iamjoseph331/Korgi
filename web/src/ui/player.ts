/**
 * Player view: boots the Live2D stage, hooks audio + timing + slides.
 * Extracted from main.ts so setup/progress can coexist in one SPA.
 */

import { loadStage } from "../live2d/loader";
import { makeExpressionDriver } from "../live2d/expressions";
import { attachLipSync } from "../live2d/lipsync";
import { Timeline } from "../player/timeline";
import { SlidePanel } from "./slides";
import type { CharacterJson, RunInfo, SlideCue, TimingEntry } from "../types";

async function fetchJson<T>(url: string): Promise<T | null> {
  const res = await fetch(url);
  if (!res.ok) return null;
  return (await res.json()) as T;
}

function setStep(status: HTMLSpanElement, message: string): void {
  currentStep = message;
  status.textContent = message;
  // eslint-disable-next-line no-console
  console.log(`[player] ${message}`);
}

let booted = false;
let booting = false;
let currentStep = "idle";

export async function bootPlayer(): Promise<void> {
  if (booted || booting) return;
  booting = true;

  const status = document.getElementById("player-status") as HTMLSpanElement;
  const canvas = document.getElementById("live2d-canvas") as HTMLCanvasElement;
  const audio = document.getElementById("audio") as HTMLAudioElement;
  const slideRoot = document.getElementById("slide") as HTMLDivElement;
  try {
    setStep(status, "loading run metadata");
    const info = await fetchJson<RunInfo>("/run/info.json");
    const character = await fetchJson<CharacterJson>("/run/character.json");
    if (!info || !character || !("slug" in info)) {
      status.textContent = "failed to load run metadata";
      return;
    }
    setStep(status, `${info.slug} — ${character.name}`);

    setStep(status, "loading stage");
    const { model, setZoom } = await loadStage(canvas, character.live2d);

    // ── zoom slider ─────────────────────────────────────
    const zoomSlider = document.getElementById("zoom-slider") as HTMLInputElement | null;
    if (zoomSlider) {
      const saved = parseFloat(localStorage.getItem("korgi:zoom") ?? "1");
      if (!Number.isNaN(saved)) {
        zoomSlider.value = String(saved);
        setZoom(saved);
      }
      zoomSlider.addEventListener("input", () => {
        const v = parseFloat(zoomSlider.value);
        setZoom(v);
        localStorage.setItem("korgi:zoom", String(v));
      });
    }
    setStep(status, "binding expressions");
    const applyTag = makeExpressionDriver(model, character.live2d_expression_map);

    if (info.audio_url) {
      setStep(status, "binding audio");
      audio.src = info.audio_url;
      try {
        attachLipSync(model, audio, character.live2d.lip_sync);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("lip sync disabled:", err);
      }
    }

    // ── pause the model while audio is paused; keep eye-blink running ─
    // pixi-live2d-display's internal update loop (motions, physics, breath,
    // AND blink) is bound to `model.autoUpdate`. When the user pauses audio
    // we want everything to freeze *except* blink so the face still feels
    // alive. Drive blink manually via the internal CubismEyeBlink component.
    type BlinkModel = {
      internalModel: {
        coreModel: {
          update: () => void;
          saveParameters?: () => void;
        };
        eyeBlink?: { updateParameters: (core: unknown, dt: number) => void };
      };
    };
    let blinkRaf = 0;
    let lastBlinkT = 0;
    const tickBlink = (t: number) => {
      const dt = lastBlinkT ? (t - lastBlinkT) / 1000 : 0;
      lastBlinkT = t;
      const im = (model as unknown as BlinkModel).internalModel;
      im.eyeBlink?.updateParameters(im.coreModel, dt);
      im.coreModel.update();
      blinkRaf = requestAnimationFrame(tickBlink);
    };
    const startBlink = () => {
      if (blinkRaf) return;
      lastBlinkT = 0;
      blinkRaf = requestAnimationFrame(tickBlink);
    };
    const stopBlink = () => {
      if (!blinkRaf) return;
      cancelAnimationFrame(blinkRaf);
      blinkRaf = 0;
    };
    audio.addEventListener("pause", () => {
      (model as unknown as { autoUpdate: boolean }).autoUpdate = false;
      startBlink();
    });
    audio.addEventListener("play", () => {
      stopBlink();
      (model as unknown as { autoUpdate: boolean }).autoUpdate = true;
    });
    audio.addEventListener("ended", () => {
      (model as unknown as { autoUpdate: boolean }).autoUpdate = false;
      startBlink();
    });

    setStep(status, "loading timing");
    const entries = (await fetchJson<TimingEntry[]>("/run/timing.json")) ?? [];
    setStep(status, "loading slide cues");
    const slideCues = (await fetchJson<SlideCue[]>("/run/slides.json")) ?? [{ idx: 0, start_ms: 0 }];

    const panel = new SlidePanel(slideRoot);
    try {
      setStep(status, "rendering slides");
      await panel.loadMarkdown("/run/slides/slides.md");
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("slide panel failed:", err);
      slideRoot.innerHTML = "<p>No slides available.</p>";
    }

    setStep(status, "starting timeline");
    let timeline = new Timeline(entries, slideCues);
    timeline.onTagChange((tag) => { void applyTag(tag); });
    timeline.onSlideAdvance((idx) => { panel.show(idx); });

    audio.addEventListener("timeupdate", () => {
      timeline.tick(Math.round(audio.currentTime * 1000));
    });

    // ── TTS provider switcher ───────────────────────────
    const ttsSel = document.getElementById("tts-provider") as HTMLSelectElement | null;
    const ttsStatus = document.getElementById("tts-status") as HTMLSpanElement | null;
    if (ttsSel) {
      const providers = info.available_providers ?? [];
      ttsSel.innerHTML = "";
      for (const p of providers) {
        const opt = document.createElement("option");
        opt.value = p;
        opt.textContent = p;
        ttsSel.appendChild(opt);
      }
      if (info.current_provider && providers.includes(info.current_provider)) {
        ttsSel.value = info.current_provider;
      }
      ttsSel.addEventListener("change", async () => {
        const provider = ttsSel.value;
        if (ttsStatus) ttsStatus.textContent = "生成中…";
        ttsSel.disabled = true;
        try {
          const fd = new FormData();
          fd.append("provider", provider);
          const res = await fetch("/api/tts/switch", { method: "POST", body: fd });
          if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
          const body = (await res.json()) as {
            audio_url: string; timing_url: string; slides_url: string | null; cached: boolean;
          };
          const wasPlaying = !audio.paused;
          const t = audio.currentTime;
          audio.src = body.audio_url;
          audio.currentTime = t;
          if (wasPlaying) void audio.play().catch(() => {});

          const [newEntries, newCues] = await Promise.all([
            fetchJson<TimingEntry[]>(body.timing_url),
            body.slides_url
              ? fetchJson<SlideCue[]>(body.slides_url)
              : Promise.resolve(slideCues),
          ]);
          timeline = new Timeline(newEntries ?? [], newCues ?? slideCues);
          timeline.onTagChange((tag) => { void applyTag(tag); });
          timeline.onSlideAdvance((idx) => { panel.show(idx); });

          if (ttsStatus) ttsStatus.textContent = body.cached ? "cached" : "ready";
        } catch (err) {
          // eslint-disable-next-line no-console
          console.error("tts switch failed:", err);
          if (ttsStatus) ttsStatus.textContent = "error";
        } finally {
          ttsSel.disabled = false;
        }
      });
    }

    setStep(status, "ready");
    booted = true;
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error("player boot failed:", err);
    status.textContent = `player error @ ${currentStep}: ${String(err)}`;
  } finally {
    booting = false;
  }
}
