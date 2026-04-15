import type { SlideCue, TimingEntry } from "../types";

type TagHandler = (tag: string) => void;
type SlideHandler = (idx: number) => void;

export class Timeline {
  private tagHandler: TagHandler = () => {};
  private slideHandler: SlideHandler = () => {};
  private lastTag = "";
  private lastSlideIdx = -1;

  constructor(
    private readonly entries: TimingEntry[],
    private readonly slides: SlideCue[]
  ) {}

  onTagChange(fn: TagHandler) { this.tagHandler = fn; }
  onSlideAdvance(fn: SlideHandler) { this.slideHandler = fn; }

  tick(currentMs: number): void {
    const entry = this.entries.find((e) => currentMs >= e.start_ms && currentMs < e.end_ms);
    const tag = entry?.tag ?? (this.entries[0]?.tag ?? "serious");
    if (tag !== this.lastTag) {
      this.lastTag = tag;
      this.tagHandler(tag);
    }

    let active = 0;
    for (const c of this.slides) {
      if (currentMs >= c.start_ms) active = c.idx;
    }
    if (active !== this.lastSlideIdx) {
      this.lastSlideIdx = active;
      this.slideHandler(active);
    }
  }
}
