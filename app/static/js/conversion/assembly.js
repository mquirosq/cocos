document.addEventListener('DOMContentLoaded', function () {
    const tabButtons = Array.from(document.querySelectorAll('[data-target-tab]'));
    const tabPanels = {
      'illumina-panel': document.getElementById('illumina-panel'),
      'ont-panel': document.getElementById('ont-panel'),
    };

    function setActiveTab(target) {
      tabButtons.forEach(function (button) {
        button.classList.toggle('tab-active', button.dataset.targetTab === target);
      });
      Object.keys(tabPanels).forEach(function (panelName) {
        const panel = tabPanels[panelName];
        if (!panel) return;
        panel.classList.toggle('hidden', panelName !== target);
      });
    }

    tabButtons.forEach(function (button) {
      button.addEventListener('click', function () {
        setActiveTab(button.dataset.targetTab);
      });
    });

    ['assembly-form-illumina', 'assembly-form-ont'].forEach(function (formId) {
      const form = document.getElementById(formId);
      if (!form) return;
      form.addEventListener('submit', function () {
        if (!form.checkValidity()) return;
        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton) submitButton.disabled = true;
      });
    });

    setActiveTab('illumina-panel');
  });
