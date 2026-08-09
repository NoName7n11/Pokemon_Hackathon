const cards = window.CARD_DATA?.cards || [];
const byId = new Map(cards.map((card) => [card.id, card]));
const deck = new Map();
const PAGE_SIZE = 120;
const STORAGE_KEY = "ontrack-deck-lab-v2";

const typeNames = {
  "{G}": "Grass",
  "{R}": "Fire",
  "{W}": "Water",
  "{L}": "Lightning",
  "{P}": "Psychic",
  "{F}": "Fighting",
  "{D}": "Darkness",
  "{M}": "Metal",
  "{C}": "Colorless",
  "{A}": "Dragon",
  "竜": "Dragon",
};

const state = {
  kind: "",
  visibleLimit: PAGE_SIZE,
  focusId: null,
  focusDeckOpen: false,
  focusDeckKind: "Pokemon",
  toastTimer: null,
};

const els = Object.fromEntries(
  [
    "dataSummary", "deckName", "importOpen", "clearDeck", "exportTxt", "exportCsv",
    "resetFilters", "searchInput", "kindFilter", "typeFilter", "expansionFilter",
    "stageFilter", "sortFilter", "megaFilter", "abilityFilter", "catalogTitle",
    "activeFilterCount", "resultCount", "cardGrid", "loadMore", "deckTotal",
    "deckStatusTitle", "countRing", "deckBreakdown", "ruleWarnings", "deckList",
    "emptyDeck", "focusOverlay", "closeFocus", "closeFocusX", "focusKind",
    "toggleFocusDeck", "focusDeckTotal", "focusPrevious",
    "focusNext", "focusCardImage", "focusRemove", "focusAdd", "focusCardCount",
    "focusCardLimit", "focusDeckDrawer", "closeFocusDeck", "focusDeckName",
    "focusDeckValidation", "focusDeckTabs", "focusDeckGrid", "importDialog",
    "importBox", "importMessage", "importDeck", "toast",
  ].map((id) => [id, document.getElementById(id)])
);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function typeLabel(value) {
  if (!value) return "Any";
  if (typeNames[value]) return typeNames[value];
  const symbols = [...value.matchAll(/\{([^}]+)\}/g)].map((match) => typeNames[`{${match[1]}}`] || match[1]);
  return symbols.length ? symbols.join(" / ") : value;
}

function fillSelect(select, values, labeler = (value) => value) {
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = labeler(value);
    select.appendChild(option);
  });
}

function totalCards() {
  return [...deck.values()].reduce((sum, count) => sum + count, 0);
}

function countFor(id) {
  return deck.get(id) || 0;
}

function nameCount(cardName) {
  let total = 0;
  deck.forEach((count, id) => {
    if (byId.get(id)?.name.toLowerCase() === cardName.toLowerCase()) total += count;
  });
  return total;
}

function canAdd(card) {
  if (totalCards() >= 60) return false;
  return card.isBasicEnergy || nameCount(card.name) < 4;
}

function addCard(id) {
  const card = byId.get(Number(id));
  if (!card) return;
  if (!canAdd(card)) {
    showToast(totalCards() >= 60 ? "The deck already contains 60 cards." : `Four copies of ${card.name} are already selected.`);
    return;
  }
  deck.set(card.id, countFor(card.id) + 1);
  persistDeck();
  renderAll();
}

function removeCard(id) {
  const numericId = Number(id);
  const next = countFor(numericId) - 1;
  if (next <= 0) deck.delete(numericId);
  else deck.set(numericId, next);
  persistDeck();
  renderAll();
}

function setCardCount(id, count) {
  const card = byId.get(Number(id));
  if (!card) return;
  if (count <= 0) deck.delete(card.id);
  else deck.set(card.id, count);
}

