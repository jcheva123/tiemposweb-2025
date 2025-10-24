// posiciones.js — tabla de posiciones (búsqueda, orden, vista compacta) con errores visibles
const STATE = { rows: [], sortKey: 'pos', sortDir: 'asc' };

function fmt(n){ if(n==null) return ''; return Number.isInteger(n)? String(n) : Number(n).toFixed(2); }

function renderMeta(meta){
  const el = document.getElementById('meta');
  if(!el || !meta) return;
  const fecha = meta.fechas_cumplidas ? `Cumplidas ${meta.fechas_cumplidas} fechas` : '';
  const src   = meta.source_pdf ? `PDF: ${meta.source_pdf}` : '';
  const up    = meta.extracted_at_utc ? `Actualizado: ${meta.extracted_at_utc}` : '';
  el.textContent = [fecha, src, up].filter(Boolean).join(' • ');
}

function renderTable(rows){
  const tb = document.querySelector('#tbl tbody');
  tb.innerHTML = '';
  for(const r of rows){
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${fmt(r.pos)}</td>
      <td>${fmt(r.nro)}</td>
      <td>${r.nombre || ''}</td>
      <td>${fmt(r.anterior)}</td>
      <td>${fmt(r.serie)}</td>
      <td>${fmt(r.semif)}</td>
      <td>${fmt(r.prefinal)}</td>
      <td>${fmt(r.final)}</td>
      <td><strong>${fmt(r.total)}</strong></td>
      <td>${fmt(r.fin)}</td>
    `;
    tb.appendChild(tr);
  }
}

function sortRows(rows, key, dir){
  const mult = dir === 'desc' ? -1 : 1;
  return [...rows].sort((a,b)=>{
    const va = a[key], vb = b[key];
    if(va == null && vb == null) return 0;
    if(va == null) return 1;
    if(vb == null) return -1;
    if(typeof va === 'number' && typeof vb === 'number') return (va - vb) * mult;
    return String(va).localeCompare(String(vb)) * mult;
  });
}

function applyFilter(){
  const q = (document.getElementById('q').value || '').trim().toLowerCase();
  let rows = STATE.rows;
  if(q){
    rows = rows.filter(r => String(r.nro).includes(q) || (r.nombre||'').toLowerCase().includes(q));
  }
  rows = sortRows(rows, STATE.sortKey, STATE.sortDir);
  renderTable(rows);
}

async function loadJSON(){
  const url = new URL('posiciones.json', window.location.href).toString();
  try{
    const res = await fetch(url, { cache: 'no-store' });
    if(!res.ok) throw new Error(res.status + ' ' + res.statusText);
    const data = await res.json();
    if(!data || !Array.isArray(data.standings)) throw new Error('JSON sin "standings"');

    STATE.rows = data.standings;
    renderMeta(data.meta || {});
    applyFilter();
  }catch(err){
    console.error('No se pudo cargar posiciones.json', err);
    const tb = document.querySelector('#tbl tbody');
    tb.innerHTML = `<tr><td colspan="10" style="color:#ffb3b3">
      No se pudo cargar <code>posiciones.json</code>.<br>
      <small>${err.message}. Si abriste el archivo con doble-click (file://), levantá un servidor local.</small>
    </td></tr>`;
  }
}

function setupSort(){
  document.querySelectorAll('#tbl thead th').forEach(th => {
    th.style.cursor = 'pointer';
    th.addEventListener('click', () => {
      const k = th.dataset.k;
      if(!k) return;
      if(STATE.sortKey === k) STATE.sortDir = (STATE.sortDir === 'asc') ? 'desc' : 'asc';
      else { STATE.sortKey = k; STATE.sortDir = 'asc'; }
      applyFilter();
    });
  });
}

function setupFilter(){ document.getElementById('q').addEventListener('input', applyFilter); }

function setupCompact(){
  const btn = document.getElementById('toggle-compact');
  const apply = (isCompact)=>{
    document.body.classList.toggle('compact', isCompact);
    btn.setAttribute('aria-pressed', String(isCompact));
    btn.textContent = isCompact ? '🧾 Vista detallada' : '📱 Vista compacta';
    localStorage.setItem('posicionesCompacta', isCompact ? '1' : '0');
  };
  apply(localStorage.getItem('posicionesCompacta') === '1');
  btn.addEventListener('click', ()=>apply(!document.body.classList.contains('compact')));
}

window.addEventListener('DOMContentLoaded', () => {
  setupSort(); setupFilter(); setupCompact(); loadJSON();
});
