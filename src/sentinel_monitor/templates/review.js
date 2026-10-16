/* Local reviewer observations for isolated validation reports. No network writes. */
(() => {
  "use strict";
  const decisions = new Set([
    "unreviewed", "likely_visible_change", "no_obvious_visible_change", "unclear"
  ]);
  const reviews = new Map();
  const tools = document.querySelectorAll(".review-tools");
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
    const key = "baseviewer-review-v1:" + JSON.stringify(identity);
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
    const save = () => {
      entry = {...identity, decision: select.value, note: note.value.slice(0, 2000),
               reviewed_at: new Date().toISOString()};
      reviews.set(key, entry);
      try {
        localStorage.setItem(key, JSON.stringify(entry));
        status.textContent = "Saved in this browser. Export a copy to keep or share it.";
      } catch {
        status.textContent = "Browser storage unavailable. Export now to keep these notes.";
      }
    };
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
