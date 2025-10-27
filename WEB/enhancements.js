// enhancements.js
(() => {
  const qs = (s, el = document) => el.querySelector(s);
  const qsa = (s, el = document) => [...el.querySelectorAll(s)];
  const on = (t, f, el = window, opts) => el.addEventListener(t, f, opts);

  const progress = qs('#progress');
  const offlineBanner = qs('#offline-banner');
  const toastEl = qs('#toast');
  const skeleton = qs('#skeleton');
  const fechaSelect = qs('#fecha-select');
  const raceListUL = qs('#race-list ul');
  const searchInput = qs('#results-search');
  const lastUpdated = qs('#last-updated');
  const selectedPill = qs('#selected-pill');
  const shareBtn = qs('#share-btn');

  let refreshTimer = null;
  const REFRESH_MS = 20000;
const PREFETCH_RACES = []; // desactivado para evitar 429


  const showToast = (msg, ms = 2200) => {
    toastEl.textContent = msg;
    toastEl.hidden = false;
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => (toastEl.hidden = true), ms);
  };

  // Reemplazar alert por toast para UX móvil
  const _alert = window.alert.bind(window);
  window.alert = (msg) => showToast(String(msg));

  // Indicadores de conexión
  const updateOnlineUI = () => (offlineBanner.hidden = navigator.onLine);
  updateOnlineUI();
  on('online', updateOnlineUI);
  on('offline', updateOnlineUI);

  // Envolver fetch para barra de progreso en llamadas a /resultados/
  const origFetch = window.fetch.bind(window);
  let inflight = 0;
  window.fetch = async (...args) => {
    const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || '';
    const isResultados = url.includes('/resultados/');
    if (isResultados) {
      if (++inflight === 1) progress.classList.add('active');
      skeleton && (skeleton.hidden = false);
    }
    try {
      const res = await origFetch(...args);
      return res;
    } finally {
      if (isResultados) {
        if (--inflight === 0) progress.classList.remove('active');
        skeleton && (skeleton.hidden = true);
      }
    }
  };

  // Hookear loadResults para: deep-link, pill, last-updated, auto-refresh
  if (typeof window.loadResults === 'function') {
    const origLoadResults = window.loadResults;
    window.loadResults = async (fecha, race) => {
      // Guardar "contexto actual" para otras features
      window.__current = { fecha, race };
      setSelectedPill(fecha, race);
      setQueryParams(fecha, race);
      clearInterval(refreshTimer);
      try {
        await origLoadResults(fecha, race);
        setLastUpdated();
        startAutoRefresh();
      } catch (e) {
        showToast('No se pudieron cargar los resultados.');
        throw e;
      }
    };
  }

  function setSelectedPill(fecha, race) {
    const pretty = prettyRaceName(race);
    selectedPill.hidden = false;
    selectedPill.textContent = `${fecha} · ${pretty}`;
    // resaltar <li> activo
    qsa('#race-list li').forEach(li => li.classList.remove('active'));
    const li = qsa('#race-list li').find(li => li.textContent.trim() === pretty);
    if (li) li.classList.add('active');
  }

  function setLastUpdated() {
    lastUpdated.hidden = false;
    lastUpdated.textContent = `Actualizado: ${new Date().toLocaleTimeString()}`;
  }

  function prettyRaceName(race) {
    return race
      .replace(/^serie(\d+)$/, 'Serie $1')
      .replace(/^repechaje(\d+)$/, 'Repechaje $1')
      .replace(/^semifinal(\d+)$/, 'Semifinal $1')
      .replace('prefinal', 'Prefinal')
      .replace('final', 'Final');
  }

  function parseRaceKey(pretty) {
    const t = pretty.toLowerCase();
    if (t.startsWith('serie ')) return 'serie' + t.split(' ')[1];
    if (t.startsWith('repechaje ')) return 'repechaje' + t.split(' ')[1];
    if (t.startsWith('semifinal ')) return 'semifinal' + t.split(' ')[1];
    if (t === 'prefinal') return 'prefinal';
    if (t === 'final') return 'final';
    return null;
  }

  function setQueryParams(fecha, race) {
    const url = new URL(location.href);
    url.searchParams.set('fecha', fecha);
    url.searchParams.set('race', race);
    history.replaceState({}, '', url);
  }

  // Deep-link al entrar con ?fecha=&race=
  on('DOMContentLoaded', async () => {
    const url = new URL(location.href);
    const qFecha = url.searchParams.get('fecha');
    const qRace = url.searchParams.get('race');

    if (qFecha) {
      fechaSelect.value = qFecha;
      if (typeof window.loadRaces === 'function') {
        await window.loadRaces();
      }
      if (qRace) {
        // Esperar a que existan los LI y simular click
        const waitLI = () =>
          new Promise((r) => {
            const id = setInterval(() => {
              const li = qsa('#race-list li').find(li => parseRaceKey(li.textContent.trim()) === qRace);
              if (li) { clearInterval(id); r(li); }
            }, 120);
          });
        const li = await waitLI();
        li.click();
        // scroll hacia resultados
        qs('#results')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  });

  // Al click en la lista, además del onClick original: resalto y compartible
  on('click', (e) => {
    const li = e.target.closest('#race-list li');
    if (!li) return;
    qsa('#race-list li').forEach(el => el.classList.remove('active'));
    li.classList.add('active');
    // Mejor UX: bajar directo a resultados
    qs('#results')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, document);

  // Búsqueda rápida en tabla
  on('input', () => {
    const q = searchInput.value.trim().toLowerCase();
    const rows = qsa('table tbody tr');
    rows.forEach(tr => {
      const num = tr.children[1]?.textContent?.toLowerCase() || '';
      const name = tr.children[2]?.textContent?.toLowerCase() || '';
      tr.hidden = !(num.includes(q) || name.includes(q));
    });
  }, searchInput, { passive: true });

  // Compartir
  on('click', async () => {
    const ctx = window.__current;
    if (!ctx) { showToast('Elegí una carrera para compartir.'); return; }
    const url = new URL(location.href);
    try {
      if (navigator.share) {
        await navigator.share({ title: document.title, url: url.toString() });
      } else {
        await navigator.clipboard.writeText(url.toString());
        showToast('Enlace copiado.');
      }
    } catch { /* cancelado */ }
  }, shareBtn);

  // Auto-refresh de la carrera seleccionada
  function startAutoRefresh() {
    clearInterval(refreshTimer);
    refreshTimer = setInterval(async () => {
      const ctx = window.__current;
      if (!ctx || !navigator.onLine) return;
      try {
        await window.loadResults(ctx.fecha, ctx.race);
      } catch { /* ya se muestra toast en error */ }
    }, REFRESH_MS);
  }

  // Prefetch silencioso de carreras “probables”
  async function prefetchLikely(fecha) {
    const base = `https://raw.githubusercontent.com/jcheva123/tiemposweb-2025/main/resultados/${fecha}/`;
    const now = Date.now();
    const cacheDuration = 60000; // mismo que tu script

    for (const race of PREFETCH_RACES) {
      const key = `${fecha}_${race}`;
      const cached = localStorage.getItem(key);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (now - parsed.timestamp <= cacheDuration) continue;
      }
      try {
        const res = await fetch(base + race + '.json', { cache: 'no-store' });
        if (!res.ok) continue;
        const data = await res.json();
        localStorage.setItem(key, JSON.stringify({ data, timestamp: now }));
      } catch { /* ignorar */ }
    }
  }

  // --- Anti-duplicados en la lista de carreras + bloqueo de llamadas simultáneas ---
(() => {
  const qs = (s, el = document) => el.querySelector(s);

  // Dedup por texto visible (SERIE 1, SERIE 2, etc.)
  function dedupeRaceList() {
    const ul = qs('#race-list ul');
    if (!ul) return;
    const seen = new Set();
    [...ul.children].forEach(li => {
      const key = li.textContent.trim().toLowerCase();
      if (seen.has(key)) li.remove();
      else seen.add(key);
    });
  }

  // Envuelve loadRaces para evitar doble ejecución en paralelo (throttle)
  if (typeof window.loadRaces === 'function') {
    const original = window.loadRaces;
    let inFlight = false;
    window.loadRaces = async (...args) => {
      if (inFlight) return;            // evita segunda llamada mientras corre
      inFlight = true;
      try {
        const res = await original(...args);
        dedupeRaceList();              // limpia por si hubo doble disparo externo
        return res;
      } finally {
        inFlight = false;
      }
    };
  }

  // También dedupe inmediatamente tras un cambio de fecha, por si otro script llama aparte
  document.getElementById('fecha-select')?.addEventListener('change', () => {
    // pequeño delay para dar tiempo a que se construya la lista
    setTimeout(dedupeRaceList, 0);
  });
})();

  // Cuando cambia de Fecha (o se restaura), prefetchear
  on('change', () => {
    const fecha = fechaSelect.value;
  //  if (fecha) prefetchLikely(fecha);
  }, fechaSelect);

  // (Opcional) Pull-to-refresh suave en móviles
  // Se mantiene simple para no interferir con scroll nativo

  // (Opcional PWA) registrar service worker si existe
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./service-worker.js').catch(() => {});
  }
})();
