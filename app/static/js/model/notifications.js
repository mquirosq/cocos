(() => {
  const panel = document.getElementById('notifications-panel');
  const markAllForm = document.getElementById('mark-all-read-form');

  const listUrl = new URL(panel.dataset.listUrl || window.location.pathname, window.location.origin);

  const getCurrentState = () => {
    const url = new URL(window.location.href);

    return {
      status: url.searchParams.get('status') || 'all',
      page: url.searchParams.get('page') || '1',
    };
  };

  const getLinkState = (link) => {
    const url = new URL(link.href, window.location.origin);

    return {
      status: url.searchParams.get('status'),
      page: url.searchParams.get('page'),
    };
  };

  const buildListUrl = (status, page, partial = true) => {
    const url = new URL(listUrl);
    url.searchParams.set('status', status);
    url.searchParams.set('page', page);

    // Partial - for AJAX requests
    if (partial) {
      url.searchParams.set('partial', '1');
    }

    return url;
  };

  const updateHistory = (status, page) => {
    const url = new URL(listUrl);
    url.searchParams.set('status', status);
    url.searchParams.set('page', page);
    window.history.pushState({}, '', url.toString());
  };

  const requestForm = async (form) => {
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
      });

      return response.ok;
    } catch {
      return false;
    }
  };

  const fetchPanel = async (status, page = '1', pushHistory = false) => {
    try {
      const response = await fetch(buildListUrl(status, page).toString(), {
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
      });

      if (!response.ok) {
        window.location.href = buildListUrl(status, page, false).toString();
        return;
      }

      panel.innerHTML = await response.text();

      if (pushHistory) {
        updateHistory(status, page);
      }
    } catch {
      window.location.href = buildListUrl(status, page, false).toString();
    }
  };

  panel.addEventListener('click', async (event) => {
    const tab = event.target.closest('[data-notification-tab]');
    if (tab && panel.contains(tab)) {
      event.preventDefault();
      const { status } = getLinkState(tab);
      await fetchPanel(status, '1', true);
      return;
    }

    const pageLink = event.target.closest('[data-notification-page]');
    if (pageLink && panel.contains(pageLink)) {
      event.preventDefault();
      const { status, page } = getLinkState(pageLink);
      await fetchPanel(status, page, true);
    }
  });

  panel.addEventListener('submit', async (event) => {
    const form = event.target.closest('form[data-mark-read-form]');
    if (!form || !panel.contains(form)) {
      return;
    }

    event.preventDefault();

    const success = await requestForm(form);
    if (!success) {
      window.location.reload();
      return;
    }

    const { status, page } = getCurrentState();
    await fetchPanel(status, page, false);
  });

  if (markAllForm) {
    markAllForm.addEventListener('submit', async (event) => {
      event.preventDefault();

      const success = await requestForm(markAllForm);
      if (!success) {
        window.location.reload();
        return;
      }

      const { status, page } = getCurrentState();
      await fetchPanel(status, page, false);
    });
  }

  window.addEventListener('popstate', () => {
    const { status, page } = getCurrentState();
    fetchPanel(status, page, false);
  });
})();
