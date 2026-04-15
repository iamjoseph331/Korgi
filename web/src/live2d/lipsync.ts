import type { Live2DModel } from "pixi-live2d-display/cubism4";
import type { LipSyncSettings } from "../types";

export function attachLipSync(
  model: Live2DModel,
  audio: HTMLAudioElement,
  settings: LipSyncSettings
): () => void {
  const ctx = new AudioContext();
  const source = ctx.createMediaElementSource(audio);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  source.connect(analyser);
  analyser.connect(ctx.destination);

  const buffer = new Uint8Array(analyser.fftSize);
  const coreModel = (model as unknown as { internalModel: { coreModel: any } }).internalModel.coreModel;
  const mouthOpenIdx = coreModel.getParameterIndex("ParamMouthOpenY");
  const mouthFormIdx = settings.use_mouth_form
    ? coreModel.getParameterIndex("ParamMouthForm")
    : -1;

  let smoothed = 0;
  let raf = 0;

  const tick = () => {
    // Resume context on first gesture.
    if (ctx.state === "suspended") ctx.resume().catch(() => {});
    analyser.getByteTimeDomainData(buffer);
    let sumSq = 0;
    for (let i = 0; i < buffer.length; i++) {
      const v = (buffer[i] - 128) / 128;
      sumSq += v * v;
    }
    const rms = Math.sqrt(sumSq / buffer.length);
    const boosted = Math.min(1, rms * settings.sensitivity);
    const gated = boosted < settings.min_threshold ? 0 : boosted;
    smoothed = smoothed + (gated - smoothed) * (1 - settings.smoothing);

    coreModel.setParameterValueByIndex(mouthOpenIdx, smoothed);
    if (mouthFormIdx >= 0) {
      coreModel.setParameterValueByIndex(mouthFormIdx, 0.3 + smoothed * 0.4);
    }
    raf = requestAnimationFrame(tick);
  };

  raf = requestAnimationFrame(tick);
  return () => {
    cancelAnimationFrame(raf);
    ctx.close().catch(() => {});
  };
}
