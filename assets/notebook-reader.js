(() => {
  const PAGED_KINDS = new Set(['summary', 'rapid-review', 'learn', 'explain']);
  const desktop = window.matchMedia('(min-width: 48.01rem)');
  const print = window.matchMedia('print');
  let mounted = false;
  let originalTemplate = null;
  let reader = null;

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

  const pageOverflows = (page) => page.scrollHeight > page.clientHeight + 1;

  const paginate = (source, grid) => {
    const nodes = Array.from(source.children);
    const measure = document.createElement('div');
    measure.className = 'notebook-measure-host';
    grid.appendChild(measure);

    const pages = [];
    let current = makePage(source, 0);
    measure.appendChild(current);
    pages.push(current);

    const fail = (reason) => {
      const all = pages.flatMap((page) => Array.from(page.children));
      for (const node of all) source.appendChild(node);
      measure.remove();
      source.dataset.notebookReaderFallback = reason;
      document.documentElement.dataset.notebookReader = 'continuous-fallback';
      return null;
    };

    for (const node of nodes) {
      current.appendChild(node);
      if (!pageOverflows(current)) continue;

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

      // A component that cannot fit on an empty page falls back to the proven
      // continuous renderer instead of clipping or introducing inner scrolling.
      if (pageOverflows(current)) {
        return fail(`oversize-block:${node.className || node.tagName.toLowerCase()}`);
      }
    }

    if (pages.some(pageOverflows)) return fail('post-pagination-overflow');
    measure.remove();
    return pages;
  };

  const makeTurnCorner = (page, getRotation, setRotation) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'notebook-turn-corner';
    button.setAttribute(
      'aria-label',
      page.dataset.side === 'back' ? 'Volver al frente de la hoja' : 'Dar vuelta la hoja'
    );
    page.appendChild(button);

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
      const current = getRotation();
      const back = Math.abs(Math.round(current / 180)) % 2 === 1;
      setRotation(current + (back ? -180 : 180));
    });
  };

  const buildReader = (source, pages) => {
    const shell = document.createElement('section');
    shell.className = 'notebook-reader';
    shell.setAttribute('aria-label', 'Cuaderno paginado');

    const stack = document.createElement('div');
    stack.className = 'notebook-stack';
    shell.appendChild(stack);

    const status = document.createElement('div');
    status.className = 'notebook-reader-status';
    status.setAttribute('aria-live', 'polite');
    shell.appendChild(status);

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
      const rootPx = parseFloat(rootStyle.fontSize) || 16;
      const peekToken = rootStyle.getPropertyValue('--notebook-leaf-peek').trim();
      const peek = peekToken.endsWith('rem')
        ? parseFloat(peekToken) * rootPx
        : (parseFloat(peekToken) || 45.6);

      leaves.forEach((leaf, index) => {
        const d = index - active;
        leaf.classList.toggle('is-active', d === 0);
        leaf.classList.toggle('is-neighbor', Math.abs(d) === 1);
        leaf.classList.toggle('is-hidden', Math.abs(d) > 1);
        leaf.style.zIndex = String(20 - Math.abs(d));
        leaf.tabIndex = Math.abs(d) === 1 ? 0 : -1;
        leaf.setAttribute('aria-hidden', Math.abs(d) > 1 ? 'true' : 'false');

        if (d === 0) {
          leaf.style.transform = `translateX(0) scale(1) rotateY(${rotations[index].toFixed(2)}deg)`;
        } else {
          const hoverBoost = leaf.matches(':hover') ? 12 : 0;
          leaf.style.transform = `translateX(${d * (peek + hoverBoost)}px) scale(var(--notebook-leaf-scale)) rotateY(0deg)`;
        }
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
      active = next;
      rotations[active] = 0;
      update();
    };

    pagePairs.forEach(([front, back], index) => {
      const leaf = document.createElement('div');
      leaf.className = 'notebook-leaf';
      leaf.dataset.leaf = String(index + 1);

      const frontFace = document.createElement('div');
      frontFace.className = 'notebook-face notebook-front-face';
      front.classList.add('notebook-front');
      front.dataset.page = String(index * 2 + 1);
      frontFace.appendChild(front);

      const backFace = document.createElement('div');
      backFace.className = 'notebook-face notebook-back-face';
      back.classList.add('notebook-back');
      back.dataset.page = String(index * 2 + 2);
      backFace.appendChild(back);

      const numberFront = document.createElement('div');
      numberFront.className = 'notebook-page-number';
      numberFront.textContent = `— ${index * 2 + 1} —`;
      front.appendChild(numberFront);

      const numberBack = document.createElement('div');
      numberBack.className = 'notebook-page-number';
      numberBack.textContent = `— ${index * 2 + 2} —`;
      back.appendChild(numberBack);

      const setRotation = (value, dragging = false) => {
        rotations[index] = value;
        leaf.style.transition = dragging ? 'none' : '';
        update();
        if (!dragging) requestAnimationFrame(() => { leaf.style.transition = ''; });
      };
      const getRotation = () => rotations[index];
      makeTurnCorner(front, getRotation, setRotation);
      makeTurnCorner(back, getRotation, setRotation);

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

    document.addEventListener('keydown', (event) => {
      if (!shell.isConnected || event.altKey || event.ctrlKey || event.metaKey) return;
      const activeElement = document.activeElement;
      const tag = activeElement?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || activeElement?.isContentEditable) return;
      if (event.key === 'ArrowRight') { event.preventDefault(); go(active + 1); }
      if (event.key === 'ArrowLeft') { event.preventDefault(); go(active - 1); }
    });

    update();
    return shell;
  };

  const mount = async () => {
    if (mounted || !desktop.matches || print.matches) return;
    const grid = document.querySelector('.study-grid');
    const source = grid?.querySelector(':scope > article');
    if (!source || !PAGED_KINDS.has(source.dataset.kind || '')) return;

    originalTemplate = source.cloneNode(true);
    await waitForAssets(source);
    const pages = paginate(source, grid);
    if (!pages || pages.length < 2) return;

    reader = buildReader(source, pages);
    source.replaceWith(reader);
    mounted = true;
    document.documentElement.dataset.notebookReader = 'ready';
    document.documentElement.dataset.notebookPages = String(pages.length);
  };

  const restoreForPrint = () => {
    if (!mounted || !reader?.isConnected || !originalTemplate) return;
    const source = originalTemplate.cloneNode(true);
    reader.replaceWith(source);
    mounted = false;
    reader = null;
    document.documentElement.dataset.notebookReader = 'print-continuous';
  };

  window.addEventListener('beforeprint', restoreForPrint);
  window.addEventListener('afterprint', () => { mount(); });
  desktop.addEventListener?.('change', () => location.reload());

  mount();
})();
