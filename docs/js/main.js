/* ================================================================
   EMBEX DOCS — Interactive Documentation Site
   Sidebar navigation, TOC generation, section switching, search,
   code copy, scroll spy
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
  initSidebarNav();
  initTOC();
  initScrollSpy();
  initCodeCopy();
  initSearch();
});

/* ── Sidebar navigation → show/hide doc sections ──────────────── */
function initSidebarNav() {
  const items = document.querySelectorAll('.sidebar-item[data-section]');
  const sections = document.querySelectorAll('.doc-section');

  items.forEach(item => {
    item.addEventListener('click', () => {
      const target = item.dataset.section;

      // Update sidebar active state
      items.forEach(i => i.classList.remove('active'));
      item.classList.add('active');

      // Show target section
      sections.forEach(s => s.classList.remove('active'));
      const section = document.getElementById(target);
      if (section) {
        section.classList.add('active');
        // Scroll content area to top
        document.querySelector('.content-area').scrollTo({ top: 0, behavior: 'instant' });
        // Rebuild TOC for new section
        buildTOC(section);
      }
    });
  });
}

/* ── Table of Contents (right sidebar) ────────────────────────── */
function initTOC() {
  const activeSection = document.querySelector('.doc-section.active');
  if (activeSection) buildTOC(activeSection);
}

