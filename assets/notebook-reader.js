(() => {
  const PAGED_KINDS = new Set(['summary', 'rapid-review', 'learn', 'explain']);
  const STORAGE_KEY = 'university-study:reader-mode';
  const desktop = window.matchMedia('(min-width: 48.01rem)');
  const print = window.matchMedia('print');

  let mounted = false;
  let mounting = false;
  let originalTemplate = null;
  let reader = null;
  let readerCleanup = null;
  let viewSwitch = null;
  let toastTimer = null;
  let pageModeUnavailable = null;
  let topicNavigator = null;
  let topicPanel = null;
  let topicPanelReturnFocus = null;
  let topicScrollCleanup = null;
  let readerNavigatePage = null;
  let topics = [];
  let activeTopicIndex = 0;

  const readStoredMode = () => {
    try {
      const value = window.localStorage?.getItem(STORAGE_KEY);
      return value === 'continuous' || value === 'pages' ? value : null;
    } catch (_) {
      return null;
    }
  };

  const writeStoredMode = (value) => {
    try { window.localStorage?.setItem(STORAGE_KEY, value); } catch (_) {}
  };

  // Pages remain the desktop/tablet default so existing artifacts keep the
  // experience they already had. Mobile keeps the continuous renderer until a
  // dedicated small-screen physical reader exists.
  let preferredMode = readStoredMode() || 'pages';

  const effectiveMode = () => (
    preferredMode === 'pages' && desktop.matches && !print.matches ? 'pages' : 'continuous'
  );

  const waitForAssets = async (root) => {
    const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    if (document.fonts?.ready) {
      try { await Promise.race([document.fonts.ready, delay(900)]); } catch (_) {}
    }
    const images = Array.from(root.querySelectorAll('img'));
    for (const img of images) img.loading = 'eager';
    await Promise.all(images.map(async (img) => {
      if (!img.complete) {
        await Promise.race([
          new Promise((resolve) => {
            img.addEventListener('load', resolve, {once: true});
            img.addEventListener('error', resolve, {once: true});
          }),
          delay(1800),
        ]);
      }
      if (typeof img.decode === 'function' && img.complete) {
        try { await Promise.race([img.decode(), delay(900)]); } catch (_) {}
      }
    }));
  };

  const cssLengthPx = (style, name, fallback) => {
    const rootPx = parseFloat(style.fontSize) || 16;
    const token = style.getPropertyValue(name).trim();
    if (token.endsWith('rem')) return parseFloat(token) * rootPx;
    if (token.endsWith('px')) return parseFloat(token);
    return parseFloat(token) || fallback;
  };

  const isEditableTarget = (target) => {
    const tag = target?.tagName?.toLowerCase();
    return tag === 'input' || tag === 'textarea' || target?.isContentEditable;
  };

  const isHeadingLike = (node) => node?.matches?.('.section-head, .subsection-head, .minor-head');

  const makePage = (source, pageIndex) => {
    const page = source.cloneNode(false);
    const back = pageIndex % 2 === 1;
    page.className = `notebook-page ${back ? 'notebook-back' : 'notebook-front'}`;
    page.dataset.page = String(pageIndex + 1);
    page.dataset.side = back ? 'back' : 'front';
    page.removeAttribute('id');
    return page;
  };

  const restorePageContent = (source, pages) => {
    for (const page of pages || []) {
      for (const node of Array.from(page.children)) source.appendChild(node);
    }
  };

  const clearPageFit = (node) => {
    node?.classList?.remove('notebook-fit-page');
    node?.style?.removeProperty('--notebook-fit-block-height');
  };

  const clearPaginationMarks = (root) => {
    root?.querySelectorAll?.('.notebook-fit-page').forEach(clearPageFit);
    root?.querySelectorAll?.('[data-notebook-figure-number]').forEach((figure) => {
      delete figure.dataset.notebookFigureNumber;
    });
    root?.querySelectorAll?.('[data-notebook-topic-number]').forEach((mark) => {
      delete mark.dataset.notebookTopicNumber;
    });
  };

  const restoreScrollPosition = ({left, top}) => {
    window.scrollTo({left, top, behavior: 'instant'});
    window.requestAnimationFrame(() => window.scrollTo({left, top, behavior: 'instant'}));
  };

  const collectTopics = (source) => Array.from(
    source.querySelectorAll(':scope > .section-head > h2[id]')
  ).map((heading, index) => {
    const section = heading.parentElement;
    section?.classList.add('notebook-section-tab');
    if (section) {
      section.dataset.topicIndex = String(index);
      section.dataset.topicNumber = String(index + 1);
    }
    return {
      id: heading.id,
      index,
      label: heading.textContent.trim(),
      number: index + 1,
      page: null,
    };
  });

  const setActiveTopic = (index) => {
    if (!topics.length) return;
    activeTopicIndex = Math.max(0, Math.min(topics.length - 1, index));
    const current = String(activeTopicIndex);
    document.querySelectorAll('.section-head.notebook-section-tab[data-topic-index]').forEach((section) => {
      section.classList.toggle('is-current-topic', section.dataset.topicIndex === current);
    });
    for (const root of [topicNavigator, topicPanel]) {
      if (!root) continue;
      root.querySelectorAll('[data-topic-index]').forEach((button) => {
        const active = button.dataset.topicIndex === current;
        if (active) button.setAttribute('aria-current', 'location');
        else button.removeAttribute('aria-current');
      });
      root.dataset.activeTopic = String(activeTopicIndex + 1);
    }
    document.documentElement.dataset.notebookTopic = String(activeTopicIndex + 1);
  };

  const setTopicPanel = (open, {focus = true} = {}) => {
    if (!topicNavigator || !topicPanel) return;
    if (open && topicPanel.hidden) {
      const active = document.activeElement;
      topicPanelReturnFocus = active instanceof HTMLElement
        && active !== document.body
        && active !== document.documentElement
        ? active
        : null;
    }
    topicPanel.hidden = !open;
    topicNavigator.dataset.open = open ? 'true' : 'false';
    if (open) {
      document.documentElement.dataset.notebookTopicIndex = 'open';
      if (focus) {
        window.requestAnimationFrame(() => {
          topicPanel.querySelector(`[data-topic-index="${activeTopicIndex}"]`)?.focus();
        });
      }
    } else {
      delete document.documentElement.dataset.notebookTopicIndex;
      if (focus && topicPanelReturnFocus?.isConnected) {
        topicPanelReturnFocus.focus({preventScroll: true});
      }
      topicPanelReturnFocus = null;
    }
  };

  const focusTopicHeading = (topic, root = document) => {
    const heading = Array.from(root.querySelectorAll?.('h2[id]') || [])
      .find((node) => node.id === topic.id);
    if (!heading) return;
    heading.tabIndex = -1;
    heading.focus({preventScroll: true});
  };

  const navigateToTopic = (index) => {
    const topic = topics[index];
    if (!topic) return;
    setActiveTopic(index);
    setTopicPanel(false, {focus: false});

    if (mounted && topic.page && readerNavigatePage) {
      readerNavigatePage(topic.page);
      window.requestAnimationFrame(() => focusTopicHeading(topic, reader || document));
      return;
    }

    const heading = document.getElementById(topic.id);
    if (!heading) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    heading.scrollIntoView({behavior: reduced ? 'auto' : 'smooth', block: 'start'});
    window.setTimeout(() => focusTopicHeading(topic), reduced ? 0 : 320);
  };

  const makeTopicButton = (topic, className) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.dataset.topicIndex = String(topic.index);
    button.setAttribute('aria-controls', topic.id);
    button.setAttribute('aria-label', `Ir al Tema ${topic.number}: ${topic.label}`);
    button.title = `Tema ${topic.number} · ${topic.label}`;
    const ordinal = document.createElement('span');
    ordinal.className = 'notebook-topic-item-number';
    ordinal.textContent = `Tema ${topic.number}`;
    const label = document.createElement('span');
    label.className = 'notebook-topic-item-label';
    label.textContent = topic.label;
    button.append(ordinal, label);
    button.addEventListener('click', () => navigateToTopic(topic.index));
    return button;
  };

  const createTopicNavigation = () => {
    if (topicNavigator || topics.length < 2) return;

    // Keep a zero-chrome host for reader-mode state. The index is deliberately
    // summoned only with T: a permanently visible shortcut label competes with
    // the physical topic tabs and will be replaced by the shared shortcuts UI.
    const nav = document.createElement('div');
    nav.className = 'notebook-topic-tabs is-detached';
    nav.setAttribute('aria-hidden', 'true');
    nav.hidden = true;

    const panel = document.createElement('section');
    panel.id = 'notebook-topic-index-panel';
    panel.className = 'notebook-topic-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'false');
    panel.setAttribute('aria-labelledby', 'notebook-topic-index-title');
    panel.setAttribute('aria-keyshortcuts', 'T');
    panel.hidden = true;

    const panelHead = document.createElement('div');
    panelHead.className = 'notebook-topic-panel-head';
    const panelTitle = document.createElement('h2');
    panelTitle.id = 'notebook-topic-index-title';
    panelTitle.textContent = 'Índice de temas';
    const shortcut = document.createElement('span');
    shortcut.className = 'notebook-topic-panel-shortcut';
    shortcut.innerHTML = '<kbd>T</kbd> abrir / cerrar';
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'notebook-topic-panel-close';
    close.setAttribute('aria-label', 'Cerrar índice de temas');
    close.textContent = 'Cerrar';
    close.addEventListener('click', () => setTopicPanel(false));
    panelHead.append(panelTitle, shortcut, close);

    const list = document.createElement('ol');
    list.className = 'notebook-topic-list';
    topics.forEach((topic) => {
      const item = document.createElement('li');
      item.appendChild(makeTopicButton(topic, 'notebook-topic-list-button'));
      list.appendChild(item);
    });
    const hint = document.createElement('p');
    hint.className = 'notebook-topic-panel-hint';
    hint.textContent = '↑ ↓ para recorrer · Enter para ir · Esc para cerrar';
    panel.append(panelHead, list, hint);

    document.body.append(nav, panel);
    topicNavigator = nav;
    topicPanel = panel;
    setActiveTopic(0);

    document.addEventListener('pointerdown', (event) => {
      if (topicPanel?.hidden !== false) return;
      if (topicPanel.contains(event.target) || topicNavigator.contains(event.target)) return;
      setTopicPanel(false, {focus: false});
    });
  };

  const detachTopicNavigation = () => {
    topicScrollCleanup?.();
    topicScrollCleanup = null;
    if (topicNavigator) {
      topicNavigator.hidden = true;
      topicNavigator.classList.add('is-detached');
    }
    topicNavigator?.remove();
    document.querySelectorAll('.notebook-topic-host').forEach((host) => {
      host.classList.remove('notebook-topic-host');
    });
  };

  const bindContinuousTopicTracking = () => {
    topicScrollCleanup?.();
    let frame = 0;
    const update = () => {
      frame = 0;
      const threshold = Math.min(window.innerHeight * .28, 240);
      let current = 0;
      topics.forEach((topic, index) => {
        const heading = document.getElementById(topic.id);
        if (heading && heading.getBoundingClientRect().top <= threshold) current = index;
      });
      // The last heading of a short document cannot always reach the threshold.
      // Treat the physical end of the article as the final topic so a direct
      // jump and manual scrolling agree on the selected tab.
      const atDocumentEnd = window.scrollY + window.innerHeight
        >= document.documentElement.scrollHeight - 2;
      if (atDocumentEnd) current = topics.length - 1;
      setActiveTopic(current);
    };
    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    window.addEventListener('scroll', schedule, {passive: true});
    window.addEventListener('resize', schedule);
    topicScrollCleanup = () => {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      if (frame) window.cancelAnimationFrame(frame);
    };
    update();
  };

  const attachTopicNavigation = (mode, host) => {
    if (!topicNavigator || !host) return;
    detachTopicNavigation();
    topicNavigator.hidden = false;
    topicNavigator.classList.remove('is-detached');
    topicNavigator.classList.toggle('is-paged', mode === 'pages');
    topicNavigator.classList.toggle('is-continuous', mode === 'continuous');
    host.appendChild(topicNavigator);
    if (mode === 'continuous') {
      host.classList.add('notebook-topic-host');
      topicNavigator.dataset.readerSide = 'front';
      bindContinuousTopicTracking();
    }
  };

  const mapTopicPages = (pages) => {
    topics.forEach((topic) => {
      const page = pages.find((candidate) => Array.from(candidate.querySelectorAll('h2[id]'))
        .some((heading) => heading.id === topic.id));
      topic.page = page ? Number(page.dataset.page) : null;
    });
  };

  const syncTopicFromPage = (physicalPage, back) => {
    if (!topics.length) return;
    let current = 0;
    topics.forEach((topic, index) => {
      if (topic.page && topic.page <= physicalPage) current = index;
    });
    if (topicNavigator) topicNavigator.dataset.readerSide = back ? 'back' : 'front';
    setActiveTopic(current);
  };

  const onTopicShortcut = (event) => {
    if (event.repeat || event.altKey || event.ctrlKey || event.metaKey) return;
    if (isEditableTarget(event.target) || !topicNavigator || print.matches) return;
    const key = event.key?.toLowerCase();
    if (key === 't') {
      event.preventDefault();
      setTopicPanel(topicPanel?.hidden !== false);
      return;
    }
    if (topicPanel?.hidden !== false) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      setTopicPanel(false);
      return;
    }
    if (!['ArrowDown', 'ArrowRight', 'ArrowUp', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const buttons = Array.from(topicPanel.querySelectorAll('[data-topic-index]'));
    const current = Math.max(0, buttons.indexOf(document.activeElement));
    let next = current;
    if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = buttons.length - 1;
    else if (event.key === 'ArrowDown' || event.key === 'ArrowRight') next = (current + 1) % buttons.length;
    else next = (current - 1 + buttons.length) % buttons.length;
    buttons[next]?.focus();
  };

  const syncViewSwitch = () => {
    if (!viewSwitch) return;
    const actualMode = mounted ? 'pages' : 'continuous';
    viewSwitch.dataset.mode = actualMode;
    viewSwitch.querySelectorAll('[data-reader-mode]').forEach((button) => {
      const mode = button.dataset.readerMode;
      button.setAttribute('aria-pressed', mode === actualMode ? 'true' : 'false');
      if (mode === 'pages') {
        button.disabled = !desktop.matches;
        button.title = desktop.matches
          ? 'Leer como hojas físicas'
          : 'La vista por hojas está disponible en tablet y escritorio';
      }
    });
  };

  // The old visual switch is kept as hidden semantic state for compatibility;
  // the user-facing interaction is now the V keyboard shortcut.
  const createViewSwitch = () => {
    if (viewSwitch) return viewSwitch;
    const control = document.createElement('div');
    control.className = 'notebook-view-switch';
    control.setAttribute('role', 'group');
    control.setAttribute('aria-label', 'Modo de lectura');
    control.innerHTML = `
      <span class="notebook-view-switch-label">Vista</span>
      <button type="button" data-reader-mode="continuous" aria-pressed="false">Continua</button>
      <button type="button" data-reader-mode="pages" aria-pressed="false">Hojas</button>
    `;
    document.body.appendChild(control);
    viewSwitch = control;
    syncViewSwitch();
    return control;
  };

  const showModeToast = (mode) => {
    let toast = document.querySelector('.notebook-mode-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'notebook-mode-toast';
      toast.setAttribute('role', 'status');
      toast.setAttribute('aria-live', 'polite');
      document.body.appendChild(toast);
    }
    toast.textContent = mode === 'pages' ? 'Vista Hojas · V' : 'Vista Continua · V';
    toast.classList.add('is-visible');
    if (toastTimer) window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.remove('is-visible'), 1200);
  };

  const createReaderShell = () => {
    const shell = document.createElement('section');
    shell.className = 'notebook-reader is-measuring';
    shell.setAttribute('aria-label', 'Cuaderno paginado');

    const stack = document.createElement('div');
    stack.className = 'notebook-stack';
    shell.appendChild(stack);

    const status = document.createElement('div');
    status.className = 'notebook-reader-status';
    status.setAttribute('aria-live', 'polite');
    shell.appendChild(status);

    return {shell, stack, status};
  };

  const paginate = (source, stack) => {
    const nodes = Array.from(source.children);
    source.querySelectorAll(':scope > .section-head').forEach((heading, index) => {
      const mark = heading.querySelector(':scope > .num');
      if (mark) mark.dataset.notebookTopicNumber = String(index + 1);
    });
    source.querySelectorAll('figure').forEach((figure, index) => {
      const number = String(index + 1);
      figure.dataset.notebookFigureNumber = number;
      const caption = figure.querySelector(':scope > figcaption');
      if (caption) caption.dataset.notebookFigureNumber = number;
    });
    const measure = document.createElement('div');
    measure.className = 'notebook-measure-host';
    stack.appendChild(measure);

    // notebook-page already has a fixed border-box height. Its scrollHeight is
    // therefore equal to clientHeight even when it is empty. The real scroll
    // overflow is the deterministic packing signal.
    const overflows = (page) => page.scrollHeight > page.clientHeight + 1;

    const pages = [];
    let current = makePage(source, 0);
    measure.appendChild(current);
    pages.push(current);

    const fitStudySketch = (page, node) => {
      if (!node.matches?.('figure.study-sketch')) return false;

      const originalHeight = node.getBoundingClientRect().height;
      const firstTarget = Math.floor(originalHeight - (page.scrollHeight - page.clientHeight) - 2);
      const minimumReadableHeight = Math.floor(page.clientHeight * .55);
      if (firstTarget < minimumReadableHeight) return false;

      node.style.setProperty('--notebook-fit-block-height', `${firstTarget}px`);
      node.classList.add('notebook-fit-page');

      // Grid/caption rounding can leave a residual pixel or two. Tighten the
      // fitted block once more using the rendered overflow instead of clipping.
      if (overflows(page)) {
        const renderedHeight = node.getBoundingClientRect().height;
        const correctedTarget = Math.floor(renderedHeight - (page.scrollHeight - page.clientHeight) - 2);
        if (correctedTarget < minimumReadableHeight) {
          clearPageFit(node);
          return false;
        }
        node.style.setProperty('--notebook-fit-block-height', `${correctedTarget}px`);
      }

      if (!overflows(page)) return true;
      clearPageFit(node);
      return false;
    };

    const fail = (reason) => {
      restorePageContent(source, pages);
      clearPaginationMarks(source);
      measure.remove();
      source.dataset.notebookReaderFallback = reason;
      document.documentElement.dataset.notebookReader = 'continuous-fallback';
      return null;
    };

    for (const node of nodes) {
      current.appendChild(node);
      if (!overflows(current)) continue;

      current.removeChild(node);

      // Never strand a heading at the bottom of a physical page.
      let carry = null;
      const last = current.lastElementChild;
      if (isHeadingLike(last) && current.children.length > 1) {
        carry = last;
        current.removeChild(last);
      }

      current = makePage(source, pages.length);
      measure.appendChild(current);
      pages.push(current);
      if (carry) current.appendChild(carry);
      current.appendChild(node);

      // Tall deterministic sketches may shrink to a dedicated leaf while their
      // SVG keeps its aspect ratio. Any other indivisible oversize component
      // falls back to the proven continuous renderer.
      if (overflows(current) && !fitStudySketch(current, node)) {
        return fail(`oversize-block:${node.className || node.tagName.toLowerCase()}`);
      }
    }

    if (pages.some(overflows)) return fail('post-pagination-overflow');
    measure.remove();
    return pages;
  };

  // `edge` is the handle's position inside its own face. The reverse face is
  // mirrored by rotateY(180deg), so its start edge is drawn on the screen right.
  const makeTurnCorner = (face, side, edge, getRotation, setRotation) => {
    const screenSign = (side === 'back' ? -1 : 1) * (edge === 'end' ? 1 : -1);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'notebook-turn-corner';
    button.dataset.edge = edge;
    button.setAttribute(
      'aria-label',
      side === 'back' ? 'Volver al frente de la hoja' : 'Dar vuelta la hoja'
    );
    face.appendChild(button);

    let dragged = false;
    let x0 = 0;
    let base = 0;
    let angle = 0;

    const move = (event) => {
      const dx = event.clientX - x0;
      if (!dragged && Math.abs(dx) < 7) return;
      dragged = true;
      button.classList.add('is-dragging');
      angle = Math.max(base - 180, Math.min(base + 180, base - dx * .42));
      setRotation(angle, true);
    };

    const finish = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', finish);
      window.removeEventListener('pointercancel', finish);
      button.classList.remove('is-dragging');
      if (!dragged) return;
      setRotation(Math.round(angle / 180) * 180);
      setTimeout(() => { dragged = false; }, 0);
    };

    button.addEventListener('pointerdown', (event) => {
      if (event.button > 0) return;
      event.preventDefault();
      event.stopPropagation();
      x0 = event.clientX;
      base = getRotation();
      angle = base;
      dragged = false;
      button.setPointerCapture?.(event.pointerId);
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', finish, {once: true});
      window.addEventListener('pointercancel', finish, {once: true});
    });

    button.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (dragged) return;
      setRotation(getRotation() + screenSign * 180);
    });
  };

  const buildReader = (source, pages, shell, stack, status) => {
    const pagePairs = [];
    for (let i = 0; i < pages.length; i += 2) {
      pagePairs.push([pages[i], pages[i + 1] || makePage(source, i + 1)]);
    }

    let active = 0;
    const rotations = Array(pagePairs.length).fill(0);
    const leaves = [];
    const sideIsBack = (deg) => Math.abs(Math.round(deg / 180)) % 2 === 1;

    const update = () => {
      const rootStyle = getComputedStyle(document.documentElement);
      const peek = cssLengthPx(rootStyle, '--notebook-leaf-peek', 45.6);
      const hoverExtra = cssLengthPx(rootStyle, '--notebook-leaf-hover-extra', 12);

      leaves.forEach((leaf, index) => {
        const d = index - active;
        const distance = Math.abs(d);
        leaf.classList.toggle('is-active', d === 0);
        leaf.classList.toggle('is-neighbor', distance === 1);
        leaf.classList.toggle('is-hidden', distance > 1);
        // Keep distant sheets out of sight via opacity while leaving their text
        // in the rendered DOM. aria-hidden still excludes them from assistive
        // navigation until the sheet becomes active or adjacent.
        leaf.style.visibility = distance > 1 ? 'visible' : '';
        leaf.style.zIndex = String(20 - Math.min(distance, 19));
        leaf.tabIndex = distance === 1 ? 0 : -1;
        leaf.setAttribute('aria-hidden', distance > 1 ? 'true' : 'false');

        if (d === 0) {
          leaf.style.transform = `translateX(0) scale(1) rotateY(${rotations[index].toFixed(2)}deg)`;
          return;
        }

        // visibility:hidden still has geometry. Hidden sheets therefore stay at
        // x=0 so only the two intentional neighbour peeks affect the stack.
        if (distance > 1) {
          leaf.style.transform = 'translateX(0) scale(var(--notebook-leaf-scale)) rotateY(0deg)';
          return;
        }

        const hoverBoost = leaf.matches(':hover') ? hoverExtra : 0;
        leaf.style.transform = `translateX(${d * (peek + hoverBoost)}px) scale(var(--notebook-leaf-scale)) rotateY(0deg)`;
      });

      const back = sideIsBack(rotations[active]);
      const physicalPage = active * 2 + (back ? 2 : 1);
      status.textContent = `Hoja ${active + 1} de ${leaves.length} · ${back ? 'dorso' : 'frente'} · p. ${Math.min(physicalPage, pages.length)}`;
      shell.dataset.activeLeaf = String(active + 1);
      shell.dataset.activeSide = back ? 'back' : 'front';
      syncTopicFromPage(Math.min(physicalPage, pages.length), back);
    };

    const go = (index, {back = false} = {}) => {
      const next = Math.max(0, Math.min(leaves.length - 1, index));
      const targetRotation = back ? 180 : 0;
      if (next !== active) {
        rotations[active] = 0;
        active = next;
      }
      rotations[active] = targetRotation;
      update();
    };

    readerNavigatePage = (pageNumber) => {
      const targetPage = Math.max(1, Math.min(pages.length, Number(pageNumber) || 1));
      go(Math.floor((targetPage - 1) / 2), {back: targetPage % 2 === 0});
    };

    pagePairs.forEach(([front, back], index) => {
      const leaf = document.createElement('div');
      leaf.className = 'notebook-leaf';
      leaf.dataset.leaf = String(index + 1);

      const frontFace = document.createElement('div');
      frontFace.className = 'notebook-face notebook-front-face notebook-front';
      front.classList.add('notebook-front');
      front.dataset.page = String(index * 2 + 1);
      frontFace.appendChild(front);

      const backFace = document.createElement('div');
      backFace.className = 'notebook-face notebook-back-face notebook-back';
      back.classList.add('notebook-back');
      back.dataset.page = String(index * 2 + 2);
      backFace.appendChild(back);

      const numberFront = document.createElement('div');
      numberFront.className = 'notebook-page-number';
      numberFront.textContent = `— ${index * 2 + 1} —`;
      frontFace.appendChild(numberFront);

      const numberBack = document.createElement('div');
      numberBack.className = 'notebook-page-number';
      numberBack.textContent = `— ${index * 2 + 2} —`;
      backFace.appendChild(numberBack);

      const setRotation = (value, dragging = false) => {
        rotations[index] = value;
        leaf.style.transition = dragging ? 'none' : '';
        update();
        if (!dragging) requestAnimationFrame(() => { leaf.style.transition = ''; });
      };
      const getRotation = () => rotations[index];
      for (const edge of ['start', 'end']) {
        makeTurnCorner(frontFace, 'front', edge, getRotation, setRotation);
        makeTurnCorner(backFace, 'back', edge, getRotation, setRotation);
      }

      leaf.append(frontFace, backFace);
      leaf.addEventListener('pointerdown', (event) => {
        if (index === active || event.target.closest('.notebook-turn-corner')) return;
        event.preventDefault();
        go(index);
      });
      leaf.addEventListener('keydown', (event) => {
        if (index !== active && (event.key === 'Enter' || event.key === ' ')) {
          event.preventDefault();
          go(index);
        }
      });
      leaf.addEventListener('mouseenter', update);
      leaf.addEventListener('mouseleave', update);
      leaves.push(leaf);
      stack.appendChild(leaf);
    });

    const onKeydown = (event) => {
      if (!shell.isConnected || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
      if (topicPanel?.hidden === false) return;
      const activeElement = document.activeElement;
      const tag = activeElement?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || activeElement?.isContentEditable) return;
      if (event.key === 'ArrowRight') { event.preventDefault(); go(active + 1); }
      if (event.key === 'ArrowLeft') { event.preventDefault(); go(active - 1); }
    };
    document.addEventListener('keydown', onKeydown);
    readerCleanup = () => document.removeEventListener('keydown', onKeydown);

    update();
    shell.classList.remove('is-measuring');
    return shell;
  };

  const restoreContinuous = (state = 'continuous') => {
    setTopicPanel(false, {focus: false});
    detachTopicNavigation();
    readerCleanup?.();
    readerCleanup = null;
    readerNavigatePage = null;
    if (mounted && reader?.isConnected && originalTemplate) {
      reader.replaceWith(originalTemplate.cloneNode(true));
    }
    mounted = false;
    reader = null;
    document.documentElement.dataset.notebookReader = state;
    delete document.documentElement.dataset.notebookPages;
    syncViewSwitch();
    attachTopicNavigation('continuous', document.querySelector('.study-grid > article'));
  };

  const mount = async ({persistFallback = false} = {}) => {
    if (mounted) return true;
    if (mounting || effectiveMode() !== 'pages' || pageModeUnavailable) return false;
    const grid = document.querySelector('.study-grid');
    const source = grid?.querySelector(':scope > article');
    if (!source || !PAGED_KINDS.has(source.dataset.kind || '')) return false;

    if (!originalTemplate) originalTemplate = source.cloneNode(true);
    mounting = true;
    await waitForAssets(source);
    if (effectiveMode() !== 'pages' || !source.isConnected) {
      mounting = false;
      syncViewSwitch();
      if (source.isConnected) attachTopicNavigation('continuous', source);
      return false;
    }

    setTopicPanel(false, {focus: false});
    detachTopicNavigation();
    delete source.dataset.notebookReaderFallback;
    const scrollPosition = {left: window.scrollX, top: window.scrollY};
    const {shell, stack, status} = createReaderShell();
    grid.insertBefore(shell, source);
    const pages = paginate(source, stack);
    if (!pages) {
      pageModeUnavailable = source.dataset.notebookReaderFallback || 'pagination-failed';
      shell.remove();
      mounting = false;
      preferredMode = 'continuous';
      if (persistFallback) writeStoredMode('continuous');
      syncViewSwitch();
      attachTopicNavigation('continuous', source);
      restoreScrollPosition(scrollPosition);
      return false;
    }

    // A one-page artifact gains nothing from the reader.
    if (pages.length < 2) {
      restorePageContent(source, pages);
      clearPaginationMarks(source);
      shell.remove();
      mounting = false;
      pageModeUnavailable = 'single-page';
      preferredMode = 'continuous';
      if (persistFallback) writeStoredMode('continuous');
      document.documentElement.dataset.notebookReader = 'continuous';
      syncViewSwitch();
      attachTopicNavigation('continuous', source);
      restoreScrollPosition(scrollPosition);
      return false;
    }

    mapTopicPages(pages);
    reader = buildReader(source, pages, shell, stack, status);
    attachTopicNavigation('pages', stack);
    source.remove();
    mounted = true;
    mounting = false;
    document.documentElement.dataset.notebookReader = 'ready';
    document.documentElement.dataset.notebookPages = String(pages.length);
    syncViewSwitch();
    return true;
  };

  const setViewMode = async (mode, {persist = true} = {}) => {
    if (mode !== 'continuous' && mode !== 'pages') return mounted ? 'pages' : 'continuous';
    if (mode === 'pages' && (!desktop.matches || pageModeUnavailable)) {
      preferredMode = 'continuous';
      if (persist) writeStoredMode('continuous');
      syncViewSwitch();
      return 'continuous';
    }
    preferredMode = mode;
    if (persist) writeStoredMode(mode);

    if (effectiveMode() === 'pages') {
      const ready = await mount({persistFallback: persist});
      return ready ? 'pages' : 'continuous';
    } else {
      restoreContinuous('continuous');
    }
    syncViewSwitch();
    return 'continuous';
  };

  const toggleViewMode = async () => {
    if (!desktop.matches || print.matches) return;
    const next = mounted || mounting ? 'continuous' : 'pages';
    const actual = await setViewMode(next);
    showModeToast(actual);
  };

  const onViewShortcut = (event) => {
    if (event.repeat || event.altKey || event.ctrlKey || event.metaKey) return;
    if (isEditableTarget(event.target)) return;
    if (event.key?.toLowerCase() !== 'v') return;
    if (!desktop.matches || print.matches) return;
    event.preventDefault();
    void toggleViewMode();
  };

  const restoreForPrint = () => {
    if (mounted) restoreContinuous('print-continuous');
  };

  const init = () => {
    const source = document.querySelector('.study-grid > article');
    if (!source) return;
    const pagedEligible = PAGED_KINDS.has(source.dataset.kind || '');
    topics = collectTopics(source);
    createTopicNavigation();
    document.addEventListener('keydown', onTopicShortcut);

    // Long guides keep their established continuous surface and TOC, while
    // sharing the same edge-tab/topic-index contract requested for every
    // semantic top-level topic.
    if (!pagedEligible) {
      attachTopicNavigation('continuous', source);
      return;
    }

    originalTemplate = source.cloneNode(true);
    createViewSwitch();
    document.addEventListener('keydown', onViewShortcut);
    if (effectiveMode() === 'pages') void mount();
    else {
      document.documentElement.dataset.notebookReader = 'continuous';
      syncViewSwitch();
      attachTopicNavigation('continuous', source);
    }
  };

  window.addEventListener('beforeprint', restoreForPrint);
  window.addEventListener('afterprint', () => {
    if (effectiveMode() === 'pages') void mount();
  });
  desktop.addEventListener?.('change', () => {
    pageModeUnavailable = null;
    if (effectiveMode() === 'pages') void mount();
    else restoreContinuous('continuous');
    syncViewSwitch();
  });

  init();
})();
