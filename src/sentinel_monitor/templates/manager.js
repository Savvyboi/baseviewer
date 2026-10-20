"use strict";
(() => {
  const form = document.getElementById("site-form");
  const fields = document.getElementById("site-fields");
  const list = document.getElementById("sites-list");
  const feedback = document.getElementById("site-feedback");
  const runFeedback = document.getElementById("run-feedback");
  const publishButton = document.getElementById("publish-sites");
  const runButton = document.getElementById("run-monitor");
  const categoryFilter = document.getElementById("category-filter");
  const groupCategories = document.getElementById("group-categories");
  const token = document.querySelector('meta[name="sentinel-token"]').content;
  const labels = {
    draft: "Saved locally",
    published: "Submitted to GitHub",
    pending: "Awaiting first check",
    possible_change: "Possible ground change",
    no_change_detected: "No change detected",
    insufficient_data: "Insufficient data",
    error: "Analysis error"
  };
  let busy = false;
  let state = null;
  let lastList = "";

  function message(element, text, error = false) {
    element.textContent = text;
    element.classList.toggle("error", error);
  }

  async function request(url, method = "GET", data) {
    const options = {method, headers: {"X-Sentinel-Token": token}};
    if (data !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(data);
    }
    const response = await fetch(url, options);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Request failed. Please try again.");
    return result;
  }

  function controls() {
    const running = state?.job.status === "running";
    fields.disabled = busy || !state || running;
    runButton.disabled = busy || !state || running || !state.sites.length;
    runButton.textContent = running ? "Checking…" : "Run demo check";
    publishButton.disabled = busy || !state || running || !state.github || state.github.synced;
    list.querySelectorAll("button, input").forEach(button => {button.disabled = busy || running;});
  }

  function cell(row, text) {
    const element = document.createElement("td");
    element.textContent = text;
    row.append(element);
    return element;
  }

  function render() {
    document.getElementById("demo-banner").hidden = state.mode !== "demo";
    document.getElementById("demo-controls").hidden = state.mode !== "demo";
    publishButton.hidden = state.mode === "demo";
    const syncState = document.getElementById("sync-state");
    syncState.textContent = state.mode === "demo" ? "Demo mode: changes stay local." :
      state.github?.synced ? "List saved on GitHub. Check GitHub runs for Pages deployment and weekly results." :
      state.publish_error || "Local changes are awaiting publication to GitHub.";
    for (const [id, key] of [["published-report", "pages_url"], ["github-runs", "actions_url"]]) {
      const link = document.getElementById(id);
      link.hidden = !state.github;
      if (state.github) link.href = state.github[key];
    }
    document.getElementById("list-summary").textContent =
      `${state.sites.length} of ${state.max_sites} sites · ${(state.planned_area_m2 / 1e6).toLocaleString(undefined, {maximumFractionDigits: 3})} km² monitored`;

    const serialized = JSON.stringify([state.sites, categoryFilter.value, groupCategories.checked]);
    if (serialized !== lastList) {
      lastList = serialized;
      list.replaceChildren();
      const categories = [...new Set(state.sites.map(site => site.category || ""))].sort((a, b) => a.localeCompare(b));
      const selected = categoryFilter.value;
      categoryFilter.replaceChildren(new Option("All categories", "all"));
      const suggestions = document.getElementById("site-categories");
      suggestions.replaceChildren();
      for (const category of categories) {
        categoryFilter.add(new Option(category || "Uncategorized", `category:${category}`));
        if (category) suggestions.append(new Option(category, category));
      }
      if ([...categoryFilter.options].some(option => option.value === selected)) categoryFilter.value = selected;
      const sites = state.sites.filter(site => categoryFilter.value === "all" || `category:${site.category || ""}` === categoryFilter.value);
      document.getElementById("empty-list").hidden = sites.length > 0;
      if (groupCategories.checked) sites.sort((a, b) => (a.category || "").localeCompare(b.category || "") || a.name.localeCompare(b.name));
      let previousCategory = null;
      for (const site of sites) {
        const category = site.category || "";
        if (groupCategories.checked && previousCategory !== category) {
          const heading = document.createElement("tr");
          const title = document.createElement("th");
          title.colSpan = 6;
          title.scope = "rowgroup";
          title.textContent = category || "Uncategorized";
          heading.append(title);
          list.append(heading);
          previousCategory = category;
        }
        const row = document.createElement("tr");
        cell(row, site.name);
        const categoryCell = cell(row, "");
        const categoryInput = document.createElement("input");
        categoryInput.value = category;
        categoryInput.maxLength = 80;
        categoryInput.placeholder = "Uncategorized";
        categoryInput.setAttribute("list", "site-categories");
        categoryInput.setAttribute("aria-label", `Category for ${site.name}`);
        const saveCategory = document.createElement("button");
        saveCategory.type = "button";
        saveCategory.textContent = "Save category";
        saveCategory.addEventListener("click", () => {
          const value = categoryInput.value.trim();
          mutate(async () => {
            await request(`/api/sites/${encodeURIComponent(site.id)}`, "POST", {category: value});
            message(feedback, `Category saved for ${site.name}. Publish the list to update the online viewer.`);
          });
        });
        categoryCell.append(categoryInput, saveCategory);
        cell(row, `${site.latitude}, ${site.longitude}`);
        cell(row, `${site.size_m.toLocaleString()} m`);
        const statusCell = cell(row, "");
        const status = document.createElement("span");
        status.className = `status ${site.status}`;
        status.textContent = labels[site.status] || site.status;
        statusCell.append(status);
        if (site.checked_through) {
          const date = document.createElement("small");
          date.textContent = `Week ending ${site.checked_through} (UTC, exclusive)`;
          statusCell.append(date);
        }
        const action = cell(row, "");
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "remove";
        remove.textContent = "Remove";
        remove.setAttribute("aria-label", `Remove ${site.name} from monitoring`);
        remove.addEventListener("click", () => mutate(async () => {
          await request(`/api/sites/${encodeURIComponent(site.id)}`, "DELETE");
          message(feedback, `${site.name} removed locally. Publish the list to stop its GitHub checks. History retained.`);
        }));
        action.append(remove);
        list.append(row);
      }
    }
    message(runFeedback, state.job.message, ["error", "partial_error"].includes(state.job.status));
    controls();
  }

  async function refresh() {
    state = await request("/api/state");
    render();
  }

  async function mutate(action) {
    if (busy) return;
    busy = true;
    controls();
    try {
      await action();
      await refresh();
    } catch (error) {
      message(feedback, error.message, true);
    } finally {
      busy = false;
      controls();
    }
  }

  form.addEventListener("submit", event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const data = new FormData(form);
    mutate(async () => {
      const site = await request("/api/sites", "POST", {
        name: data.get("name").trim(),
        latitude: Number(data.get("latitude")),
        longitude: Number(data.get("longitude")),
        size_m: Number(data.get("size_m")),
        category: data.get("category").trim()
      });
      form.reset();
      message(feedback, `${site.name} saved locally. Publish the list to add it to GitHub monitoring.`);
    });
  });

  categoryFilter.addEventListener("change", render);
  groupCategories.addEventListener("change", render);

  publishButton.addEventListener("click", () => mutate(async () => {
    await request("/api/publish", "POST");
    message(feedback, "Sending the saved list to GitHub…");
  }));

  runButton.addEventListener("click", () => mutate(async () => {
    await request("/api/run", "POST");
    message(feedback, "Monitoring started for the saved list.");
  }));

  async function poll() {
    try {
      if (!busy) await refresh();
    } catch (error) {
      state = null;
      controls();
      message(runFeedback, "Cannot reach the local manager. Restart it, then reload this page.", true);
    } finally {
      setTimeout(poll, 2500);
    }
  }
  poll();
})();
