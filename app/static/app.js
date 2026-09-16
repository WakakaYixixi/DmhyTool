"use strict";

const STORAGE_KEY = "dmhytool.savedSearchTerms";
const state = { results: [] };

const searchForm = document.querySelector("#search-form");
const searchInput = document.querySelector("#search-input");
const searchButton = document.querySelector("#search-button");
const saveButton = document.querySelector("#save-button");
const searchStatus = document.querySelector("#search-status");
const savedTerms = document.querySelector("#saved-terms");
const resultsSection = document.querySelector("#results-section");
const resultCount = document.querySelector("#result-count");
const resultsBody = document.querySelector("#results-body");
const selectAllButton = document.querySelector("#select-all");
const selectNoneButton = document.querySelector("#select-none");
const exportButton = document.querySelector("#export-button");
const downloadButton = document.querySelector("#download-button");
const exportSection = document.querySelector("#export-section");
const exportStatus = document.querySelector("#export-status");
const magnetOutput = document.querySelector("#magnet-output");
const exportFailures = document.querySelector("#export-failures");
const copyButton = document.querySelector("#copy-button");
const downloadConfig = document.querySelector("#download-config");
const downloadStatus = document.querySelector("#download-status");
const downloadResults = document.querySelector("#download-results");

function setStatus(element, message, type = "") {
  element.textContent = message;
  element.className = `status${type ? ` ${type}` : ""}`;
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    throw new Error(`服务返回了无法解析的响应（HTTP ${response.status}）`);
  }
}

function loadSavedTerms() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(value) ? value.filter(item => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function storeSavedTerms(terms) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(terms));
  renderSavedTerms();
}

function renderSavedTerms() {
  const terms = loadSavedTerms();
  savedTerms.replaceChildren();
  if (!terms.length) {
    const empty = document.createElement("p");
    empty.className = "saved-empty";
    empty.textContent = "还没有保存搜索词";
    savedTerms.append(empty);
    return;
  }

  terms.forEach((term, index) => {
    const item = document.createElement("div");
    item.className = "saved-item";

    const searchSaved = document.createElement("button");
    searchSaved.type = "button";
    searchSaved.className = "saved-search";
    searchSaved.textContent = term;
    searchSaved.title = `搜索“${term}”`;
    searchSaved.addEventListener("click", () => {
      searchInput.value = term;
      runSearch(term);
    });

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "saved-delete";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `删除已保存搜索词“${term}”`);
    remove.addEventListener("click", () => {
      const next = loadSavedTerms();
      next.splice(index, 1);
      storeSavedTerms(next);
    });

    item.append(searchSaved, remove);
    savedTerms.append(item);
  });
}

function makeCell(text, className = "") {
  const cell = document.createElement("td");
  cell.textContent = text || "—";
  if (className) cell.className = className;
  return cell;
}

function renderResults(results) {
  resultsBody.replaceChildren();
  resultCount.textContent = `(${results.length})`;
  resultsSection.classList.remove("hidden");

  results.forEach((result, index) => {
    const row = document.createElement("tr");
    const checkCell = document.createElement("td");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "result-check";
    checkbox.dataset.index = String(index);
    checkbox.setAttribute("aria-label", `选择 ${result.title}`);
    checkCell.append(checkbox);

    const titleCell = document.createElement("td");
    const titleLink = document.createElement("a");
    titleLink.className = "result-title-link";
    titleLink.href = result.detail_url;
    titleLink.target = "_blank";
    titleLink.rel = "noopener noreferrer";
    titleLink.textContent = result.title;
    titleCell.append(titleLink);

    const detailCell = document.createElement("td");
    const detailLink = document.createElement("a");
    detailLink.href = result.detail_url;
    detailLink.target = "_blank";
    detailLink.rel = "noopener noreferrer";
    detailLink.textContent = "打开";
    detailCell.append(detailLink);

    row.append(
      checkCell,
      makeCell(result.published_at, "nowrap"),
      titleCell,
      makeCell(result.group),
      makeCell(result.size, "nowrap"),
      detailCell,
    );
    resultsBody.append(row);
  });
}

function getSelectedResults() {
  return [...document.querySelectorAll(".result-check:checked")]
    .map(item => state.results[Number(item.dataset.index)])
    .filter(Boolean);
}

async function loadDownloadStatus() {
  try {
    const response = await fetch("/api/download/status");
    const data = await readJson(response);
    if (!response.ok) throw new Error();
    if (data.configured) {
      downloadConfig.textContent = data.download_dir
        ? `下载目录：${data.download_dir}`
        : "下载目录：DSM 默认";
    } else {
      downloadConfig.textContent = "尚未配置 DSM 连接";
    }
  } catch {
    downloadConfig.textContent = "无法读取 DSM 配置状态";
  }
}

function renderDownloadResults(data) {
  downloadResults.replaceChildren();
  if (data.success.length) {
    const successBox = document.createElement("div");
    successBox.className = "download-result success";
    const heading = document.createElement("h3");
    heading.textContent = "已添加";
    const list = document.createElement("ul");
    data.success.forEach(result => {
      const item = document.createElement("li");
      item.textContent = result.title || result.resource_id;
      list.append(item);
    });
    successBox.append(heading, list);
    downloadResults.append(successBox);
  }

  if (data.failed.length) {
    const failureBox = document.createElement("div");
    failureBox.className = "download-result failure";
    const heading = document.createElement("h3");
    heading.textContent = "失败";
    const list = document.createElement("ul");
    data.failed.forEach(result => {
      const item = document.createElement("li");
      item.textContent = `${result.title || result.resource}：${result.reason}`;
      list.append(item);
    });
    failureBox.append(heading, list);
    downloadResults.append(failureBox);
  }
}

