document.addEventListener('DOMContentLoaded', function () {
  const LOW_THRESHOLD = 0.35;
  const HIGH_THRESHOLD = 0.65;

  const computeBtn = document.getElementById('compute-matrix');
  const exportBtn = document.getElementById('export-csv');
  const fileSelect = document.getElementById('file_id_batch');

  const predictionResults = document.getElementById('prediction-results');
  const predictionStatus = document.getElementById('prediction-status');

  const modelsSelectEl = document.getElementById('models-select');
  const antibioticsSelectEl = document.getElementById('antibiotics-select');

  const lowThresholdElement = document.getElementById('prediction-low-threshold');
  const highThresholdElement = document.getElementById('prediction-high-threshold');

  const csrftoken = (() => {
    const el = document.querySelector('input[name=csrfmiddlewaretoken]');
    return el ? el.value : null;
  })();

  let lastComputedMatrix = null;


  // Initialization
  if (lowThresholdElement) {
    lowThresholdElement.textContent = LOW_THRESHOLD;
  }

  if (highThresholdElement) {
    highThresholdElement.textContent = HIGH_THRESHOLD;
  }


  // Selection

  function initializeSelection() {
    if (modelsSelectEl) {
      modelsSelectEl.addEventListener('change', updateButtonsState);
    }

    if (antibioticsSelectEl) {
      antibioticsSelectEl.addEventListener('change', updateButtonsState);
    }

    if (fileSelect) {
      fileSelect.addEventListener('change', updateButtonsState);
    }

    updateButtonsState();
  }


  function collectSelection() {
    const models = (modelsSelectEl && Array.isArray(modelsSelectEl.value))? modelsSelectEl.value.slice() : [];

    const antibiotics = (antibioticsSelectEl && Array.isArray(antibioticsSelectEl.value)) ? antibioticsSelectEl.value.slice() : [];

    return {
      models: models,
      antibiotics: antibiotics,
      file_id: fileSelect ? fileSelect.value : '',
    };
  }


  function updateButtonsState() {
    if (!computeBtn || !exportBtn) {
      return;
    }

    const selection = collectSelection();

    const hasModels = selection.models.length > 0;
    const hasAntibiotics = selection.antibiotics.length > 0;
    const hasFile = Boolean(selection.file_id);

    const enabled = hasModels && hasAntibiotics && hasFile;

    computeBtn.disabled = !enabled;
    exportBtn.disabled = !enabled;
  }


  // Matrix rendering

  function renderMatrix(matrix) {
    const header = document.getElementById('prediction-header');
    const body = document.getElementById('prediction-body');

    if (!header || !body || !predictionResults) {
      return;
    }

    body.innerHTML = '';

    // Remove previous model headers
    header.querySelectorAll('.prediction-model-header').forEach(element => element.remove());

    // Add model headers
    matrix.models.forEach(model => {
      const th = document.createElement('th');

      th.className = 'prediction-table-header prediction-antibiotic';

      th.textContent = model;

      header.insertBefore(th, header.querySelector('.prediction-average-header'));
    });

    // Add rows
    matrix.antibiotics.forEach((antibiotic, index) => {
      const values = matrix.data[index];

      const row = document.createElement('tr');
      row.className = 'prediction-row';

      const antibioticCell = document.createElement('td');
      antibioticCell.className = 'prediction-antibiotic';
      antibioticCell.textContent = antibiotic;

      row.appendChild(antibioticCell);

      values.forEach(value => {row.appendChild(createPredictionCell(value))});

      // Average
      row.appendChild(createAverageCell(values));

      body.appendChild(row);
    });

    predictionResults.classList.remove('hidden');
  }


  function createPredictionCell(value) {
    const cell = document.createElement('td');
    cell.className = 'prediction-cell';

    if (value === 'NO_RESULT') {
      cell.classList.add('prediction-no-result');

      const content = document.createElement('div');
      content.className = 'prediction-cell-content';

      const label = document.createElement('span');
      label.className = 'prediction-value';
      label.textContent = 'No results';

      content.appendChild(label);
      cell.appendChild(content);

      return cell;
    }

    const level = getPredictionLevel(value);
    cell.classList.add(level);

    const content = document.createElement('div');
    content.className = 'prediction-cell-content';

    const valueElement = document.createElement('span');
    valueElement.className = 'prediction-value';
    valueElement.textContent = value.toFixed(2);

    const bar = document.createElement('div');
    bar.className = 'prediction-bar';

    const fill = document.createElement('div');
    fill.className = `prediction-bar-fill ${level}`;
    fill.style.width = `${(value * 100).toFixed(0)}%`;

    bar.appendChild(fill);

    content.append(valueElement, bar);
    cell.appendChild(content);

    return cell;
  }


  function createAverageCell(values) {
    const cell = document.createElement('td');
    cell.className = 'prediction-cell prediction-average';

    const numericValues = values.filter(
      value => value !== 'NO_RESULT'
    );

    if (numericValues.length === 0) {
      cell.classList.add('prediction-no-result');

      const content = document.createElement('div');
      content.className = 'prediction-cell-content';

      const label = document.createElement('span');
      label.className = 'prediction-value';
      label.textContent = 'N/A';

      content.appendChild(label);
      cell.appendChild(content);

      return cell;
    }

    const average =
      numericValues.reduce((sum, value) => sum + value, 0) /
      numericValues.length;

    const roundedAverage = Number(average.toFixed(2));
    const level = getPredictionLevel(roundedAverage);

    cell.classList.add(level);

    const content = document.createElement('div');
    content.className = 'prediction-cell-content';

    const valueElement = document.createElement('span');
    valueElement.className = 'prediction-value';
    valueElement.textContent = roundedAverage.toFixed(2);

    const bar = document.createElement('div');
    bar.className = 'prediction-bar';

    const fill = document.createElement('div');
    fill.className = `prediction-bar-fill ${level}`;
    fill.style.width = `${(roundedAverage * 100).toFixed(0)}%`;

    bar.appendChild(fill);

    const riskElement = document.createElement('span');
    riskElement.className = `prediction-risk ${level}`;
    riskElement.textContent = getRiskLabel(roundedAverage);

    content.append(valueElement, bar, riskElement);
    cell.appendChild(content);

    return cell;
  }


  function getPredictionLevel(value) {
    if (value < LOW_THRESHOLD) {
      return 'prediction-low';
    }

    if (value < HIGH_THRESHOLD) {
      return 'prediction-medium';
    }

    return 'prediction-high';
  }


  function getRiskLabel(value) {
    if (value < LOW_THRESHOLD) {
      return 'Low';
    }

    if (value < HIGH_THRESHOLD) {
      return 'Medium';
    }

    return 'High';
  }


  // Prediction

  async function computeMatrix() {
    if (!predictionResults) {
      return null;
    }

    predictionResults.classList.add('hidden');

    if (predictionStatus) {
      predictionStatus.classList.remove('hidden');
    }

    const selection = collectSelection();
    const params = new URLSearchParams();

    selection.models.forEach(model => params.append('models', model));

    selection.antibiotics.forEach(antibiotic => params.append('antibiotics', antibiotic));

    params.append('file_id', selection.file_id);

    try {
      const response = await fetch('/prediction/matrix/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': csrftoken,
        },
        body: params.toString(),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));

        console.error('Prediction request failed:', response.status, error);

        lastComputedMatrix = null;
        return null;
      }

      const matrix = await response.json();

      lastComputedMatrix = matrix;
      renderMatrix(matrix);

      return matrix;

    } catch (error) {
      console.error('Prediction failed:', error);
      lastComputedMatrix = null;
      return null;

    } finally {
      if (predictionStatus) {
        predictionStatus.classList.add('hidden');
      }
    }
  }


  // CSV export

  async function exportCSV() {
    let matrix = lastComputedMatrix;

    if (!matrix) {
      matrix = await computeMatrix();

      if (!matrix) {
        return;
      }
    }

    try {
      const response = await fetch('/prediction/matrix/csv/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify(matrix),
      });

      if (!response.ok) {
        console.error('CSV export failed:', response.status);
        return;
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = url;

      const contentDisposition = response.headers.get('Content-Disposition') || '';

      const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);

      link.download = filenameMatch? filenameMatch[1] : 'predictions.csv';

      document.body.appendChild(link);
      link.click();
      link.remove();

      setTimeout(() => window.URL.revokeObjectURL(url), 1500);

    } catch (error) {
      console.error('CSV export failed:', error);
    }
  }


  // Event listeners

  if (computeBtn) {
    computeBtn.addEventListener('click', event => {
      event.preventDefault();
      computeMatrix();
    });
  }

  if (exportBtn) {
    exportBtn.addEventListener('click', event => {
      event.preventDefault();
      exportCSV();
    });
  }


  // Multi-select initialization

  customElements.whenDefined('multi-select').then(() => {
    initializeSelection();
  });

  updateButtonsState();
});