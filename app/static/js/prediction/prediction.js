document.addEventListener('DOMContentLoaded', function () {
  const lowToHighPredictionThreshold = 0.35;
  const highToLowPredictionThreshold = 0.65;
  
  const computeBtn = document.getElementById('compute-matrix');
  const exportBtn = document.getElementById('export-csv');
  const fileSelect = document.getElementById('file_id_batch');
  const matrixDiv = document.getElementById('prediction-matrix');
  const predictionData = document.getElementById('prediction-data');


  const csrftoken = (function() {
    const el = document.querySelector('input[name=csrfmiddlewaretoken]');
    return el ? el.value : null;
  })();

  const modelsSelectEl = document.getElementById('models-select');
  const antibioticsSelectEl = document.getElementById('antibiotics-select');
  let lastComputedMatrix = null;
  function initializeSelection() {
    if (modelsSelectEl) modelsSelectEl.addEventListener('change', updateButtonsState);
    if (antibioticsSelectEl) antibioticsSelectEl.addEventListener('change', updateButtonsState);
    if (fileSelect) fileSelect.addEventListener('change', updateButtonsState);

    updateButtonsState();
    return Boolean(modelsSelectEl || antibioticsSelectEl);
  }

  function collectSelection() {
    const models = (modelsSelectEl && Array.isArray(modelsSelectEl.value)) ? modelsSelectEl.value.slice() : [];
    const antibiotics = (antibioticsSelectEl && Array.isArray(antibioticsSelectEl.value)) ? antibioticsSelectEl.value.slice() : [];
    return {
      models: models,
      antibiotics: antibiotics,
      file_id: fileSelect ? fileSelect.value : '',
    };
  }

  function updateButtonsState() {
    if (!computeBtn || !exportBtn) return;
    const sel = collectSelection();
    const hasModels = Array.isArray(sel.models) ? sel.models.length > 0 : Boolean(sel.models);
    const hasAntibiotics = Array.isArray(sel.antibiotics) ? sel.antibiotics.length > 0 : Boolean(sel.antibiotics);
    const hasFile = Boolean(sel.file_id);
    computeBtn.disabled = !(hasModels && hasAntibiotics && hasFile);
    exportBtn.disabled = !(hasModels && hasAntibiotics && hasFile);
  }

  function getCSSVar(name) {
    return getComputedStyle(document.querySelector('[data-theme]')).getPropertyValue(name).trim();
  }

  function renderMatrix(matrix) {
    const warningColor = getCSSVar('--color-warning-soft');
    const warningColorContent = getCSSVar('--color-warning-soft-content');
    const errorColor = getCSSVar('--color-error-soft');
    const errorColorContent = getCSSVar('--color-error-soft-content');
    const successColor = getCSSVar('--color-success-soft');
    const successColorContent = getCSSVar('--color-success-soft-content');

    const container = document.getElementById('prediction-matrix');

    function colorForProb(p) {
      if (p < lowToHighPredictionThreshold) return { bg: successColor, fill: successColorContent, text: successColorContent };
      if (p < highToLowPredictionThreshold) return { bg: warningColor, fill: warningColorContent, text: warningColorContent };
      return { bg: errorColor, fill: errorColorContent, text: errorColorContent };
    }

    function riskLabel(p) {
      if (p < lowToHighPredictionThreshold) return { label: 'Low',    bg: successColor, color: successColorContent };
      if (p < highToLowPredictionThreshold) return { label: 'Medium', bg: warningColor, color: warningColorContent };
      return             { label: 'High',   bg: errorColor, color: errorColorContent };
    }

    function cellHTML(v) {
      const c = colorForProb(v);
      return `<td style="background:${c.bg};padding:9px 14px;text-align:center">
        <div style="display:inline-flex;flex-direction:column;align-items:center;gap:3px;min-width:52px">
          <span style="font-size:13px;font-weight:500;color:${c.text}">${v.toFixed(2)}</span>
          <div style="width:36px;height:3px;border-radius:2px;background:#ffffff">
            <div style="width:${(v*100).toFixed(0)}%;height:100%;border-radius:2px;background:${c.fill}"></div>
          </div>
        </div>
      </td>`;
    }

    function avgCellHTML(avg) {
      const c = colorForProb(avg);
      const rl = riskLabel(avg);
      return `<td style="background:${c.bg};padding:9px 14px;text-align:center;border-left:1.5px solid #d1d5db;font-weight:500">
        <div style="display:inline-flex;flex-direction:column;align-items:center;gap:3px;min-width:52px">
          <span style="font-size:13px;font-weight:500;color:${c.text}">${avg.toFixed(2)}</span>
          <div style="width:36px;height:3px;border-radius:2px;background:#ffffff">
            <div style="width:${(avg*100).toFixed(0)}%;height:100%;border-radius:2px;background:${c.fill}"></div>
          </div>
          <span style="font-size:11px;font-weight:500;padding:2px 7px;border-radius:999px;background:${rl.bg};color:${rl.color}">${rl.label}</span>
        </div>
      </td>`;
    }

    const rows = matrix.antibiotics.map((ab, i) => {
      const vals = matrix.data[i];
      const avg = parseFloat((vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2));
      return `<tr style="border-bottom:0.5px solid #e5e7eb">
        <td style="padding:9px 14px;font-weight:500;font-size:13px;white-space:nowrap">${ab}</td>
        ${vals.map(v => cellHTML(v)).join('')}
        ${avgCellHTML(avg)}
      </tr>`;
    });

    container.innerHTML = `
      <div style="margin-top:1.5rem">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.75rem;flex-wrap:wrap;gap:8px">
          <span style="font-size:15px;font-weight:500">Prediction matrix</span>
          <div style="display:flex;align-items:center;gap:12px;font-size:12px;color:#6b7280">
            <span>Resistance probability:</span>
            <span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:50%;background:${successColorContent};display:inline-block"></span>Low (&lt;${lowToHighPredictionThreshold})</span>
            <span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:50%;background:${warningColorContent};display:inline-block"></span>Medium</span>
            <span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:50%;background:${errorColorContent};display:inline-block"></span>High (&gt;${highToLowPredictionThreshold})</span>
          </div>
        </div>
        <div style="overflow-x:auto;border-radius:12px;border:0.5px solid #e5e7eb">
          <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead>
              <tr style="background:#f9fafb;border-bottom:0.5px solid #e5e7eb">
                <th style="padding:10px 14px;text-align:left;font-weight:500;font-size:12px;color:#6b7280;white-space:nowrap">Antibiotic</th>
                ${matrix.models.map(m => `<th style="padding:10px 14px;text-align:center;font-weight:500;font-size:12px;color:#6b7280;white-space:nowrap">${m}</th>`).join('')}
                <th style="padding:10px 14px;text-align:center;font-weight:500;font-size:12px;color:#111827;border-left:1.5px solid #d1d5db;white-space:nowrap">Average</th>
              </tr>
            </thead>
            <tbody>${rows.join('')}</tbody>
          </table>
        </div>
      </div>`;
  }

  function parseMatrixResponse(raw) {
    if (!Array.isArray(raw) && Object.keys(raw).length && Object.values(raw).every(v => v && typeof v === 'object' && !Array.isArray(v))) {
      const antibiotics = Object.keys(raw);
      const modelSet = new Set();
      antibiotics.forEach(a => Object.keys(raw[a] || {}).forEach(m => modelSet.add(m)));
      const models = Array.from(modelSet);
      const data = antibiotics.map(a => models.map(m => {
        const cell = raw[a] && raw[a][m];
        return Number(cell) || 0;
      }));
      return { models, antibiotics, data };
    }
  }

  async function computeMatrix() {
    matrixDiv.innerHTML = '<div class="p-4">Computing…</div>';
    const sel = collectSelection();
    const params = new URLSearchParams();
    (sel.models.length ? sel.models : ['all']).forEach(m => params.append('models', m));
    (sel.antibiotics.length ? sel.antibiotics : ['all']).forEach(a => params.append('antibiotics', a));
    params.append('file_id', sel.file_id);

    try {
        const res = await fetch('/prediction/matrix/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrftoken,
            },
            body: params.toString(),
        });

      if (!res.ok) {
        const txt = await res.text();
        matrixDiv.innerHTML = `<div class="alert alert-error">Request failed: ${res.status} ${res.statusText}: ${txt}</div>`;
        return;
      }
      let data = await res.json();
      const normalized = parseMatrixResponse(data);
      if (!normalized) {
        matrixDiv.innerHTML = `<div class="alert alert-error">Received unexpected matrix format.</div>`;
        lastComputedMatrix = null;
        return null;
      }
      lastComputedMatrix = normalized;
      renderMatrix(normalized);
      return normalized;
    } catch (err) {
      matrixDiv.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
      lastComputedMatrix = null;
      return null;
    }
   }

   async function exportCSV() {
    let matrix = lastComputedMatrix;
    if (!matrix) {
      matrixDiv.innerHTML = '<div class="p-4">Computing matrix for CSV export…</div>';
      matrix = await computeMatrix();
      if (!matrix) {
        matrixDiv.innerHTML = `<div class="alert alert-error">Cannot export CSV: failed to compute matrix.</div>`;
        return;
      }
    }

    try {
      const res = await fetch('/prediction/matrix/csv/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify(matrix),
      });

      if (!res.ok) {
        const txt = await res.text();
        console.error('CSV export failed: ' + txt);
        matrixDiv.innerHTML = `<div class="alert alert-error">CSV export failed: ${txt}</div>`;
        return;
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;

      const cd = res.headers.get('Content-Disposition') || '';
      let filename = 'predictions.csv';
      const fnStarMatch = /filename\*=([^']*)'[^']*'([^;\s]+)/i.exec(cd);
      try { 
        filename = decodeURIComponent(fnStarMatch[2]); 
      }
      catch (e) { 
        filename = fnStarMatch[2]; 
      }

      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => window.URL.revokeObjectURL(url), 1500);
    } catch (err) {
      matrixDiv.innerHTML = `<div class="alert alert-error">CSV export error: ${err && err.message ? err.message : err}</div>`;
    }
   }

   computeBtn.addEventListener('click', (e) => {
     e.preventDefault();
     console.log('Computing matrix with selection:', collectSelection());
     computeMatrix();
   });

   exportBtn.addEventListener('click', (e) => {
     e.preventDefault();
     console.log('Exporting CSV with selection:', collectSelection());
     exportCSV();
   });


  customElements.whenDefined('multi-select').then(() => {
    initializeSelection();
  });

  // initial state
  updateButtonsState();
});
