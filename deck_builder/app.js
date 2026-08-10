const cards = window.CARD_DATA?.cards || [];
const byId = new Map(cards.map((card) => [card.id, card]));
const deck = new Map();
const flags = new Map();
const savedDecks = new Map();
const PAGE_SIZE = 120;
const STORAGE_KEY = "ontrack-deck-lab-v2";
const FLAG_VALUES = new Set(["Ability", "Attack", "Both"]);

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
  view: "library",
  visibleLimit: PAGE_SIZE,
  focusId: null,
  focusDeckOpen: false,
  focusDeckKind: "Pokemon",
  savedDeckId: null,
  pendingDeckFiles: [],
  toastTimer: null,
};

const els = Object.fromEntries(
  [
    "dataSummary", "deckName", "importOpen", "clearDeck", "exportTxt", "exportCsv",
    "resetFilters", "searchInput", "kindFilter", "typeFilter", "expansionFilter",
    "stageFilter", "sortFilter", "megaFilter", "abilityFilter", "catalogTitle",
    "activeFilterCount", "resultCount", "catalogViews", "importFlagsOpen",
    "exportFlagsTxt", "exportFlagsCsv", "cardGrid", "loadMore", "deckTotal",
    "savedDeckToolbar", "savedDeckBack", "savedDeckTitle", "savedDeckMeta",
    "savedDeckActions", "loadSavedDeck", "deleteSavedDeck",
    "deckStatusTitle", "countRing", "deckBreakdown", "ruleWarnings", "deckList",
    "emptyDeck", "focusOverlay", "closeFocus", "closeFocusX", "focusKind",
    "toggleFocusDeck", "focusDeckTotal", "focusPrevious",
    "focusNext", "focusCardImage", "focusFlagButtons", "focusRemove", "focusAdd", "focusCardCount",
    "focusCardLimit", "focusDeckDrawer", "closeFocusDeck", "focusDeckName",
    "focusDeckValidation", "focusDeckTabs", "focusDeckGrid", "importDialog",
    "deckImportFiles", "importDeckName", "importBox", "importMessage", "importDeck", "flagImportDialog", "flagImportFile",
    "flagImportBox", "replaceFlags", "flagImportMessage", "importFlags", "toast",
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

function flagFor(id) {
  return flags.get(Number(id)) || "";
}

function setFlag(id, value) {
  const numericId = Number(id);
  const card = byId.get(numericId);
  if (!card) return;
  const next = FLAG_VALUES.has(value) ? value : "";
  if (next) flags.set(numericId, next);
  else flags.delete(numericId);
  persistDeck();

  if (!els.focusOverlay.hidden && state.view !== "library" && next !== state.view) {
    closeFocus();
  }
  renderAll();
  showToast(next ? `${card.name} flagged for ${next}.` : `${card.name} flag removed.`);
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
  const payload = {
    name: els.deckName.value,
    cards: [...deck.entries()],
    flags: [...flags.entries()],
    savedDecks: [...savedDecks.values()],
  };
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
    (payload.flags || []).forEach(([id, value]) => {
      if (byId.has(Number(id)) && FLAG_VALUES.has(value)) flags.set(Number(id), value);
    });
    (payload.savedDecks || []).forEach((saved) => {
      if (!saved?.id || !saved?.name || !Array.isArray(saved.cards)) return;
      const recognized = saved.cards
        .map(([id, count]) => [Number(id), Number(count)])
        .filter(([id, count]) => byId.has(id) && count > 0);
      if (recognized.length) savedDecks.set(saved.id, { ...saved, cards: recognized });
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

function selectedSavedDeck() {
  return state.savedDeckId ? savedDecks.get(state.savedDeckId) || null : null;
}

function savedDeckEntries(saved = selectedSavedDeck()) {
  if (!saved) return [];
  return saved.cards
    .map(([id, count]) => ({ card: byId.get(Number(id)), count: Number(count) }))
    .filter(({ card, count }) => card && count > 0);
}

function filteredCards() {
  const query = els.searchInput.value.trim().toLowerCase();
  const saved = selectedSavedDeck();
  const source = state.view === "saved" && saved ? savedDeckEntries(saved).map(({ card }) => card) : cards;
  const visible = source.filter((card) => {
    if (FLAG_VALUES.has(state.view) && flagFor(card.id) !== state.view) return false;
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

function cardTile(card, savedCount = 0) {
  const selected = countFor(card.id);
  const flag = flagFor(card.id);
  const article = document.createElement("article");
  article.className = `cardTile${selected ? " selected" : ""}${flag ? ` flagged flag-${flag.toLowerCase()}` : ""}`;
  article.dataset.id = card.id;
  article.innerHTML = `
    <button class="artButton" type="button" aria-label="Preview ${escapeHtml(card.name)}">
      <img src="${escapeHtml(card.image)}" alt="${escapeHtml(card.name)}" loading="lazy" width="320" height="448">
      ${selected ? `<span class="selectedBadge">${selected}</span>` : ""}
      ${savedCount ? `<span class="savedCopyBadge">×${savedCount}</span>` : ""}
      ${flag ? `<span class="flagBadge">${flag}</span>` : ""}
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
  if (state.view === "saved") {
    renderSavedDecks();
    return;
  }
  els.savedDeckToolbar.hidden = true;
  els.cardGrid.classList.remove("savedDeckFolderGrid");
  const filtered = filteredCards();
  const visible = filtered.slice(0, state.visibleLimit);
  els.resultCount.textContent = `${filtered.length.toLocaleString()} card${filtered.length === 1 ? "" : "s"}`;
  const filterTotal = activeFilterTotal();
  els.activeFilterCount.hidden = filterTotal === 0;
  els.activeFilterCount.textContent = `${filterTotal} active`;
  const viewTitle = state.view === "library" ? "All cards" : `${state.view} flags`;
  els.catalogTitle.textContent = state.kind ? `${viewTitle} · ${state.kind}` : viewTitle;
  renderCatalogViews();
  els.cardGrid.replaceChildren(...visible.map(cardTile));
  els.loadMore.hidden = visible.length >= filtered.length;
  els.loadMore.textContent = `Show more (${filtered.length - visible.length} remaining)`;

  if (!filtered.length) {
    const emptyTitle = state.view === "library" ? "No cards match these filters" : `No cards flagged for ${state.view}`;
    const emptyHelp = state.view === "library" ? "Try clearing a filter or using a broader search." : `Choose ${state.view} from a card's Flag menu to collect it here.`;
    els.cardGrid.innerHTML = `<div class="noResults"><strong>${emptyTitle}</strong><span>${emptyHelp}</span></div>`;
  }
}

function renderCatalogViews() {
  const counts = { Ability: 0, Attack: 0, Both: 0 };
  flags.forEach((value) => { if (counts[value] !== undefined) counts[value] += 1; });
  [...els.catalogViews.querySelectorAll("button")].forEach((button) => {
    const view = button.dataset.view;
    button.classList.toggle("active", view === state.view);
    button.setAttribute("aria-current", view === state.view ? "page" : "false");
    button.querySelector("b").textContent = view === "library"
      ? cards.length.toLocaleString()
      : view === "saved"
        ? savedDecks.size
        : counts[view];
  });
}

function savedDeckStats(saved) {
  const stats = { Pokemon: 0, Trainer: 0, Energy: 0 };
  savedDeckEntries(saved).forEach(({ card, count }) => { stats[card.kind] += count; });
  return stats;
}

function renderSavedDeckFolders() {
  els.savedDeckToolbar.hidden = false;
  els.savedDeckBack.hidden = true;
  els.savedDeckActions.hidden = true;
  els.savedDeckTitle.textContent = "Deck library";
  els.savedDeckMeta.textContent = `${savedDecks.size} saved deck${savedDecks.size === 1 ? "" : "s"}`;
  els.catalogTitle.textContent = "Saved decks";
  els.resultCount.textContent = `${savedDecks.size} folder${savedDecks.size === 1 ? "" : "s"}`;
  els.activeFilterCount.hidden = true;
  els.loadMore.hidden = true;
  els.cardGrid.classList.add("savedDeckFolderGrid");
  els.cardGrid.replaceChildren();

  if (!savedDecks.size) {
    els.cardGrid.innerHTML = `<div class="noResults"><strong>No saved decks yet</strong><span>Use Import to upload one or more deck TXT files.</span></div>`;
    return;
  }

  [...savedDecks.values()]
    .sort((a, b) => String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")) || a.name.localeCompare(b.name))
    .forEach((saved) => {
      const entries = savedDeckEntries(saved);
      const stats = savedDeckStats(saved);
      const total = entries.reduce((sum, entry) => sum + entry.count, 0);
      const folder = document.createElement("button");
      folder.className = "savedDeckFolder";
      folder.type = "button";
      folder.dataset.savedDeckId = saved.id;
      folder.setAttribute("aria-label", `Open ${saved.name}`);
      const artwork = entries.slice(0, 4).map(({ card }) => `<img src="${escapeHtml(card.image)}" alt="" loading="lazy">`).join("");
      folder.innerHTML = `
        <span class="folderTab" aria-hidden="true"></span>
        <span class="folderArtwork">${artwork}</span>
        <span class="folderDetails">
          <strong title="${escapeHtml(saved.name)}">${escapeHtml(saved.name)}</strong>
          <small>${total} cards · ${entries.length} unique</small>
          <span><b>${stats.Pokemon}</b> Pokémon <b>${stats.Trainer}</b> Trainer <b>${stats.Energy}</b> Energy</span>
        </span>`;
      folder.addEventListener("click", () => {
        state.savedDeckId = saved.id;
        state.visibleLimit = PAGE_SIZE;
        renderCards();
      });
      els.cardGrid.appendChild(folder);
    });
}

function renderSavedDecks() {
  renderCatalogViews();
  els.savedDeckToolbar.hidden = false;
  const saved = selectedSavedDeck();
  if (!saved) {
    renderSavedDeckFolders();
    return;
  }

  const allEntries = savedDeckEntries(saved);
  const counts = new Map(allEntries.map(({ card, count }) => [card.id, count]));
  const total = allEntries.reduce((sum, entry) => sum + entry.count, 0);
  const stats = savedDeckStats(saved);
  const filtered = filteredCards();
  const visible = filtered.slice(0, state.visibleLimit);
  els.savedDeckBack.hidden = false;
  els.savedDeckActions.hidden = false;
  els.savedDeckTitle.textContent = saved.name;
  els.savedDeckMeta.textContent = `${total} cards · ${stats.Pokemon} Pokémon · ${stats.Trainer} Trainer · ${stats.Energy} Energy`;
  els.catalogTitle.textContent = saved.name;
  els.resultCount.textContent = `${filtered.length} unique card${filtered.length === 1 ? "" : "s"}`;
  const filterTotal = activeFilterTotal();
  els.activeFilterCount.hidden = filterTotal === 0;
  els.activeFilterCount.textContent = `${filterTotal} active`;
  els.cardGrid.classList.remove("savedDeckFolderGrid");
  els.cardGrid.replaceChildren(...visible.map((card) => cardTile(card, counts.get(card.id) || 0)));
  els.loadMore.hidden = visible.length >= filtered.length;
  els.loadMore.textContent = `Show more (${filtered.length - visible.length} remaining)`;
  if (!filtered.length) {
    els.cardGrid.innerHTML = `<div class="noResults"><strong>No cards match these filters</strong><span>Clear a filter to see the complete saved deck.</span></div>`;
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
  const flag = flagFor(card.id);
  [...els.focusFlagButtons.querySelectorAll("button[data-flag]")].forEach((button) => {
    const active = button.dataset.flag === flag;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
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
  if (event.target.matches("select, input, textarea")) return;
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

function sortedFlaggedCards() {
  const order = { Ability: 0, Attack: 1, Both: 2 };
  return [...flags.entries()]
    .map(([id, flag]) => ({ card: byId.get(id), flag }))
    .filter(({ card, flag }) => card && FLAG_VALUES.has(flag))
    .sort((a, b) => order[a.flag] - order[b.flag] || a.card.name.localeCompare(b.card.name) || a.card.id - b.card.id);
}

function flagsCsvExportText() {
  return ["card_id,flag", ...sortedFlaggedCards().map(({ card, flag }) => `${card.id},${flag}`)].join("\n") + "\n";
}

function flagsTxtExportText() {
  const entries = sortedFlaggedCards();
  const lines = ["****** OnTrack Flagged Card Library ******", ""];
  ["Ability", "Attack", "Both"].forEach((flag) => {
    const group = entries.filter((entry) => entry.flag === flag);
    lines.push(`[${flag}] - ${group.length}`, "");
    group.forEach(({ card }) => lines.push(`${card.id} - ${card.name}`));
    lines.push("");
  });
  lines.push(`Total Flagged Cards - ${entries.length}`, "");
  return lines.join("\n");
}

function exportFlags(format) {
  if (!flags.size) {
    showToast("No flagged cards to export.");
    return;
  }
  const filename = `${safeFilename()}_flags.${format}`;
  if (format === "csv") download(filename, flagsCsvExportText(), "text/csv;charset=utf-8");
  else download(filename, flagsTxtExportText(), "text/plain;charset=utf-8");
  showToast(`Flagged cards exported as ${format.toUpperCase()}.`);
}

function parseFlagImport(text) {
  const imported = new Map();
  const unknown = new Set();
  let currentFlag = "";

  text.replace(/^\uFEFF/, "").split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) return;

    const groupMatch = trimmed.match(/^\[(Ability|Attack|Both)\](?:\s*-\s*\d+)?$/i);
    if (groupMatch) {
      currentFlag = groupMatch[1][0].toUpperCase() + groupMatch[1].slice(1).toLowerCase();
      return;
    }

    const csvMatch = trimmed.match(/^(\d+)\s*,\s*(Ability|Attack|Both)$/i);
    const txtMatch = currentFlag ? trimmed.match(/^(\d+)\s+-\s+.+$/) : null;
    const id = csvMatch ? Number(csvMatch[1]) : txtMatch ? Number(txtMatch[1]) : null;
    const flag = csvMatch
      ? csvMatch[2][0].toUpperCase() + csvMatch[2].slice(1).toLowerCase()
      : txtMatch
        ? currentFlag
        : "";

    if (id !== null) {
      if (byId.has(id) && FLAG_VALUES.has(flag)) imported.set(id, flag);
      else unknown.add(id);
    }
  });
  return { imported, unknown: [...unknown] };
}

function importFlagData() {
  const parsed = parseFlagImport(els.flagImportBox.value);
  if (!parsed.imported.size) {
    els.flagImportMessage.textContent = "No recognized flagged card entries were found.";
    els.flagImportMessage.className = "importMessage error";
    return;
  }
  if (els.replaceFlags.checked) flags.clear();
  parsed.imported.forEach((flag, id) => flags.set(id, flag));
  persistDeck();
  renderAll();
  els.flagImportDialog.close();
  els.flagImportBox.value = "";
  els.flagImportFile.value = "";
  els.flagImportMessage.textContent = "";
  showToast(`Imported ${parsed.imported.size} flagged cards${parsed.unknown.length ? `; ${parsed.unknown.length} unknown IDs skipped` : ""}.`);
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
  const imported = new Map();
  const unknown = new Set();
  text.replace(/^\uFEFF/, "").split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    const txtMatch = trimmed.match(/^(\d+)\s+(.+?)\s+-\s+(\d+)$/);
    const csvMatch = trimmed.match(/^(\d+)$/);
    if (txtMatch) {
      const count = Number(txtMatch[1]);
      const id = Number(txtMatch[3]);
      if (count <= 0) return;
      if (byId.has(id)) imported.set(id, (imported.get(id) || 0) + count);
      else unknown.add(id);
    } else if (csvMatch) {
      const id = Number(csvMatch[1]);
      if (byId.has(id)) imported.set(id, (imported.get(id) || 0) + 1);
      else unknown.add(id);
    }
  });
  return {
    imported,
    unknown: [...unknown],
    total: [...imported.values()].reduce((sum, count) => sum + count, 0),
  };
}

function deckNameFromFile(filename) {
  return filename.replace(/\.[^.]+$/, "").replaceAll("_", " ").trim() || "Imported deck";
}

function saveImportedDeck(name, parsed, source = "Pasted deck list") {
  const cleanName = name.trim() || "Imported deck";
  const existing = [...savedDecks.values()].find((saved) => saved.name.toLowerCase() === cleanName.toLowerCase());
  const id = existing?.id || `deck-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  savedDecks.set(id, {
    id,
    name: cleanName,
    source,
    cards: [...parsed.imported.entries()],
    unknown: parsed.unknown,
    updatedAt: new Date().toISOString(),
  });
  return { id, updated: Boolean(existing) };
}

function clearDeckImportDialog() {
  state.pendingDeckFiles = [];
  els.deckImportFiles.value = "";
  els.importDeckName.value = "";
  els.importBox.value = "";
  els.importMessage.textContent = "";
}

function importDeck() {
  const candidates = [...state.pendingDeckFiles];
  if (els.importBox.value.trim()) {
    candidates.push({
      name: els.importDeckName.value.trim() || els.deckName.value.trim() || "Imported deck",
      source: "Pasted deck list",
      text: els.importBox.value,
    });
  }
  if (!candidates.length) {
    els.importMessage.textContent = "Choose a deck TXT file or paste a deck list first.";
    els.importMessage.className = "importMessage error";
    return;
  }

  const saved = [];
  const rejected = [];
  let unknownCount = 0;
  candidates.forEach((candidate) => {
    const parsed = parseImport(candidate.text);
    if (!parsed.imported.size) {
      rejected.push(candidate.name);
      return;
    }
    const result = saveImportedDeck(candidate.name, parsed, candidate.source);
    saved.push({ ...result, name: candidate.name, total: parsed.total });
    unknownCount += parsed.unknown.length;
  });

  if (!saved.length) {
    els.importMessage.textContent = "No recognized card IDs were found in the selected deck lists.";
    els.importMessage.className = "importMessage error";
    return;
  }
  persistDeck();
  state.view = "saved";
  state.savedDeckId = null;
  state.visibleLimit = PAGE_SIZE;
  renderCards();
  els.importDialog.close();
  clearDeckImportDialog();
  const updates = saved.filter((item) => item.updated).length;
  const details = [
    `${saved.length} deck${saved.length === 1 ? "" : "s"} saved`,
    updates ? `${updates} updated` : "",
    unknownCount ? `${unknownCount} unknown ID${unknownCount === 1 ? "" : "s"} skipped` : "",
    rejected.length ? `${rejected.length} unreadable file${rejected.length === 1 ? "" : "s"}` : "",
  ].filter(Boolean).join("; ");
  showToast(details + ".");
}

function loadSelectedSavedDeck() {
  const saved = selectedSavedDeck();
  if (!saved) return;
  deck.clear();
  saved.cards.forEach(([id, count]) => setCardCount(Number(id), Number(count)));
  els.deckName.value = saved.name;
  persistDeck();
  renderAll();
  showToast(`${saved.name} loaded into the builder.`);
}

function deleteSelectedSavedDeck() {
  const saved = selectedSavedDeck();
  if (!saved || !window.confirm(`Delete the saved deck "${saved.name}"?`)) return;
  savedDecks.delete(saved.id);
  state.savedDeckId = null;
  persistDeck();
  renderCards();
  showToast(`${saved.name} deleted from saved decks.`);
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
  els.catalogViews.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-view]");
    if (!button) return;
    const nextView = button.dataset.view;
    if (nextView === "saved" && state.view !== "saved") state.savedDeckId = null;
    state.view = nextView;
    state.visibleLimit = PAGE_SIZE;
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
  els.importFlagsOpen.addEventListener("click", () => {
    els.flagImportMessage.textContent = "";
    els.flagImportDialog.showModal();
  });
  els.exportFlagsCsv.addEventListener("click", () => exportFlags("csv"));
  els.exportFlagsTxt.addEventListener("click", () => exportFlags("txt"));
  els.flagImportFile.addEventListener("change", async () => {
    const file = els.flagImportFile.files[0];
    if (!file) return;
    try {
      els.flagImportBox.value = await file.text();
      els.flagImportMessage.textContent = `${file.name} loaded and ready to import.`;
      els.flagImportMessage.className = "importMessage";
    } catch {
      els.flagImportMessage.textContent = "The selected file could not be read.";
      els.flagImportMessage.className = "importMessage error";
    }
  });
  els.importFlags.addEventListener("click", importFlagData);
  els.importOpen.addEventListener("click", () => {
    els.importMessage.textContent = "";
    els.importDeckName.value = els.deckName.value.trim() || "My imported deck";
    els.importDialog.showModal();
  });
  els.deckImportFiles.addEventListener("change", async () => {
    const files = [...els.deckImportFiles.files];
    state.pendingDeckFiles = [];
    if (!files.length) return;
    try {
      state.pendingDeckFiles = await Promise.all(files.map(async (file) => ({
        name: deckNameFromFile(file.name),
        source: file.name,
        text: await file.text(),
      })));
      els.importMessage.textContent = `${files.length} deck file${files.length === 1 ? "" : "s"} loaded and ready to save.`;
      els.importMessage.className = "importMessage";
      if (files.length === 1) els.importDeckName.value = deckNameFromFile(files[0].name);
    } catch {
      state.pendingDeckFiles = [];
      els.importMessage.textContent = "One or more selected files could not be read.";
      els.importMessage.className = "importMessage error";
    }
  });
  els.importDeck.addEventListener("click", importDeck);
  els.savedDeckBack.addEventListener("click", () => {
    state.savedDeckId = null;
    state.visibleLimit = PAGE_SIZE;
    renderCards();
  });
  els.loadSavedDeck.addEventListener("click", loadSelectedSavedDeck);
  els.deleteSavedDeck.addEventListener("click", deleteSelectedSavedDeck);
  els.closeFocus.addEventListener("click", closeFocus);
  els.closeFocusX.addEventListener("click", closeFocus);
  els.focusPrevious.addEventListener("click", () => navigateFocus(-1));
  els.focusNext.addEventListener("click", () => navigateFocus(1));
  els.focusRemove.addEventListener("click", () => removeCard(state.focusId));
  els.focusAdd.addEventListener("click", () => addCard(state.focusId));
  els.focusFlagButtons.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-flag]");
    if (!button) return;
    setFlag(state.focusId, flagFor(state.focusId) === button.dataset.flag ? "" : button.dataset.flag);
  });
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
  els.flagImportDialog.addEventListener("click", (event) => {
    if (event.target === els.flagImportDialog) els.flagImportDialog.close();
  });
  document.addEventListener("keydown", handleFocusKeydown);

  renderAll();
}

init();