async function runSearch(rawKeyword) {
  const keyword = rawKeyword.trim();
  if (!keyword) {
    setStatus(searchStatus, "请输入搜索词", "error");
    searchInput.focus();
    return;
  }

  searchInput.value = keyword;
  searchButton.disabled = true;
  saveButton.disabled = true;
  resultsSection.classList.add("hidden");
  exportSection.classList.add("hidden");
  setStatus(searchStatus, "正在搜索 DMHY，请稍候…");

  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(keyword)}`);
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.detail || `搜索失败（HTTP ${response.status}）`);

    state.results = data.results;
    renderResults(data.results);
    if (data.results.length) {
      setStatus(searchStatus, `找到 ${data.results.length} 条结果`, "success");
    } else {
      setStatus(searchStatus, "没有找到匹配的结果，请尝试其他关键词", "error");
    }
  } catch (error) {
    state.results = [];
    setStatus(searchStatus, error.message || "搜索请求失败", "error");
  } finally {
    searchButton.disabled = false;
    saveButton.disabled = false;
  }
}

searchForm.addEventListener("submit", event => {
  event.preventDefault();
  runSearch(searchInput.value);
});

saveButton.addEventListener("click", () => {
  const term = searchInput.value.trim();
  if (!term) {
    setStatus(searchStatus, "请先输入要保存的搜索词", "error");
    return;
  }
  const terms = loadSavedTerms();
  if (!terms.includes(term)) terms.push(term);
  storeSavedTerms(terms);
  setStatus(searchStatus, `已保存搜索词“${term}”`, "success");
});

selectAllButton.addEventListener("click", () => {
  document.querySelectorAll(".result-check").forEach(item => { item.checked = true; });
});

selectNoneButton.addEventListener("click", () => {
  document.querySelectorAll(".result-check").forEach(item => { item.checked = false; });
});

exportButton.addEventListener("click", async () => {
  const selected = getSelectedResults();

  exportSection.classList.remove("hidden");
  exportFailures.replaceChildren();
  magnetOutput.value = "";
  if (!selected.length) {
    setStatus(exportStatus, "请至少勾选一条搜索结果后再导出", "error");
    exportSection.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }

  exportButton.disabled = true;
  setStatus(exportStatus, `正在获取 ${selected.length} 个详情页的磁力链接…`);
  try {
    const response = await fetch("/api/magnets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: selected.map(item => ({ resource: item.detail_url, title: item.title })),
      }),
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.detail || `导出失败（HTTP ${response.status}）`);

    magnetOutput.value = data.magnets.map(item => item.magnet).join("\n");
    setStatus(
      exportStatus,
      `成功 ${data.magnets.length} 条，失败 ${data.failures.length} 条`,
      data.magnets.length ? "success" : "error",
    );

    if (data.failures.length) {
      const heading = document.createElement("strong");
      heading.textContent = "以下项目获取失败：";
      const list = document.createElement("ul");
      data.failures.forEach(failure => {
        const item = document.createElement("li");
        item.textContent = `${failure.title || failure.resource}：${failure.reason}`;
        list.append(item);
      });
      exportFailures.append(heading, list);
    }
  } catch (error) {
    setStatus(exportStatus, error.message || "导出请求失败", "error");
  } finally {
    exportButton.disabled = false;
    exportSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
});

downloadButton.addEventListener("click", async () => {
  const selected = getSelectedResults();
  downloadResults.replaceChildren();
  if (!selected.length) {
    setStatus(downloadStatus, "请至少勾选一条搜索结果后再加入 Download Station", "error");
    document.querySelector("#download-section").scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (!window.confirm(`准备添加 ${selected.length} 个下载任务，是否继续？`)) {
    setStatus(downloadStatus, "已取消添加下载任务");
    return;
  }

  downloadButton.disabled = true;
  setStatus(downloadStatus, `正在解析并提交 ${selected.length} 个下载任务…`);
  try {
    const response = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: selected.map(item => ({ resource: item.detail_url, title: item.title })),
      }),
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.detail || `提交失败（HTTP ${response.status}）`);
    renderDownloadResults(data);
    setStatus(
      downloadStatus,
      `已添加 ${data.success.length} 个任务，失败 ${data.failed.length} 个`,
      data.success.length ? "success" : "error",
    );
  } catch (error) {
    setStatus(downloadStatus, error.message || "提交 Download Station 失败", "error");
  } finally {
    downloadButton.disabled = false;
    document.querySelector("#download-section").scrollIntoView({ behavior: "smooth", block: "start" });
  }
});

copyButton.addEventListener("click", async () => {
  if (!magnetOutput.value) {
    setStatus(exportStatus, "没有可复制的磁力链接", "error");
    return;
  }
  try {
    await navigator.clipboard.writeText(magnetOutput.value);
  } catch {
    magnetOutput.select();
    if (!document.execCommand("copy")) {
      setStatus(exportStatus, "复制失败，请手动选择文本复制", "error");
      return;
    }
  }
  setStatus(exportStatus, "已复制全部磁力链接", "success");
});

renderSavedTerms();
loadDownloadStatus();
