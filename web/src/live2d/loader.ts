import * as PIXI from "pixi.js";
import type { Live2DSettings } from "../types";
import type { Live2DModel as Live2DModelType } from "pixi-live2d-display/cubism4";

let live2dModelPromise: Promise<typeof import("pixi-live2d-display/cubism4").Live2DModel> | null = null;

async function getLive2DModel() {
  if (!live2dModelPromise) {
    // pixi-live2d-display expects PIXI on window during module init.
    (window as unknown as { PIXI: typeof PIXI }).PIXI = PIXI;
    live2dModelPromise = import("pixi-live2d-display/cubism4").then((mod) => {
      mod.Live2DModel.registerTicker(PIXI.Ticker);
      return mod.Live2DModel;
    });
  }
  return live2dModelPromise;
}

export interface LoadedStage {
  app: PIXI.Application;
  model: Live2DModelType;
  setZoom: (factor: number) => void;
  getZoom: () => number;
}

export async function loadStage(
  canvas: HTMLCanvasElement,
  settings: Live2DSettings
): Promise<LoadedStage> {
  const Live2DModel = await getLive2DModel();
  const parent = canvas.parentElement;
  const app = new PIXI.Application({
    view: canvas,
    autoStart: true,
    resizeTo: parent ?? window,
    backgroundAlpha: 0,
    antialias: true,
  });

  const model = await Live2DModel.from(settings.model_path, {
    autoInteract: false,
  });
  model.anchor.set(0.5, 0.5);
  app.stage.addChild(model as unknown as PIXI.DisplayObject);
  app.start();

  let zoom = 1;

  const layoutModel = () => {
    const width = parent?.clientWidth || window.innerWidth;
    const height = parent?.clientHeight || window.innerHeight;
    app.renderer.resize(width, height);
    const s = settings.scale * zoom;
    model.scale.set(s, s);
    model.x = app.renderer.width / 2 + settings.x_offset;
    // As zoom increases, shift the model down so its head/upper body
    // drifts toward the vertical center instead of disappearing off-top.
    const upperBodyShift = (zoom - 1) * app.renderer.height * 0.35;
    model.y = app.renderer.height / 2 + settings.y_offset + upperBodyShift;
    app.render();
  };

  layoutModel();
  requestAnimationFrame(layoutModel);

  window.addEventListener("resize", layoutModel);

  const setZoom = (factor: number) => {
    zoom = Math.max(1, Math.min(2.5, factor));
    layoutModel();
  };

  return { app, model, setZoom, getZoom: () => zoom };
}
