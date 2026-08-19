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

    const fail = (reason) => {
      restorePageContent(source, pages);
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

      // A component that cannot fit on an empty physical page falls back to the
      // proven continuous renderer instead of clipping or inner scrolling.
      if (overflows(current)) {
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
    };

    const go = (index) => {
      const next = Math.max(0, Math.min(leaves.length - 1, index));
      if (next === active) return;
      rotations[active] = 0;
      active = next;
      rotations[active] = 0;
      update();
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
      if (!shell.isConnected || event.altKey || event.ctrlKey || event.metaKey) return;
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
    readerCleanup?.();
    readerCleanup = null;
    if (mounted && reader?.isConnected && originalTemplate) {
      reader.replaceWith(originalTemplate.cloneNode(true));
    }
    mounted = false;
    reader = null;
    document.documentElement.dataset.notebookReader = state;
    delete document.documentElement.dataset.notebookPages;
    syncViewSwitch();
  };

  const mount = async () => {
    if (mounted || mounting || effectiveMode() !== 'pages') return;
    const grid = document.querySelector('.study-grid');
    const source = grid?.querySelector(':scope > article');
    if (!source || !PAGED_KINDS.has(source.dataset.kind || '')) return;

    if (!originalTemplate) originalTemplate = source.cloneNode(true);
    mounting = true;
    await waitForAssets(source);
    if (effectiveMode() !== 'pages' || !source.isConnected) {
      mounting = false;
      syncViewSwitch();
      return;
    }

    const {shell, stack, status} = createReaderShell();
    grid.insertBefore(shell, source);
    const pages = paginate(source, stack);
    if (!pages) {
      shell.remove();
      mounting = false;
      syncViewSwitch();
      return;
    }

    // A one-page artifact gains nothing from the reader.
    if (pages.length < 2) {
      restorePageContent(source, pages);
      shell.remove();
      mounting = false;
      document.documentElement.dataset.notebookReader = 'continuous';
      syncViewSwitch();
      return;
    }

    reader = buildReader(source, pages, shell, stack, status);
    source.remove();
    mounted = true;
    mounting = false;
    document.documentElement.dataset.notebookReader = 'ready';
    document.documentElement.dataset.notebookPages = String(pages.length);
    syncViewSwitch();
  };

  const setViewMode = (mode, {persist = true} = {}) => {
    if (mode !== 'continuous' && mode !== 'pages') return;
    if (mode === 'pages' && !desktop.matches) return;
    preferredMode = mode;
    if (persist) writeStoredMode(mode);

    if (effectiveMode() === 'pages') {
      mount();
    } else {
      restoreContinuous('continuous');
    }
    syncViewSwitch();
  };

  const toggleViewMode = () => {
    if (!desktop.matches || print.matches) return;
    const next = mounted || mounting ? 'continuous' : 'pages';
    setViewMode(next);
    showModeToast(next);
  };

  const isEditableTarget = (target) => {
    const tag = target?.tagName?.toLowerCase();
    return tag === 'input' || tag === 'textarea' || target?.isContentEditable;
  };

  const onViewShortcut = (event) => {
    if (event.repeat || event.altKey || event.ctrlKey || event.metaKey) return;
    if (isEditableTarget(event.target)) return;
    if (event.key?.toLowerCase() !== 'v') return;
    if (!desktop.matches || print.matches) return;
    event.preventDefault();
    toggleViewMode();
  };

  const restoreForPrint = () => {
    if (mounted) restoreContinuous('print-continuous');
  };

  const init = () => {
    const source = document.querySelector('.study-grid > article');
    if (!source || !PAGED_KINDS.has(source.dataset.kind || '')) return;
    originalTemplate = source.cloneNode(true);
    createViewSwitch();
    document.addEventListener('keydown', onViewShortcut);
    if (effectiveMode() === 'pages') mount();
    else {
      document.documentElement.dataset.notebookReader = 'continuous';
      syncViewSwitch();
    }
  };

  window.addEventListener('beforeprint', restoreForPrint);
  window.addEventListener('afterprint', () => {
    if (effectiveMode() === 'pages') mount();
  });
  desktop.addEventListener?.('change', () => {
    if (effectiveMode() === 'pages') mount();
    else restoreContinuous('continuous');
    syncViewSwitch();
  });

  init();
})();