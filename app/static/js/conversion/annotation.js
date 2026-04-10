document.addEventListener('DOMContentLoaded', function () {
  const annotationRoot = document.getElementById('annotation-page');
  const initialActiveTab = annotationRoot ? annotationRoot.dataset.activeTab : 'fasta-panel';

  const tabButtons = Array.from(document.querySelectorAll('[data-target-tab]'));
  const tabPanels = {
    'fasta-panel': document.getElementById('fasta-panel'),
    'json-panel': document.getElementById('json-panel'),
  };

  function setActiveTab(target) {
    tabButtons.forEach(function (button) {
      button.classList.toggle('tab-active', button.dataset.targetTab === target);
    });
    Object.keys(tabPanels).forEach(function (panelName) {
      tabPanels[panelName].classList.toggle('hidden', panelName !== target);
    });
  }

  tabButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      setActiveTab(button.dataset.targetTab);
    });
  });

  const sourceJobSelect = document.getElementById('source_job_id');
  const fastaFileInput = document.getElementById('fasta_file');
  const clearFastaFileButton = document.getElementById('clear-fasta-file');

  function syncFastaSourceGuard() {
    if (!sourceJobSelect || !fastaFileInput) return;
    const hasSourceJob = Boolean(sourceJobSelect.value);
    const hasLocalFile = Boolean(fastaFileInput.files && fastaFileInput.files.length > 0);

    fastaFileInput.disabled = hasSourceJob;
    sourceJobSelect.disabled = hasLocalFile;

    if (clearFastaFileButton) {
      clearFastaFileButton.classList.toggle('hidden', !hasLocalFile);
    }
  }

  if (sourceJobSelect && fastaFileInput) {
    sourceJobSelect.addEventListener('change', function () {
      if (sourceJobSelect.value) {
        fastaFileInput.value = '';
      }
      syncFastaSourceGuard();
    });

    fastaFileInput.addEventListener('change', function () {
      if (fastaFileInput.files && fastaFileInput.files.length > 0) {
        sourceJobSelect.value = '';
      }
      syncFastaSourceGuard();
    });

    if (clearFastaFileButton) {
      clearFastaFileButton.addEventListener('click', function () {
        fastaFileInput.value = '';
        syncFastaSourceGuard();
      });
    }

    syncFastaSourceGuard();
  }

  ['annotation-fasta-form', 'annotation-json-form'].forEach(function (formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    form.addEventListener('submit', function () {
      if (!form.checkValidity()) return;
      const submitButton = form.querySelector('button[type="submit"]');
      if (submitButton) submitButton.disabled = true;
    });
  });

  setActiveTab(initialActiveTab || 'fasta-panel');
});
