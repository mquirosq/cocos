(() => {
  const processShell = document.querySelector('.process-shell');

  if (!processShell) {
    return;
  }

  const loadPage = async (url, pushHistory = false) => {
    try {
      const response = await fetch(url, {
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
      });

      if (!response.ok) {
        window.location.href = url;
        return;
      }

      const documentHtml = new DOMParser().parseFromString(await response.text(), 'text/html');
      const nextProcessList = documentHtml.querySelector('.process-list');

      if (!nextProcessList) {
        window.location.href = url;
        return;
      }

      processShell.querySelector('.process-list').replaceWith(nextProcessList);

      if (pushHistory) {
        window.history.pushState({}, '', url);
      }
    } catch {
      window.location.href = url;
    }
  };

  processShell.addEventListener('click', (event) => {
    const pageLink = event.target.closest('[data-process-page]');

    if (!pageLink || !processShell.contains(pageLink)) {
      return;
    }

    event.preventDefault();
    loadPage(pageLink.href, true);
  });

  window.addEventListener('popstate', () => {
    loadPage(window.location.href);
  });
})();
