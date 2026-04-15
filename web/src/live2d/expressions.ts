import type { Live2DModel } from "pixi-live2d-display/cubism4";

let motionPriorityPromise: Promise<typeof import("pixi-live2d-display/cubism4").MotionPriority> | null = null;

async function getMotionPriority() {
  if (!motionPriorityPromise) {
    motionPriorityPromise = import("pixi-live2d-display/cubism4").then(
      (mod) => mod.MotionPriority
    );
  }
  return motionPriorityPromise;
}

interface ModelSettings {
  expressions?: Array<{ Name?: string; name?: string }>;
  motions?: Record<string, unknown>;
}

function readSettings(model: Live2DModel): ModelSettings {
  const internal = (model as unknown as { internalModel?: { settings?: ModelSettings } }).internalModel;
  return internal?.settings ?? {};
}

export function makeExpressionDriver(
  model: Live2DModel,
  expressionMap: Record<string, string>
) {
  const settings = readSettings(model);
  const expressionNames = new Set<string>(
    (settings.expressions ?? [])
      .map((e) => e.Name ?? e.name)
      .filter((n): n is string => !!n)
  );
  const motionGroups = new Set<string>(Object.keys(settings.motions ?? {}));

  let current = "";

  return async function applyTag(tag: string): Promise<void> {
    if (tag === current) return;
    current = tag;
    const name = expressionMap[tag] ?? expressionMap["serious"];
    if (!name) return;
    const MotionPriority = await getMotionPriority();

    try {
      if (expressionNames.has(name)) {
        // Classic expression flow: force-kick Idle to clear residual pose,
        // then stamp the expression on top.
        await model.motion("Idle", 0, MotionPriority.FORCE);
        await model.expression(name);
        // eslint-disable-next-line no-console
        console.log(`[expr] → ${tag} (expression: ${name})`);
        return;
      }
      if (motionGroups.has(name)) {
        await model.motion(name, undefined, MotionPriority.FORCE);
        // eslint-disable-next-line no-console
        console.log(`[expr] → ${tag} (motion group: ${name})`);
        return;
      }
      // eslint-disable-next-line no-console
      console.warn(
        `[expr] no expression or motion group "${name}" on model (tag="${tag}")`
      );
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn(`[expr] failed to apply "${name}" for tag "${tag}"`, err);
    }
  };
}
