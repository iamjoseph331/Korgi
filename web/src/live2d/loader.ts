import * as PIXI from "pixi.js";
import type { Live2DSettings } from "../types";
import type { Live2DModel as Live2DModelType } from "pixi-live2d-display/cubism4";

let live2dModelPromise: Promise<typeof import("pixi-live2d-display/cubism4").Live2DModel> | null = null;
let cubismPatched = false;

async function getLive2DModel() {
  if (!live2dModelPromise) {
    // pixi-live2d-display expects PIXI on window during module init.
    (window as unknown as { PIXI: typeof PIXI }).PIXI = PIXI;
    live2dModelPromise = import("pixi-live2d-display/cubism4").then((mod) => {
      if (!cubismPatched) {
        cubismPatched = true;

        const proto = mod.CubismClippingManager_WebGL.prototype as {
          setupLayoutBounds(usingClipCount: number): void;
          _clippingContextListForMask: Array<{
            _layoutChannelNo: number;
            _layoutBounds: { x: number; y: number; width: number; height: number };
          }>;
        };

        proto.setupLayoutBounds = function setupLayoutBoundsPatched(usingClipCount: number): void {
          const colorChannelCount = 4;
          const div = Math.floor(usingClipCount / colorChannelCount);
          const modCount = usingClipCount % colorChannelCount;
          let curClipIndex = 0;

          for (let channelNo = 0; channelNo < colorChannelCount; channelNo++) {
            const layoutCount = div + (channelNo < modCount ? 1 : 0);
            if (layoutCount <= 0) continue;

            const grid = Math.ceil(Math.sqrt(layoutCount));
            const cellSize = 1 / grid;

            for (let i = 0; i < layoutCount; i++) {
              const xpos = i % grid;
              const ypos = Math.floor(i / grid);
              const cc = this._clippingContextListForMask[curClipIndex++];
              cc._layoutChannelNo = channelNo;
              cc._layoutBounds.x = xpos * cellSize;
              cc._layoutBounds.y = ypos * cellSize;
              cc._layoutBounds.width = cellSize;
              cc._layoutBounds.height = cellSize;
            }
          }
        };
      }

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
    autoStart: false,
    resizeTo: parent ?? window,
    backgroundAlpha: 0,
    antialias: true,
  });

  const layoutStage = () => {
    const width = parent?.clientWidth || window.innerWidth;
    const height = parent?.clientHeight || window.innerHeight;
    app.renderer.resize(width, height);
  };

  layoutStage();

  const model = await Live2DModel.from(settings.model_path, {
    autoInteract: false,
  });

  const internalRenderer = (
    model as unknown as {
      internalModel?: { renderer?: { setClippingMaskBufferSize?: (size: number) => void } };
    }
  ).internalModel?.renderer;
  // PonchoGirl uses far more mask partitions than the default sample model.
  // A larger mask atlas reduces obvious clipping artifacts once we allow >4x4
  // subdivisions per RGBA channel.
  internalRenderer?.setClippingMaskBufferSize?.(1024);

  // Pixi 7's federated event system can still try to walk the Live2D
  // display tree on pointer move. Some pixi-live2d-display internals are
  // not compatible with that traversal, so keep the model fully non-interactive.
  model.eventMode = "none";
  model.interactive = false;
  model.interactiveChildren = false;
  model.anchor.set(0.5, 0.5);
  app.stage.addChild(model as unknown as PIXI.DisplayObject);

  let zoom = 1;
  let layoutPass = 0;

  const layoutModel = () => {
    layoutStage();
    const s = settings.scale * zoom;
    model.scale.set(s, s);
    model.x = app.renderer.width / 2;
    model.y = app.renderer.height / 2;

    const bounds = model.getBounds();
    const targetX = app.renderer.width / 2;
    const targetY = app.renderer.height * 0.58;
    const centerX = bounds.x + bounds.width / 2;
    const centerY = bounds.y + bounds.height / 2;

    // Center using the model's actual visual bounds rather than assuming
    // every model's local origin behaves like Hiyori's.
    model.x += targetX - centerX + settings.x_offset;

    // Bias slightly low so bust-up characters keep the face in frame.
    // Preserve manual YAML offsets and the extra zoom compensation.
    const upperBodyShift = (zoom - 1) * app.renderer.height * 0.35;
    model.y += targetY - centerY + settings.y_offset + upperBodyShift;

    layoutPass += 1;
    if (layoutPass <= 3) {
      const nextBounds = model.getBounds();
      // eslint-disable-next-line no-console
      console.log("[live2d layout]", {
        modelPath: settings.model_path,
        renderer: { width: app.renderer.width, height: app.renderer.height },
        scale: s,
        zoom,
        position: { x: model.x, y: model.y },
        boundsBefore: { x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height },
        boundsAfter: {
          x: nextBounds.x,
          y: nextBounds.y,
          width: nextBounds.width,
          height: nextBounds.height,
        },
        offsets: { x: settings.x_offset, y: settings.y_offset },
      });
    }
  };

  layoutModel();
  requestAnimationFrame(() => {
    layoutModel();
    app.start();
  });

  window.addEventListener("resize", layoutModel);

  const setZoom = (factor: number) => {
    zoom = Math.max(1, Math.min(2.5, factor));
    layoutModel();
  };

  return { app, model, setZoom, getZoom: () => zoom };
}
