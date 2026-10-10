(() => {
  const root = document.documentElement;
  const button = document.getElementById('themeBtn');
  const saved = localStorage.getItem('theme');

  if (saved) root.dataset.theme = saved;

  const paint = () => {
    if (button) {
      button.textContent = root.dataset.theme === 'dark'
        ? '◐ Dark'
        : root.dataset.theme === 'light'
          ? '◐ Light'
          : '◐ Auto';
    }
  };

  paint();

  button?.addEventListener('click', () => {
    const next = root.dataset.theme === 'dark'
      ? 'light'
      : root.dataset.theme === 'light'
        ? ''
        : 'dark';

    if (next) {
      root.dataset.theme = next;
      localStorage.setItem('theme', next);
    } else {
      delete root.dataset.theme;
      localStorage.removeItem('theme');
    }

    paint();
  });

  const tabs = [...document.querySelectorAll('[role="tab"]')];
  const show = () => {
    if (!tabs.length) return;

    const wanted = location.hash.slice(1);
    const key = tabs.some((tab) => tab.dataset.tab === wanted) ? wanted : 'overview';

    tabs.forEach((tab) => {
      const selected = tab.dataset.tab === key;
      tab.setAttribute('aria-selected', selected);
      const panel = document.getElementById(tab.dataset.tab);
      if (panel) panel.hidden = !selected;
    });
  };

  tabs.forEach((tab) => tab.addEventListener('click', () => {
    location.hash = tab.dataset.tab;
  }));

  addEventListener('hashchange', show);
  show();

  document.querySelectorAll('iframe.diagram-frame').forEach((frame) => {
    const fit = () => {
      try {
        frame.style.height = `${frame.contentDocument.documentElement.scrollHeight}px`;
      } catch (_) {}
    };

    frame.addEventListener('load', () => {
      fit();
      setTimeout(fit, 500);

      try {
        frame.contentWindow.addEventListener('resize', fit);
      } catch (_) {}
    });
  });
})();
