(() => {
  const root = document.documentElement;
  const body = document.body;
  const button = document.getElementById('themeBtn');
  const masthead = document.querySelector('.masthead');
  const footer = document.querySelector('.footer');
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

  const fitViewport = () => {
    if (masthead) root.style.setProperty('--topbar', `${masthead.offsetHeight}px`);
    const intro = document.querySelector('.overview-intro');
    const compact = body.classList.contains('diagram-page-body') || body.classList.contains('landing-overview');
    root.style.setProperty('--intro', `${body.classList.contains('landing-overview') && intro ? intro.offsetHeight : 0}px`);
    root.style.setProperty('--footer', `${compact && footer ? footer.offsetHeight : 0}px`);
  };

  const embeddedStyle = `
    html.embed, html.embed body { width: 100% !important; height: 100% !important; margin: 0 !important; padding: 0 !important; min-height: 0 !important; overflow: hidden !important; }
    html.embed body { display: block !important; }
    html.embed [data-motion-root] { display: grid !important; grid-template-rows: minmax(0, 1fr) auto !important; width: 100% !important; height: 100vh !important; min-height: 0 !important; }
    html.embed .topbar, html.embed .theme, html.embed .eyebrow, html.embed #panel { display: none !important; }
    html.embed .diagram-container { display: flex !important; align-items: center !important; justify-content: center !important; min-width: 0 !important; min-height: 0 !important; height: 100% !important; overflow: hidden !important; }
    html.embed .diagram-container > svg.embed-primary-svg { display: block !important; width: 100% !important; height: 100% !important; min-width: 0 !important; max-width: 100% !important; max-height: 100% !important; flex: none !important; }
    html.embed [data-motion-controls] { display: flex !important; min-width: 0 !important; min-height: 0 !important; flex-wrap: wrap !important; gap: 6px !important; margin: 0 !important; padding: 6px 0 !important; }
    html.embed [data-motion-controls] button { min-width: 0 !important; min-height: 36px !important; padding: 6px 9px !important; }
    html.embed [data-motion-status-visible] { margin-left: auto !important; white-space: nowrap !important; }
    html.embed .pop:target, html.embed .box-card:target, html.embed .phase-pop:target { position: fixed !important; z-index: 100 !important; top: 50% !important; left: 50% !important; width: min(400px, 92vw) !important; max-width: min(400px, 92vw) !important; max-height: calc(100vh - 32px) !important; overflow: auto !important; transform: translate(-50%, -50%) !important; }
    html.embed .keyboard-help { display: none !important; }
  `;

  const applyFrameTheme = (frame) => {
    try {
      const doc = frame.contentDocument;
      if (!doc) return;
      const theme = root.dataset.theme || 'auto';
      if (theme === 'auto') delete doc.documentElement.dataset.theme;
      else doc.documentElement.dataset.theme = theme;
      const radio = doc.getElementById(`t-${theme}`);
      if (radio) radio.checked = true;
    } catch (_) {}
  };

  const prepareFrame = (frame) => {
    try {
      const doc = frame.contentDocument;
      if (!doc) return;
      doc.documentElement.classList.add('embed');
      if (!doc.getElementById('site-embed-style')) {
        const style = doc.createElement('style');
        style.id = 'site-embed-style';
        style.textContent = embeddedStyle;
        doc.head.append(style);
      }
      const primarySvg = [...doc.querySelectorAll('.diagram-container > svg[viewBox]')].find((svg) => {
        const visible = doc.defaultView.getComputedStyle(svg).display !== 'none';
        return visible && svg.querySelector('a[href^="#box-"]');
      }) || [...doc.querySelectorAll('.diagram-container > svg[viewBox]')].find((svg) => doc.defaultView.getComputedStyle(svg).display !== 'none');
      primarySvg?.classList.add('embed-primary-svg');
      const controls = doc.querySelector('[data-motion-controls]');
      if (controls) doc.documentElement.style.setProperty('--embed-controls-height', `${Math.ceil(controls.getBoundingClientRect().height + 18)}px`);
      applyFrameTheme(frame);
      if (!doc.documentElement.dataset.closeWired) {
        doc.documentElement.dataset.closeWired = '1';
        doc.addEventListener('click', (event) => {
          if (event.target.closest('a, .pop:target, .box-card:target, .phase-pop:target')) return;
          closeCard(doc.defaultView);
        });
        doc.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeCard(doc.defaultView); });
      }
    } catch (_) {}
  };

  // Close an open box or step card on a click outside it, or on Escape.
  const closeCard = (win) => {
    if (/^#(box|pop)-/.test(win.location.hash)) win.location.hash = '#close-card';
  };
  const closeAllCards = () => frames().forEach((frame) => { try { closeCard(frame.contentWindow); } catch (_) {} });
  document.addEventListener('click', (event) => {
    if (!event.target.closest('a[target="diagram-frame"]')) closeAllCards();
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeAllCards(); });

  const frameSource = (frame) => `${frame.dataset.embed || frame.getAttribute('src').split('#')[0]}${location.hash}`;
  const forwardHash = () => {
    document.querySelectorAll('iframe.diagram-frame[data-forward-hash]').forEach((frame) => {
      const wanted = frameSource(frame);
      if (frame.getAttribute('src') !== wanted) frame.setAttribute('src', wanted);
    });
  };

  const frames = () => document.querySelectorAll('iframe.diagram-frame');
  frames().forEach((frame) => frame.addEventListener('load', () => prepareFrame(frame)));

  paint();
  fitViewport();
  forwardHash();

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
    frames().forEach(applyFrameTheme);
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
    body.classList.toggle('landing-overview', key === 'overview');
    fitViewport();
  };

  tabs.forEach((tab) => tab.addEventListener('click', () => { location.hash = tab.dataset.tab; }));
  addEventListener('hashchange', () => { show(); forwardHash(); });
  addEventListener('load', () => { fitViewport(); forwardHash(); });
  addEventListener('resize', fitViewport);
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => frames().forEach(applyFrameTheme));
  show();
})();