function buildTOC(section) {
  const tocList = document.getElementById('tocList');
  if (!tocList) return;

  tocList.innerHTML = '';
  const headings = section.querySelectorAll('h2, h3');

  headings.forEach((h, i) => {
    // Ensure heading has an id
    if (!h.id) {
      h.id = 'heading-' + i + '-' + h.textContent.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/-+$/, '');
    }

    const item = document.createElement('div');
    item.className = 'toc-item' + (h.tagName === 'H3' ? ' toc-h3' : '');
    item.textContent = h.textContent;
    item.dataset.target = h.id;

    item.addEventListener('click', () => {
      h.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    tocList.appendChild(item);
  });
}

/* ── Scroll spy for right sidebar ─────────────────────────────── */
function initScrollSpy() {
  const contentArea = document.querySelector('.content-area');
  if (!contentArea) return;

  contentArea.addEventListener('scroll', () => {
    const tocItems = document.querySelectorAll('.toc-item');
    if (!tocItems.length) return;

    const activeSection = document.querySelector('.doc-section.active');
    if (!activeSection) return;

    const headings = activeSection.querySelectorAll('h2, h3');
    let current = null;

    // Detect if scrolled to the absolute bottom of the container
    const isAtBottom = contentArea.scrollHeight - contentArea.scrollTop - contentArea.clientHeight < 25;

    if (isAtBottom && headings.length > 0) {
      current = headings[headings.length - 1].id;
    } else {
      let bestTop = -Infinity;
      headings.forEach(h => {
        const rect = h.getBoundingClientRect();
        // The header area is at the top of the window (topnav is 56px).
        // A heading is active if it has scrolled past 90px from the top.
        if (rect.top <= 90) {
          if (rect.top > bestTop) {
            bestTop = rect.top;
            current = h.id;
          }
        }
      });
    }

    // Default to the first heading if none have crossed the threshold yet
    if (!current && headings.length > 0) {
      current = headings[0].id;
    }

    tocItems.forEach(item => {
      item.classList.toggle('active', item.dataset.target === current);
    });
  }, { passive: true });
}

/* ── Code copy buttons ────────────────────────────────────────── */
function initCodeCopy() {
  document.querySelectorAll('.code-copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const block = btn.closest('.code-block');
      const code = block?.querySelector('pre')?.textContent;
      if (!code) return;

      navigator.clipboard.writeText(code).then(() => {
        const orig = btn.innerHTML;
        btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied`;
        btn.style.color = 'var(--accent)';
        btn.style.borderColor = 'var(--accent-border)';
        setTimeout(() => {
          btn.innerHTML = orig;
          btn.style.color = '';
          btn.style.borderColor = '';
        }, 1800);
      });
    });
  });
}

/* ── Search ───────────────────────────────────────────────────── */
function initSearch() {
  const input = document.getElementById('searchInput');
  const results = document.getElementById('searchResults');
  if (!input || !results) return;

  let searchIndex = [];

  // Build index from DOM content
  function buildIndex() {
    searchIndex = [];
    const sections = document.querySelectorAll('.doc-section');
    sections.forEach(sec => {
      const sectionId = sec.id;
      const sectionName = document.querySelector(`.sidebar-item[data-section="${sectionId}"]`)?.textContent.trim() || 'General';
      
      // Add section title
      const h1 = sec.querySelector('h1');
      if (h1) {
        searchIndex.push({
          type: 'section',
          title: h1.textContent.trim(),
          subtitle: sectionName,
          sectionId: sectionId,
          targetId: h1.id || h1.parentNode.id,
          text: sec.textContent.toLowerCase()
        });
      }

      // Add headings
      sec.querySelectorAll('h2, h3').forEach(heading => {
        searchIndex.push({
          type: 'heading',
          title: heading.textContent.trim(),
          subtitle: `${sectionName} > ${heading.textContent.trim()}`,
          sectionId: sectionId,
          targetId: heading.id,
          text: heading.textContent.toLowerCase()
        });
      });
    });
  }

  buildIndex();

  let selectedIndex = -1;

  input.addEventListener('input', () => {
    const query = input.value.toLowerCase().trim();
    results.innerHTML = '';
    selectedIndex = -1;

    if (!query) {
      results.classList.remove('active');
      return;
    }

    const matches = searchIndex.filter(item => {
      return item.title.toLowerCase().includes(query) || item.text.includes(query);
    }).slice(0, 8); // cap at 8 results

    if (matches.length === 0) {
      results.innerHTML = `<div class="search-result-item" style="color:var(--text-muted);cursor:default;">No results found</div>`;
      results.classList.add('active');
      return;
    }

    matches.forEach((item, idx) => {
      const el = document.createElement('div');
      el.className = 'search-result-item';
      el.dataset.index = idx;
      el.dataset.section = item.sectionId;
      el.dataset.target = item.targetId;

      let snippet = '';
      if (item.type === 'section') {
        snippet = 'Go to section overview';
      } else {
        snippet = `Jump to ${item.title}`;
      }

      el.innerHTML = `
        <div class="search-result-title">${item.title}</div>
        <div class="search-result-subtitle">${item.subtitle}</div>
        <div class="search-result-snippet">${snippet}</div>
      `;

      el.addEventListener('click', () => {
        goToResult(item);
      });

      results.appendChild(el);
    });

    results.classList.add('active');
  });

  function goToResult(item) {
    // 1. Switch sidebar section
    const sidebarItem = document.querySelector(`.sidebar-item[data-section="${item.sectionId}"]`);
    if (sidebarItem) {
      sidebarItem.click();
    }

    // 2. Scroll to target heading
    setTimeout(() => {
      const targetEl = document.getElementById(item.targetId);
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        
        // Highlight effect
        targetEl.style.transition = 'text-shadow 0.3s ease';
        targetEl.style.textShadow = '0 0 10px var(--accent)';
        setTimeout(() => {
          targetEl.style.textShadow = '';
        }, 1200);
      }
    }, 100);

    // 3. Clear search
    input.value = '';
    results.classList.remove('active');
    input.blur();
  }

  // Keyboard navigation
  input.addEventListener('keydown', e => {
    const items = results.querySelectorAll('.search-result-item:not([style*="cursor:default"])');
    if (!results.classList.contains('active') || !items.length) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex = (selectedIndex + 1) % items.length;
      updateSelection(items);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex = (selectedIndex - 1 + items.length) % items.length;
      updateSelection(items);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < items.length) {
        items[selectedIndex].click();
      }
    }
  });

  function updateSelection(items) {
    items.forEach((item, idx) => {
      item.classList.toggle('selected', idx === selectedIndex);
      if (idx === selectedIndex) {
        item.scrollIntoView({ block: 'nearest' });
      }
    });
  }

  // Hide on click outside
  document.addEventListener('click', e => {
    if (!input.contains(e.target) && !results.contains(e.target)) {
      results.classList.remove('active');
    }
  });

  // Ctrl+K shortcut
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      input.focus();
    }
    if (e.key === 'Escape') {
      input.blur();
      input.value = '';
      results.classList.remove('active');
    }
  });
}
