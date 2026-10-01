const LOW_THRESHOLD = 0.35;
const HIGH_THRESHOLD = 0.65;


function initializeMatrix(container) {
  const lowThresholdElement = container.querySelector('.prediction-low-threshold');

  const highThresholdElement = container.querySelector('.prediction-high-threshold');

  if (lowThresholdElement) {
    lowThresholdElement.textContent = LOW_THRESHOLD;
  }

  if (highThresholdElement) {
    highThresholdElement.textContent = HIGH_THRESHOLD;
  }
}


function renderMatrix(container, matrix) {
  const template = document.getElementById('prediction-matrix-template');

  if (!template) {
    console.error('Prediction matrix template not found.');
    return;
  }

  container.innerHTML = template.innerHTML;

  initializeMatrix(container);

  const header = container.querySelector('.prediction-header');
  const body = container.querySelector('.prediction-body');

  if (!header || !body) {
    console.error('Prediction matrix elements not found.');
    return;
  }

  renderHeaders(header, matrix.models);
  renderRows(body, matrix);
}


function renderHeaders(header, models) {
  const averageHeader = header.querySelector('.prediction-average-header');

  models.forEach(model => {
    const th = document.createElement('th');

    th.className = 'prediction-table-header prediction-model-header';
    th.textContent = model;

    header.insertBefore(th, averageHeader);
  });
}

function renderRows(body, matrix) {
  body.innerHTML = '';

  matrix.antibiotics.forEach((antibiotic, index) => {
    const values = matrix.data[index];

    const row = document.createElement('tr');
    row.className = 'prediction-row';

    const antibioticCell = document.createElement('td');
    antibioticCell.className = 'prediction-antibiotic';
    antibioticCell.textContent = antibiotic;

    row.appendChild(antibioticCell);

    values.forEach(value => {
      row.appendChild(createPredictionCell(value));
    });

    row.appendChild(createAverageCell(values));

    body.appendChild(row);
  });
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


function initializePredictionMatrices() {
  document.querySelectorAll('.prediction-matrix').forEach(container => {
    const matrixId = container.dataset.matrixId;

    if (!matrixId) {
      return;
    }

    const matrixElement = document.getElementById(matrixId);

    if (!matrixElement) {
      return;
    }

    try {
      const matrix = JSON.parse(matrixElement.textContent);
      renderMatrix(container, matrix);
    } catch (error) {
      console.error('Could not parse prediction matrix:', error);
    }
  });
}


document.addEventListener(
  'DOMContentLoaded',
  initializePredictionMatrices
);