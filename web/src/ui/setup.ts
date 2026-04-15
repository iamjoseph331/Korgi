/**
 * Setup view: pick a PDF + pipeline options, POST /api/run, then
 * navigate to the progress view.
 */

type ApiList<K extends string> = Record<K, string[]>;

async function fetchList<K extends string>(url: string, key: K): Promise<string[]> {
  try {
    const res = await fetch(url);
    if (!res.ok) return [];
    const body = (await res.json()) as ApiList<K>;
    return body[key] ?? [];
  } catch {
    return [];
  }
}

function fillSelect(el: HTMLSelectElement, values: string[], preferred?: string): void {
  el.innerHTML = "";
  for (const v of values) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    el.appendChild(opt);
  }
  if (preferred && values.includes(preferred)) el.value = preferred;
}

export async function mountSetup(onSubmitted: (runId: string) => void): Promise<void> {
  const drop = document.getElementById("drop") as HTMLDivElement;
  const fileInput = document.getElementById("file") as HTMLInputElement;
  const langSel = document.getElementById("lang") as HTMLSelectElement;
  const minutesInput = document.getElementById("minutes") as HTMLInputElement;
  const charSel = document.getElementById("character") as HTMLSelectElement;
  const provSel = document.getElementById("provider") as HTMLSelectElement;
  const voiceInput = document.getElementById("voice") as HTMLInputElement;
  const skipFcCb = document.getElementById("skip_factcheck") as HTMLInputElement;
  const slidesCb = document.getElementById("slides") as HTMLInputElement;
  const goBtn = document.getElementById("go") as HTMLButtonElement;
  const status = document.getElementById("setup-status") as HTMLSpanElement;
  const errBox = document.getElementById("setup-err") as HTMLDivElement;
  const pitchInput = document.getElementById("pitch") as HTMLInputElement | null;
  const pitchVal = document.getElementById("pitch-val") as HTMLSpanElement | null;
  const speedInput = document.getElementById("speed") as HTMLInputElement | null;
  const speedVal = document.getElementById("speed-val") as HTMLSpanElement | null;
  const charYaml = document.getElementById("character-yaml") as HTMLTextAreaElement | null;

  let picked: File | null = null;

  const [characters, providers] = await Promise.all([
    fetchList("/api/characters", "characters"),
    fetchList("/api/providers", "providers"),
  ]);

  const lang = langSel.value as "ja" | "en";
  fillSelect(charSel, characters, `default_${lang}`);
  fillSelect(provSel, providers, providers.includes("elevenlabs") ? "elevenlabs" : providers[0]);

  langSel.addEventListener("change", () => {
    const l = langSel.value;
    const pref = `default_${l}`;
    if (characters.includes(pref)) {
      charSel.value = pref;
      void loadCharacterYaml(pref);
    }
  });

  // ── character YAML editor ─────────────────────────────
  let charYamlOriginal = "";
  async function loadCharacterYaml(name: string): Promise<void> {
    if (!charYaml) return;
    try {
      const res = await fetch(`/api/characters/${encodeURIComponent(name)}`);
      if (!res.ok) { charYaml.value = ""; charYamlOriginal = ""; return; }
      const text = await res.text();
      charYaml.value = text;
      charYamlOriginal = text;
    } catch {
      charYaml.value = ""; charYamlOriginal = "";
    }
  }
  charSel.addEventListener("change", () => { void loadCharacterYaml(charSel.value); });
  await loadCharacterYaml(charSel.value);

  // ── pitch / speed sliders ─────────────────────────────
  if (pitchInput && pitchVal) {
    const updatePitch = () => {
      const v = parseInt(pitchInput.value, 10);
      pitchVal.textContent = v === 0 ? "0" : (v > 0 ? `+${v}` : `${v}`);
    };
    pitchInput.addEventListener("input", updatePitch);
    updatePitch();
  }
  if (speedInput && speedVal) {
    const updateSpeed = () => {
      speedVal.textContent = `${parseFloat(speedInput.value).toFixed(2)}×`;
    };
    speedInput.addEventListener("input", updateSpeed);
    updateSpeed();
  }

  function renderPicked(): void {
    drop.classList.remove("drag");
    drop.classList.toggle("picked", picked !== null);
    if (picked) {
      const kb = (picked.size / 1024).toFixed(1);
      drop.innerHTML = `
        <div class="fname">${picked.name}</div>
        <div class="meta">${kb} KB — クリックで変更</div>
      `;
    } else {
      drop.innerHTML = `
        <div class="big">PDF をここにドロップ <span style="color:var(--muted)">または</span> クリックして選択</div>
        <div class="hint">.pdf only — 論文一本（数MB〜数十MB）</div>
      `;
    }
    goBtn.disabled = picked === null;
  }
  renderPicked();

  function pick(file: File | null): void {
    if (file && !file.name.toLowerCase().endsWith(".pdf")) {
      errBox.textContent = "PDF ファイルを選んでください。";
      errBox.hidden = false;
      return;
    }
    errBox.hidden = true;
    picked = file;
    renderPicked();
  }

  drop.addEventListener("click", () => fileInput.click());
  drop.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
  });
  fileInput.addEventListener("change", () => pick(fileInput.files?.[0] ?? null));

  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("drag"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    pick(e.dataTransfer?.files?.[0] ?? null);
  });

  goBtn.addEventListener("click", async () => {
    if (!picked) return;
    errBox.hidden = true;
    goBtn.disabled = true;
    status.textContent = "アップロード中…";

    try {
      const fd = new FormData();
      fd.append("pdf", picked);
      fd.append("lang", langSel.value);
      fd.append("minutes", String(parseInt(minutesInput.value, 10) || 30));
      fd.append("character", charSel.value);
      fd.append("provider", provSel.value);
      fd.append("voice", voiceInput.value.trim());
      fd.append("skip_factcheck", String(skipFcCb.checked));
      fd.append("slides", String(slidesCb.checked));
      if (pitchInput) fd.append("pitch", pitchInput.value);
      if (speedInput) fd.append("speed", speedInput.value);
      if (charYaml && charYaml.value.trim() && charYaml.value !== charYamlOriginal) {
        fd.append("character_yaml", charYaml.value);
      }

      const res = await fetch("/api/run", { method: "POST", body: fd });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      const { run_id: runId } = (await res.json()) as { run_id: string };
      status.textContent = "";
      onSubmitted(runId);
    } catch (err) {
      errBox.textContent = `アップロード失敗: ${String(err)}`;
      errBox.hidden = false;
      status.textContent = "";
      goBtn.disabled = false;
    }
  });
}
