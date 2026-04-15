import { Marp } from "@marp-team/marp-core";

const marp = new Marp({ html: false });

export class SlidePanel {
  private slidesHtml: string[] = [];

  constructor(private readonly root: HTMLElement) {}

  async loadMarkdown(url: string): Promise<void> {
    const res = await fetch(url);
    if (!res.ok) {
      this.root.innerHTML = "<p>No slides available.</p>";
      return;
    }
    const md = await res.text();
    const { html, css } = marp.render(md);
    // Marp emits one <section> per slide.
    const doc = new DOMParser().parseFromString(html, "text/html");
    this.slidesHtml = Array.from(doc.querySelectorAll("section")).map((s) => s.outerHTML);
    this.root.innerHTML = `<style>${css}</style>` + (this.slidesHtml[0] ?? "");
  }

  show(idx: number): void {
    if (idx < 0 || idx >= this.slidesHtml.length) return;
    const style = this.root.querySelector("style")?.outerHTML ?? "";
    this.root.innerHTML = style + this.slidesHtml[idx];
  }
}
