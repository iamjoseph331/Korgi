export interface RunInfo {
  active?: boolean;
  slug?: string;
  lang?: "ja" | "en";
  character?: string;
  has_audio?: boolean;
  has_slides?: boolean;
  audio_url?: string | null;
}

export interface LipSyncSettings {
  sensitivity: number;
  smoothing: number;
  min_threshold: number;
  use_mouth_form: boolean;
}

export interface Live2DSettings {
  model_path: string;
  scale: number;
  x_offset: number;
  y_offset: number;
  lip_sync: LipSyncSettings;
}

export interface CharacterJson {
  name: string;
  lang: "ja" | "en";
  live2d_expression_map: Record<string, string>;
  live2d: Live2DSettings;
}

export interface TimingEntry {
  start_ms: number;
  end_ms: number;
  text: string;
  tag: string;
}

export interface SlideCue {
  idx: number;
  start_ms: number;
}
