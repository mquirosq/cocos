document.addEventListener('DOMContentLoaded', function () {
  const computeBtn = document.getElementById('compute-matrix');
  const exportBtn = document.getElementById('export-csv');
  const fileSelect = document.getElementById('file_id_batch');

  const predictionResults = document.getElementById('prediction-results');
  const predictionStatus = document.getElementById('prediction-status');

  const modelsSelectEl = document.getElementById('models-select');
  const antibioticsSelectEl = document.getElementById('antibiotics-select');

  const csrftoken = (() => {
    const el = document.querySelector('input[name=csrfmiddlewaretoken]');
    return el ? el.value : null;
  })();

  let lastComputedMatrix = null;


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
    const models = (
      modelsSelectEl &&
      Array.isArray(modelsSelectEl.value)
    )
      ? modelsSelectEl.value.slice()
      : [];

    const antibiotics = (
      antibioticsSelectEl &&
      Array.isArray(antibioticsSelectEl.value)
    )
      ? antibioticsSelectEl.value.slice()
      : [];

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

    selection.models.forEach(model => {
      params.append('models', model);
    });

    selection.antibiotics.forEach(antibiotic => {
      params.append('antibiotics', antibiotic);
    });

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

        console.error(
          'Prediction request failed:',
          response.status,
          error
        );

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
  // TODO: Remove the hardcoded URL and use the prediction task ID instead.
  async function exportCSV() {
    try {
      const response = await fetch('/prediction/3/csv/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken,
        },
      });

      if (!response.ok) {
        console.error('CSV export failed:', response.status);
        return;
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = url;

      const contentDisposition =
        response.headers.get('Content-Disposition') || '';

      const filenameMatch =
        contentDisposition.match(/filename="?([^"]+)"?/);

      link.download = filenameMatch
        ? filenameMatch[1]
        : 'predictions.csv';

      document.body.appendChild(link);
      link.click();
      link.remove();

      setTimeout(() => {
        window.URL.revokeObjectURL(url);
      }, 1500);

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

  // Matrix initialization
  initializeMatrix();
});