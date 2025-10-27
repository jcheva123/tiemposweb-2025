// script.js (estable, sin probes masivos y con fallback a CDN)

// ========== Config ==========
const RACE_TYPES = [
  "serie1","serie2","serie3","serie4","serie5","serie6","serie7","serie8","serie9","serie10","serie11","serie12","serie13",
  "repechaje1","repechaje2","repechaje3","repechaje4","repechaje5","repechaje6",
  "semifinal1","semifinal2","semifinal3","semifinal4",
  "prefinal","final"
];

const BASE_RAW = "https://raw.githubusercontent.com/jcheva123/tiemposweb-2025/main/resultados/";
const BASE_CDN = "https://cdn.jsdelivr.net/gh/jcheva123/tiemposweb-2025@main/resultados/";
const CACHE_MS_RESULTS = 60000; // 60s como usabas antes

// ========== Utils ==========
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

function prettyRaceName(race) {
  return race
    .replace(/^serie(\d+)$/, "Serie $1")
    .replace(/^repechaje(\d+)$/, "Repechaje $1")
    .replace(/^semifinal(\d+)$/, "Semifinal $1")
    .replace("prefinal", "Prefinal")
    .replace("final", "Final");
}

function buildURL(base, fecha, race) {
  // encode Fecha (tiene espacios) y mantiene nombre de archivo
  const f = encodeURIComponent(fecha);
  return `${base}${f}/${race}.json`;
}

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// Intenta Raw y luego CDN. Reintenta 3 veces con backoff si 429/red
async function fetchJSONWithFallback(fecha, race, retries = 3) {
  const urls = [buildURL(BASE_RAW, fecha, race), buildURL(BASE_CDN, fecha, race)];
  let delay = 500;
  for (let attempt = 0; attempt < retries; attempt++) {
    for (const url of urls) {
      try {
        const res = await fetch(url, { cache: "no-store" });
        if (res.ok) return await res.json();
        if (res.status === 404) {
          const e = new Error("not-found"); e.code = 404; throw e;
        }
        if (res.status !== 429) throw new Error(`status-${res.status}`);
      } catch (err) {
        if (err.code === 404) throw err; // no reintentar 404
        // otros errores -> probar siguiente URL o reintentar tras backoff
      }
    }
    await sleep(delay + Math.random() * 250);
    delay *= 2;
  }
  throw new Error("fetch-failed");
}

// ========== UI: cargar lista sin hacer fetch ==========
async function loadRaces() {
  const fechaSelect = $("#fecha-select");
  const fechaValue = fechaSelect.value;

  const raceList = $("#race-list ul");
  const resultsBody = $("table tbody");
  raceList.innerHTML = "";
  resultsBody.innerHTML = "";

  if (!fechaValue) return;

  // Guardar fecha seleccionada
  localStorage.setItem("selectedFecha", fechaValue);

  // Poblar lista sin golpear la red
  for (const race of RACE_TYPES) {
    const li = document.createElement("li");
    li.textContent = prettyRaceName(race);
    li.onclick = () => loadResults(fechaValue, race);
    raceList.appendChild(li);
  }
}

// ========== Cargar resultados al tocar una carrera ==========
async function loadResults(fecha, race) {
  const cacheKey = `${fecha}_${race}`;
  const now = Date.now();
  const tbody = $("table tbody");
  tbody.innerHTML = "";

  try {
    // Cache
    const cached = localStorage.getItem(cacheKey);
    if (cached) {
      const parsed = JSON.parse(cached);
      if (now - parsed.timestamp <= CACHE_MS_RESULTS) {
        renderResults(parsed.data, tbody);
        return;
      }
    }

    // Red con fallback (Raw -> CDN) + backoff
    const data = await fetchJSONWithFallback(fecha, race);
    localStorage.setItem(cacheKey, JSON.stringify({ data, timestamp: now }));
    renderResults(data, tbody);
    setLastUpdatedUI();
    highlightSelectedLI(race);

  } catch (error) {
    if (error.code === 404) {
      // Marcar esa carrera como no disponible (opcional: ocultarla)
      disableRaceLI(race);
      alert(`No hay datos para ${prettyRaceName(race)} en ${fecha}.`);
      return;
    }
    console.error("Error loading results:", error);
    alert("No se pudieron cargar los resultados. Probá nuevamente.");
  }
}

function renderResults(data, tbody) {
  (data?.results || []).forEach(result => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${result.position ?? ""}</td>
      <td>${result.number ?? ""}</td>
      <td>${result.name ?? ""}</td>
      <td>${result.rec ?? ""}</td>
      <td>${result.t_final || "N/A"}</td>
      <td>${result.laps || "N/A"}</td>
      <td class="${result.penalty ? 'penalty' : ''}">${result.penalty ?? "N/A"}</td>
    `;
    tbody.appendChild(tr);
  });
}

function setLastUpdatedUI() {
  const el = $("#last-updated");
  if (!el) return;
  el.hidden = false;
  el.textContent = `Actualizado: ${new Date().toLocaleTimeString()}`;
}

function highlightSelectedLI(race) {
  $$("#race-list li").forEach(li => li.classList.remove("active"));
  const pretty = prettyRaceName(race);
  const li = $$("#race-list li").find(li => li.textContent.trim() === pretty);
  if (li) li.classList.add("active");
}

function disableRaceLI(race) {
  const pretty = prettyRaceName(race);
  const li = $$("#race-list li").find(li => li.textContent.trim() === pretty);
  if (li) {
    li.style.opacity = ".5";
    li.style.pointerEvents = "none";
    li.title = "No disponible";
  }
}

// ========== Estado inicial ==========
document.addEventListener("DOMContentLoaded", () => {
  const fechaSelect = $("#fecha-select");
  const savedFecha = localStorage.getItem("selectedFecha");
  if (savedFecha) fechaSelect.value = savedFecha;
  loadRaces();
});

// ========== Botón "Actualizar Datos" ==========
document.getElementById("update-btn").addEventListener("click", () => {
  const fechaValue = $("#fecha-select").value || "";
  // mantener la fecha, limpiar lo demás
  localStorage.clear();
  localStorage.setItem("selectedFecha", fechaValue);
  location.reload();
});
