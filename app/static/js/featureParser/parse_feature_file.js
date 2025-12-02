
// Show loading indicator on form submit and disable submit button
document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('#uploadForm');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const uploadBtn = document.getElementById('uploadBtn');

    if (!form || !loadingIndicator) return;

    form.addEventListener('submit', function (e) {
        if (!form.checkValidity()) return;

        // show indicator and prevent double submit
        loadingIndicator.style.display = 'block';
        if (uploadBtn) uploadBtn.disabled = true;
    });
});