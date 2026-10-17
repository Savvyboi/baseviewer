/* Local reviewer observations for isolated validation reports. No network writes. */
(() => {
  "use strict";
  const decisions = new Set([
    "unreviewed", "likely_visible_change", "no_obvious_visible_change", "unclear"
  ]);
  const identityFields = [
    "mode", "case_id", "site_id", "analysis_key", "comparison_id",
    "record_generated_at", "acquisition_date", "sensor"
  ];
  const reviewKey = source => "baseviewer-review-v1:" + JSON.stringify(
    Object.fromEntries(identityFields.map(field => [field, source[field]]))
  );
  const reviews = new Map();
  const restorers = new Map();
  const tools = document.querySelectorAll(".review-tools");
  const queue = document.getElementById("review-queue");
  const queueRows = [...document.querySelectorAll("[data-review-target]")];
  const queueReviews = new Map();
  const onlyUnreviewed = document.getElementById("only-unreviewed");
  const nextButton = document.getElementById("next-unreviewed");
  let activeTarget = null;
  const updateQueue = () => {
    if (!queue) return;
    let reviewed = 0;
    let awaiting = 0;
    let unclear = 0;
    for (const row of queueRows) {
      const entry = queueReviews.get(row.dataset.reviewTarget);
      const complete = entry && entry.decision !== "unreviewed";
      const ready = row.dataset.previewReady === "true";
      reviewed += complete ? 1 : 0;
      unclear += entry?.decision === "unclear" ? 1 : 0;
      awaiting += ready ? 0 : 1;
      row.querySelector(".queue-review-status").textContent = !ready ? "Awaiting previews"
        : complete ? ({likely_visible_change: "Likely visible change",
                       no_obvious_visible_change: "No obvious visible change",
                       unclear: "Unclear / needs another look"})[entry.decision]
        : "Unreviewed";
      row.hidden = onlyUnreviewed.checked && complete;
    }
    const pending = queueRows.length - reviewed - awaiting;
    document.getElementById("review-progress").textContent =
      reviewed + " of " + queueRows.length + " usable observations reviewed · "
      + pending + " unreviewed" + (unclear ? " · " + unclear + " unclear" : "")
      + (awaiting ? " · " + awaiting + " awaiting previews" : "");
    nextButton.disabled = pending === 0;
    document.getElementById("review-queue-empty").hidden =
      queueRows.some(row => !row.hidden);
  };
  const openObservation = target => {
    const article = document.getElementById(target);
    if (!article) return;
    activeTarget = target;
    const tool = article.querySelector(".review-tools");
    if (tool) tool.open = true;
    article.scrollIntoView({block: "start"});
    (tool?.querySelector(".review-decision") || article).focus({preventScroll: true});
  };
  onlyUnreviewed?.addEventListener("change", updateQueue);
  for (const row of queueRows) {
    row.querySelector("a").addEventListener("click", event => {
      event.preventDefault();
      openObservation(row.dataset.reviewTarget);
    });
  }
  nextButton?.addEventListener("click", () => {
    const start = queueRows.findIndex(row => row.dataset.reviewTarget === activeTarget);
    for (let offset = 1; offset <= queueRows.length; offset++) {
      const row = queueRows[(start + offset) % queueRows.length];
      if (row.dataset.previewReady === "true"
          && queueReviews.get(row.dataset.reviewTarget)?.decision === "unreviewed") {
        openObservation(row.dataset.reviewTarget);
        break;
      }
    }
  });
  for (const tool of tools) {
    const data = tool.dataset;
    const identity = {
      mode: data.mode,
      case_id: data.caseId,
      site_id: data.siteId,
      analysis_key: data.analysisKey,
      comparison_id: data.comparisonId,
      record_generated_at: data.generatedAt,
      acquisition_date: data.date,
      sensor: data.sensor
    };
    // A refreshed record gets its own review, even if its science key is unchanged.
    const key = reviewKey(identity);
    const select = tool.querySelector(".review-decision");
    const note = tool.querySelector(".review-note");
    const status = tool.querySelector(".review-save-status");
    let entry = {...identity, decision: "unreviewed", note: "", reviewed_at: null};
    try {
      const saved = JSON.parse(localStorage.getItem(key));
      if (saved && decisions.has(saved.decision) && typeof saved.note === "string"
          && saved.note.length <= 2000
          && Object.entries(identity).every(([field, value]) => saved[field] === value)) {
        entry = {...entry, decision: saved.decision, note: saved.note,
                 reviewed_at: typeof saved.reviewed_at === "string" ? saved.reviewed_at : null};
        status.textContent = "Restored review saved in this browser.";
      }
    } catch {
      status.textContent = "Saved review unavailable. Export notes to keep a copy.";
    }
    select.value = entry.decision;
    note.value = entry.note;
    reviews.set(key, entry);
    queueReviews.set(tool.closest(".report").id, entry);
    updateQueue();
    const persist = () => {
      try {
        localStorage.setItem(key, JSON.stringify(entry));
        status.textContent = "Saved in this browser. Export a copy to keep it.";
        return true;
      } catch {
        status.textContent = "Browser storage unavailable. Export now to keep these notes.";
        return false;
      }
    };
    const update = () => {
      reviews.set(key, entry);
      queueReviews.set(tool.closest(".report").id, entry);
      updateQueue();
      return persist();
    };
    const save = () => {
      entry = {...identity, decision: select.value, note: note.value.slice(0, 2000),
               reviewed_at: new Date().toISOString()};
      update();
    };
    restorers.set(key, incoming => {
      entry = {...identity, decision: incoming.decision, note: incoming.note,
               reviewed_at: incoming.reviewed_at};
      select.value = entry.decision;
      note.value = entry.note;
      return update();
    });
    tool.addEventListener("focusin", () => { activeTarget = tool.closest(".report").id; });
    select.addEventListener("change", save);
    note.addEventListener("input", save);
    const image = tool.querySelector(".review-stage img");
    const label = tool.querySelector(".review-view-label");
    const buttons = tool.querySelectorAll("[data-view]");
    for (const button of buttons) {
      button.addEventListener("click", () => {
        for (const other of buttons) {
          other.setAttribute("aria-pressed", String(other === button));
        }
        const title = button.dataset.view === "before" ? "Baseline median composite"
          : button.dataset.view === "after" ? "Target observation · " + data.date
          : "Orange qualifying patches · " + data.date;
        image.alt = title;
        image.src = button.dataset.src;
        label.textContent = title + ". Checkerboard: missing display data.";
      });
    }
    image.addEventListener("error", () => {
      label.textContent = "Preview could not load. Check the original image links above.";
    });
  }
  updateQueue();
  if (queue) queue.hidden = false;
  const importButton = document.getElementById("import-reviews");
  const importFile = document.getElementById("review-import-file");
  let importing = false;
  importButton?.addEventListener("click", () => importFile.click());
  importFile?.addEventListener("change", async () => {
    const file = importFile.files[0];
    if (!file || importing) return;
    const output = document.getElementById("review-import-status");
    importing = true;
    importButton.disabled = true;
    output.textContent = "Reading review file in this browser…";
    try {
      if (file.size > 2 * 1024 * 1024) {
        output.textContent = "File exceeds the 2 MB limit. No notes restored.";
        return;
      }
      let payload;
      try {
        payload = JSON.parse(await file.text());
      } catch {
        output.textContent = "Could not read valid JSON. No notes restored.";
        return;
      }
      if (payload?.schema_version !== 1
          || payload.kind !== "human imagery review observations"
          || !Array.isArray(payload.reviews) || payload.reviews.length > 5000) {
        output.textContent = "Unsupported review export. No notes restored.";
        return;
      }
      const incoming = new Map();
      // Validate the entire file before applying any entry. Treat every value as data.
      for (const entry of payload.reviews) {
        if (!entry || !identityFields.every(field => typeof entry[field] === "string")
            || !decisions.has(entry.decision) || typeof entry.note !== "string"
            || entry.note.length > 2000
            || !(entry.reviewed_at === null || (typeof entry.reviewed_at === "string"
                 && Number.isFinite(Date.parse(entry.reviewed_at))))) {
          output.textContent = "Invalid review entry. No notes restored.";
          return;
        }
        const key = reviewKey(entry);
        if (incoming.has(key)) {
          output.textContent = "File contains duplicate review records. No notes restored.";
          return;
        }
        incoming.set(key, entry);
      }
      let restored = 0;
      let unchanged = 0;
      let unmatched = 0;
      let storageFailures = 0;
      for (const [key, entry] of incoming) {
        const current = reviews.get(key);
        if (!current) {
          unmatched++;
          continue;
        }
        // Never replace an existing choice, a draft note, or a deliberate reset.
        if (current.decision !== "unreviewed" || current.note !== ""
            || current.reviewed_at !== null
            || (entry.decision === "unreviewed" && entry.note === ""
                && entry.reviewed_at === null)) {
          unchanged++;
          continue;
        }
        if (!restorers.get(key)(entry)) storageFailures++;
        restored++;
      }
      output.textContent = restored + " restored · " + unchanged + " unchanged · "
        + unmatched + " did not match this report."
        + (storageFailures ? " Browser storage unavailable for " + storageFailures
           + " records; export a copy to keep them." : "");
    } finally {
      importing = false;
      importButton.disabled = false;
      importFile.value = "";
    }
  });
  const exportButton = document.getElementById("export-reviews");
  exportButton?.addEventListener("click", () => {
    const output = document.getElementById("review-export-status");
    const payload = {
      schema_version: 1,
      kind: "human imagery review observations",
      note: "Reviewer observations only; not independently verified ground truth. Only comparisons in this report are included.",
      exported_at: new Date().toISOString(),
      reviews: [...reviews.values()]
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2) + "\n"],
                                            {type: "application/json"}));
    const link = document.createElement("a");
    link.href = url;
    link.download = "baseviewer-reviews-" + payload.exported_at.slice(0, 10) + ".json";
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    output.textContent = "Exported " + payload.reviews.length + " review records.";
  });
})();