function persistDeck() {
  const payload = { name: els.deckName.value, cards: [...deck.entries()] };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function restoreDeck() {
  try {
    const payload = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (!payload) return;
    if (payload.name) els.deckName.value = payload.name;
    (payload.cards || []).forEach(([id, count]) => {
      if (byId.has(Number(id)) && Number(count) > 0) deck.set(Number(id), Number(count));
    });
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function cardSearchText(card) {
  return [card.name, card.expansion, card.stage, card.rule, card.category, card.type, card.previousStage, card.effectText]
    .join(" ")
    .toLowerCase();
}

function activeFilterTotal() {
  return [
    els.searchInput.value.trim(), state.kind, els.typeFilter.value, els.expansionFilter.value,
    els.stageFilter.value, els.megaFilter.checked, els.abilityFilter.checked,
  ].filter(Boolean).length;
}

function filteredCards() {
  const query = els.searchInput.value.trim().toLowerCase();
  const visible = cards.filter((card) => {
    if (query && !cardSearchText(card).includes(query)) return false;
    if (state.kind && card.kind !== state.kind) return false;
    if (els.typeFilter.value && card.type !== els.typeFilter.value) return false;
    if (els.expansionFilter.value && card.expansion !== els.expansionFilter.value) return false;
    if (els.stageFilter.value && card.stage !== els.stageFilter.value) return false;
    if (els.megaFilter.checked && !card.isMega) return false;
    if (els.abilityFilter.checked && !card.hasAbility) return false;
    return true;
  });

  const sort = els.sortFilter.value;
  visible.sort((a, b) => {
    if (sort === "name") return a.name.localeCompare(b.name) || a.id - b.id;
    if (sort === "hp") return (b.hp || 0) - (a.hp || 0) || a.name.localeCompare(b.name);
    return a.expansion.localeCompare(b.expansion) || Number(a.collectionNumber) - Number(b.collectionNumber) || a.id - b.id;
  });
  return visible;
}

function cardTile(card) {
  const selected = countFor(card.id);
  const article = document.createElement("article");
  article.className = `cardTile${selected ? " selected" : ""}`;
  article.dataset.id = card.id;
  article.innerHTML = `
    <button class="artButton" type="button" aria-label="Preview ${escapeHtml(card.name)}">
      <img src="${escapeHtml(card.image)}" alt="${escapeHtml(card.name)}" loading="lazy" width="320" height="448">
      ${selected ? `<span class="selectedBadge">${selected}</span>` : ""}
    </button>
    <div class="cardTileFooter">
      <div class="tileIdentity">
        <strong title="${escapeHtml(card.name)}">${escapeHtml(card.name)}</strong>
        <span>${escapeHtml(card.expansion)} ${escapeHtml(card.collectionNumber)} · ID ${card.id}</span>
      </div>
      <div class="tileStepper">
        <button class="removeButton" type="button" aria-label="Remove ${escapeHtml(card.name)}" ${selected ? "" : "disabled"}>−</button>
        <span>${selected}</span>
        <button class="addButton" type="button" aria-label="Add ${escapeHtml(card.name)}" ${canAdd(card) ? "" : "disabled"}>+</button>
      </div>
    </div>`;
  article.querySelector(".artButton").addEventListener("click", () => openCard(card.id));
  article.querySelector(".artButton").addEventListener("keydown", handleGridKeydown);
  article.querySelector(".removeButton").addEventListener("click", () => removeCard(card.id));
  article.querySelector(".addButton").addEventListener("click", () => addCard(card.id));
  return article;
}

function handleGridKeydown(event) {
  if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "+", "=", "-", "_"].includes(event.key)) return;
  event.preventDefault();
  const buttons = [...els.cardGrid.querySelectorAll(".artButton")];
  const current = buttons.indexOf(event.currentTarget);
  if (current < 0) return;
  const firstWidth = buttons[0]?.getBoundingClientRect().width || 140;
  const columns = Math.max(1, Math.floor(els.cardGrid.clientWidth / firstWidth));
  if (event.key === "+" || event.key === "=") {
    addCard(Number(event.currentTarget.closest(".cardTile").dataset.id));
    return;
  }
  if (event.key === "-" || event.key === "_") {
    removeCard(Number(event.currentTarget.closest(".cardTile").dataset.id));
    return;
  }
  const offset = event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : event.key === "ArrowUp" ? -columns : columns;
  buttons[Math.max(0, Math.min(buttons.length - 1, current + offset))]?.focus();
}

function renderCards() {
  const filtered = filteredCards();
  const visible = filtered.slice(0, state.visibleLimit);
  els.resultCount.textContent = `${filtered.length.toLocaleString()} card${filtered.length === 1 ? "" : "s"}`;
  const filterTotal = activeFilterTotal();
  els.activeFilterCount.hidden = filterTotal === 0;
  els.activeFilterCount.textContent = `${filterTotal} active`;
  els.catalogTitle.textContent = state.kind ? `${state.kind} cards` : "All cards";
  els.cardGrid.replaceChildren(...visible.map(cardTile));
  els.loadMore.hidden = visible.length >= filtered.length;
  els.loadMore.textContent = `Show more (${filtered.length - visible.length} remaining)`;

  if (!filtered.length) {
    els.cardGrid.innerHTML = `<div class="noResults"><strong>No cards match these filters</strong><span>Try clearing a filter or using a broader search.</span></div>`;
  }
}

function sortedDeckCards() {
  const order = { Pokemon: 0, Trainer: 1, Energy: 2 };
  return [...deck.entries()]
    .map(([id, count]) => ({ card: byId.get(id), count }))
    .filter(({ card }) => card)
    .sort((a, b) => order[a.card.kind] - order[b.card.kind] || a.card.name.localeCompare(b.card.name) || a.card.id - b.card.id);
}

function deckStats() {
  const stats = { Pokemon: 0, Trainer: 0, Energy: 0 };
  sortedDeckCards().forEach(({ card, count }) => { stats[card.kind] += count; });
  return stats;
}

function validationIssues() {
  const issues = [];
  const total = totalCards();
  if (total !== 60) issues.push({ type: "error", text: `${60 - total > 0 ? `${60 - total} more card${60 - total === 1 ? "" : "s"} needed` : `${total - 60} cards over the limit`}.` });

  const byName = new Map();
  sortedDeckCards().forEach(({ card, count }) => {
    if (!card.isBasicEnergy) byName.set(card.name, (byName.get(card.name) || 0) + count);
  });
  byName.forEach((count, name) => {
    if (count > 4) issues.push({ type: "error", text: `${name} exceeds the four-copy limit.` });
  });

  const aceSpecCount = sortedDeckCards()
    .filter(({ card }) => `${card.rule} ${card.category} ${card.effectText}`.toLowerCase().includes("ace spec"))
    .reduce((sum, entry) => sum + entry.count, 0);
  if (aceSpecCount > 1) issues.push({ type: "error", text: `Only one ACE SPEC is allowed (${aceSpecCount} selected).` });

  const basicPokemon = sortedDeckCards()
    .filter(({ card }) => card.kind === "Pokemon" && card.stage.toLowerCase().startsWith("basic"))
    .reduce((sum, entry) => sum + entry.count, 0);
  if (total > 0 && basicPokemon === 0) issues.push({ type: "warning", text: "Add at least one Basic Pokemon to start a game." });
  return issues;
}

function deckRow(card, count) {
  const row = document.createElement("div");
  row.className = "deckRow";
  row.innerHTML = `
    <button class="deckThumb" type="button" aria-label="Preview ${escapeHtml(card.name)}"><img src="${escapeHtml(card.image)}" alt="" loading="lazy"></button>
    <div class="deckRowName"><strong title="${escapeHtml(card.name)}">${escapeHtml(card.name)}</strong><span>${escapeHtml(card.expansion)} ${escapeHtml(card.collectionNumber)} · ID ${card.id}</span></div>
    <div class="stepper" aria-label="Copies of ${escapeHtml(card.name)}">
      <button type="button" data-action="remove" aria-label="Remove one">−</button>
      <strong>${count}</strong>
      <button type="button" data-action="add" aria-label="Add one" ${canAdd(card) ? "" : "disabled"}>+</button>
    </div>`;
  row.querySelector(".deckThumb").addEventListener("click", () => openCard(card.id));
  row.querySelector('[data-action="remove"]').addEventListener("click", () => removeCard(card.id));
  row.querySelector('[data-action="add"]').addEventListener("click", () => addCard(card.id));
  return row;
}

function renderDeck() {
  const entries = sortedDeckCards();
  const total = totalCards();
  const stats = deckStats();
  const issues = validationIssues();
  const isLegal = total === 60 && !issues.some((issue) => issue.type === "error");

  els.deckTotal.textContent = total;
  els.deckStatusTitle.textContent = isLegal ? "Ready to export" : total ? "In progress" : "Start building";
  els.countRing.style.setProperty("--progress", `${Math.min(total / 60, 1) * 360}deg`);
  els.countRing.classList.toggle("complete", isLegal);
  els.deckBreakdown.innerHTML = `
    <span class="stat pokemon"><b>${stats.Pokemon}</b> Pokemon</span>
    <span class="stat trainer"><b>${stats.Trainer}</b> Trainer</span>
    <span class="stat energy"><b>${stats.Energy}</b> Energy</span>`;
  els.ruleWarnings.innerHTML = isLegal
    ? `<div class="validationItem success"><span>✓</span><div><strong>60-card deck ready</strong><small>Basic deck rules passed.</small></div></div>`
    : issues.map((issue) => `<div class="validationItem ${issue.type}"><span>${issue.type === "error" ? "!" : "i"}</span><div>${escapeHtml(issue.text)}</div></div>`).join("");

  els.deckList.innerHTML = "";
  els.emptyDeck.hidden = entries.length > 0;
  els.deckList.hidden = entries.length === 0;
  const groups = { Pokemon: [], Trainer: [], Energy: [] };
  entries.forEach((entry) => groups[entry.card.kind].push(entry));
  Object.entries(groups).forEach(([kind, groupEntries]) => {
    if (!groupEntries.length) return;
    const section = document.createElement("section");
    section.className = "deckGroup";
    const subtotal = groupEntries.reduce((sum, entry) => sum + entry.count, 0);
    section.innerHTML = `<div class="deckGroupTitle"><h3>${kind}</h3><span>${subtotal}</span></div>`;
    groupEntries.forEach(({ card, count }) => section.appendChild(deckRow(card, count)));
    els.deckList.appendChild(section);
  });
}

function renderAll() {
  renderCards();
  renderDeck();
  if (!els.focusOverlay.hidden && state.focusId) renderFocus();
}

function openCard(id) {
  const card = byId.get(Number(id));
  if (!card) return;
  state.focusId = card.id;
  els.focusOverlay.hidden = false;
  renderFocus();
  els.focusAdd.focus();
}

function focusSequence() {
  const filtered = filteredCards();
  return filtered.some((card) => card.id === state.focusId) ? filtered : cards;
}

function navigateFocus(offset) {
  const sequence = focusSequence();
  if (!sequence.length) return;
  const current = Math.max(0, sequence.findIndex((card) => card.id === state.focusId));
  state.focusId = sequence[(current + offset + sequence.length) % sequence.length].id;
  renderFocus();
}

function closeFocus() {
  const closingId = state.focusId;
  els.focusOverlay.hidden = true;
  state.focusDeckOpen = false;
  els.focusDeckDrawer.hidden = true;
  els.toggleFocusDeck.setAttribute("aria-expanded", "false");
  requestAnimationFrame(() => els.cardGrid.querySelector(`.cardTile[data-id="${closingId}"] .artButton`)?.focus());
}

function toggleFocusDeck(force) {
  state.focusDeckOpen = typeof force === "boolean" ? force : !state.focusDeckOpen;
  els.focusDeckDrawer.hidden = !state.focusDeckOpen;
  els.focusOverlay.classList.toggle("drawerOpen", state.focusDeckOpen);
  els.toggleFocusDeck.setAttribute("aria-expanded", String(state.focusDeckOpen));
  if (state.focusDeckOpen) renderFocusDeck();
}

function renderFocus() {
  const card = byId.get(state.focusId);
  if (!card) return;
  els.focusKind.textContent = card.kind;
  els.focusCardImage.src = card.image;
  els.focusCardImage.alt = card.name;
  els.focusCardCount.textContent = countFor(card.id);
  els.focusCardLimit.textContent = card.isBasicEnergy ? "60" : "4";
  els.focusRemove.disabled = countFor(card.id) === 0;
  els.focusAdd.disabled = !canAdd(card);
  els.focusDeckTotal.textContent = `${totalCards()} / 60`;
  els.focusDeckName.textContent = els.deckName.value || "My Deck";
  renderFocusDeck();
}

function renderFocusDeck() {
  if (!state.focusDeckOpen) return;
  const stats = deckStats();
  [...els.focusDeckTabs.querySelectorAll("button")].forEach((button) => {
    const kind = button.dataset.kind;
    button.classList.toggle("active", kind === state.focusDeckKind);
    button.querySelector("b").textContent = stats[kind];
  });
  const issues = validationIssues();
  const legal = totalCards() === 60 && !issues.some((issue) => issue.type === "error");
  els.focusDeckValidation.className = `drawerValidation ${legal ? "valid" : "invalid"}`;
  els.focusDeckValidation.textContent = legal ? "Valid 60-card deck" : `${totalCards()} / 60 · Deck incomplete`;
  const entries = sortedDeckCards().filter(({ card }) => card.kind === state.focusDeckKind);
  els.focusDeckGrid.innerHTML = entries.length ? entries.map(({ card, count }) => `
    <button class="drawerCard" type="button" data-id="${card.id}" aria-label="Open ${escapeHtml(card.name)}">
      <img src="${escapeHtml(card.image)}" alt="">
      <span>${count}</span>
    </button>`).join("") : `<div class="drawerEmpty">No ${state.focusDeckKind.toLowerCase()} cards yet.</div>`;
  els.focusDeckGrid.querySelectorAll(".drawerCard").forEach((button) => {
    button.addEventListener("click", () => { state.focusId = Number(button.dataset.id); renderFocus(); });
  });
}

function handleFocusKeydown(event) {
  if (els.focusOverlay.hidden) return;
  if (["ArrowLeft", "ArrowUp"].includes(event.key)) {
    event.preventDefault(); navigateFocus(-1);
  } else if (["ArrowRight", "ArrowDown"].includes(event.key)) {
    event.preventDefault(); navigateFocus(1);
  } else if (event.key === "+" || event.key === "=") {
    event.preventDefault(); addCard(state.focusId);
  } else if (event.key === "-" || event.key === "_") {
    event.preventDefault(); removeCard(state.focusId);
  } else if (event.key === "Escape") {
    event.preventDefault(); closeFocus();
  }
}

function csvExportText() {
  return sortedDeckCards().flatMap(({ card, count }) => Array(count).fill(String(card.id))).join("\n") + "\n";
}

function txtExportText() {
  const groups = { Pokemon: [], Trainer: [], Energy: [] };
  sortedDeckCards().forEach((entry) => groups[entry.card.kind].push(entry));
  const lines = ["****** Pokémon Trading Card Game Deck List ******", ""];
  [["Pokemon", "Pokémon"], ["Trainer", "Trainer Cards"], ["Energy", "Energy Cards"]].forEach(([key, label]) => {
    const entries = groups[key];
    const subtotal = entries.reduce((sum, entry) => sum + entry.count, 0);
    lines.push(`${subtotal} - ${label}`, "");
    entries.forEach(({ card, count }) => lines.push(`${count} ${card.name} - ${card.id}`));
    lines.push("");
  });
  lines.push(`Total Cards - ${totalCards()}`, "");
  return lines.join("\n");
}

function safeFilename() {
  return (els.deckName.value.trim() || "deck").replace(/[<>:"/\\|?*]+/g, "-").replace(/\s+/g, "_");
}

function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function parseImport(text) {
  const imported = [];
  const unknown = [];
  text.split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    const txtMatch = trimmed.match(/^(\d+)\s+.+\s+-\s+(\d+)$/);
    const csvMatch = trimmed.match(/^(\d+)$/);
    if (txtMatch) {
      const count = Number(txtMatch[1]);
      const id = Number(txtMatch[2]);
      if (byId.has(id)) imported.push(...Array(count).fill(id));
      else unknown.push(id);
    } else if (csvMatch) {
      const id = Number(csvMatch[1]);
      if (byId.has(id)) imported.push(id);
      else unknown.push(id);
    }
  });
  return { imported, unknown: [...new Set(unknown)] };
}

function importDeck() {
  const parsed = parseImport(els.importBox.value);
  if (!parsed.imported.length) {
    els.importMessage.textContent = "No recognized card IDs were found.";
    els.importMessage.className = "importMessage error";
    return;
  }
  deck.clear();
  parsed.imported.slice(0, 60).forEach((id) => setCardCount(id, countFor(id) + 1));
  persistDeck();
  renderAll();
  els.importDialog.close();
  els.importBox.value = "";
  els.importMessage.textContent = "";
  showToast(`Imported ${totalCards()} cards${parsed.unknown.length ? `; ${parsed.unknown.length} unknown IDs skipped` : ""}.`);
}

function resetFilters() {
  els.searchInput.value = "";
  els.typeFilter.value = "";
  els.expansionFilter.value = "";
  els.stageFilter.value = "";
  els.sortFilter.value = "set";
  els.megaFilter.checked = false;
  els.abilityFilter.checked = false;
  state.kind = "";
  state.visibleLimit = PAGE_SIZE;
  [...els.kindFilter.querySelectorAll("button")].forEach((button) => button.classList.toggle("active", button.dataset.value === ""));
  renderCards();
}

function showToast(message) {
  clearTimeout(state.toastTimer);
  els.toast.textContent = message;
  els.toast.classList.add("visible");
  state.toastTimer = setTimeout(() => els.toast.classList.remove("visible"), 2600);
}

function init() {
  document.querySelector(".catalogPanel").appendChild(els.focusOverlay);
  fillSelect(els.typeFilter, window.CARD_DATA.types, typeLabel);
  fillSelect(els.expansionFilter, window.CARD_DATA.expansions);
  fillSelect(els.stageFilter, [...new Set(cards.map((card) => card.stage).filter(Boolean))].sort());
  const imageCount = cards.filter((card) => card.image).length;
  els.dataSummary.textContent = `${cards.length.toLocaleString()} competition cards · ${imageCount.toLocaleString()} local images`;
  restoreDeck();

  [els.searchInput, els.typeFilter, els.expansionFilter, els.stageFilter, els.sortFilter, els.megaFilter, els.abilityFilter]
    .forEach((control) => control.addEventListener("input", () => { state.visibleLimit = PAGE_SIZE; renderCards(); }));
  els.kindFilter.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-value]");
    if (!button) return;
    state.kind = button.dataset.value;
    state.visibleLimit = PAGE_SIZE;
    [...els.kindFilter.querySelectorAll("button")].forEach((item) => item.classList.toggle("active", item === button));
    renderCards();
  });
  els.loadMore.addEventListener("click", () => { state.visibleLimit += PAGE_SIZE; renderCards(); });
  els.resetFilters.addEventListener("click", resetFilters);
  els.deckName.addEventListener("input", () => {
    persistDeck();
    if (!els.focusOverlay.hidden) els.focusDeckName.textContent = els.deckName.value || "My Deck";
  });
  els.clearDeck.addEventListener("click", () => {
    if (!deck.size || window.confirm("Clear every card from this deck?")) {
      deck.clear(); persistDeck(); renderAll(); showToast("Deck cleared.");
    }
  });
  els.exportCsv.addEventListener("click", () => { download(`${safeFilename()}.csv`, csvExportText(), "text/csv;charset=utf-8"); showToast("CSV exported."); });
  els.exportTxt.addEventListener("click", () => { download(`${safeFilename()}.txt`, txtExportText(), "text/plain;charset=utf-8"); showToast("TXT exported."); });
  els.importOpen.addEventListener("click", () => els.importDialog.showModal());
  els.importDeck.addEventListener("click", importDeck);
  els.closeFocus.addEventListener("click", closeFocus);
  els.closeFocusX.addEventListener("click", closeFocus);
  els.focusPrevious.addEventListener("click", () => navigateFocus(-1));
  els.focusNext.addEventListener("click", () => navigateFocus(1));
  els.focusRemove.addEventListener("click", () => removeCard(state.focusId));
  els.focusAdd.addEventListener("click", () => addCard(state.focusId));
  els.closeFocusDeck.addEventListener("click", () => toggleFocusDeck(false));
  els.focusDeckTabs.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-kind]");
    if (!button) return;
    state.focusDeckKind = button.dataset.kind;
    renderFocusDeck();
  });
  els.importDialog.addEventListener("click", (event) => {
    if (event.target === els.importDialog) els.importDialog.close();
  });
  document.addEventListener("keydown", handleFocusKeydown);

  renderAll();
}

init();
