/* multiselect.js — Web Component for daisyUI multi-select
 *
 * Usage:
 *   <multi-select placeholder="Pick countries…" max-tags="20">
 *     <ms-option value="ar">Argentina</ms-option>
 *     <ms-option value="br">Brazil</ms-option>
 *     <ms-option value="es" selected>Spain</ms-option>
 *   </multi-select>
 *
 * Attributes on <multi-select>:
 *   placeholder  — trigger placeholder text (default: "Select options…")
 *   max-tags     — max individual tags shown before collapsing (default: 20)
 *   name         — name used when reading .value or submitting a form
 *
 * Properties:
 *   el.value     — returns array of selected values
 *   el.selected  — returns array of { value, label } objects
 *
 * Events:
 *   "change"     — fired on every selection change, detail: { value, selected }
 */

class MultiSelect extends HTMLElement {
  connectedCallback() {
    this._maxTags   = parseInt(this.getAttribute('max-tags') ?? '20', 10);
    this._placeholder = this.getAttribute('placeholder') ?? 'Select options…';

    // Collect <ms-option> children before replacing innerHTML
    this._options = [...this.querySelectorAll('ms-option')].map(o => ({
      value:    o.getAttribute('value') ?? o.textContent.trim(),
      label:    o.textContent.trim(),
      selected: o.hasAttribute('selected'),
    }));

    this._selected = new Set(
      this._options.filter(o => o.selected).map(o => o.value)
    );

    this._filtered = [...this._options];
    this._open = false;

    this._render();
    this._attachEvents();
  }

  /* ── public API ─────────────────────────────────────────────── */

  get value() {
    return [...this._selected];
  }

  get selected() {
    return this._options
      .filter(o => this._selected.has(o.value))
      .map(({ value, label }) => ({ value, label }));
  }

  /* ── internal rendering ─────────────────────────────────────── */

  _render() {
    this.innerHTML = `
      <div class="ms-wrapper">
        <div class="ms-trigger">
          <span class="ms-placeholder">${this._placeholder}</span>
          <div class="ms-tags"></div>
          <span class="ms-chevron">▼</span>
        </div>
        <div class="ms-dropdown">
          <div class="ms-search-row">
            <input class="ms-search" type="text" placeholder="Search…" />
            <button class="ms-sel-all" type="button">Select all</button>
          </div>
          <div class="ms-list"></div>
          <div class="ms-no-results">No options found</div>
        </div>
      </div>
    `;

    this._els = {
      wrapper:   this.querySelector('.ms-wrapper'),
      trigger:   this.querySelector('.ms-trigger'),
      chevron:   this.querySelector('.ms-chevron'),
      placeholder: this.querySelector('.ms-placeholder'),
      tags:      this.querySelector('.ms-tags'),
      dropdown:  this.querySelector('.ms-dropdown'),
      search:    this.querySelector('.ms-search'),
      selAll:    this.querySelector('.ms-sel-all'),
      list:      this.querySelector('.ms-list'),
      noResults: this.querySelector('.ms-no-results'),
    };

    this._renderOptions();
    this._renderTags();
  }

  _renderOptions() {
    const { list, noResults, selAll } = this._els;
    list.innerHTML = '';

    if (this._filtered.length === 0) {
      noResults.classList.add('visible');
      return;
    }
    noResults.classList.remove('visible');

    this._filtered.forEach(opt => {
      const div = document.createElement('div');
      div.className = 'ms-option' + (this._selected.has(opt.value) ? ' selected' : '');
      div.dataset.value = opt.value;
      div.innerHTML = `<span class="ms-tick">✓</span><span class="ms-opt-label">${opt.label}</span>`;
      div.addEventListener('click', e => {
        e.stopPropagation();
        this._toggle(opt.value);
      });
      list.appendChild(div);
    });

    // Update select-all label
    const allSel = this._filtered.length > 0 && this._filtered.every(o => this._selected.has(o.value));
    selAll.textContent = allSel ? 'Deselect all' : 'Select all';
  }

  _renderTags() {
    const { tags, placeholder } = this._els;
    tags.innerHTML = '';

    if (this._selected.size === 0) {
      placeholder.style.display = 'inline';
      return;
    }
    placeholder.style.display = 'none';

    const items = this._options.filter(o => this._selected.has(o.value));

    if (items.length <= this._maxTags) {
      items.forEach(opt => {
        const tag = document.createElement('span');
        tag.className = 'ms-tag';
        tag.title = opt.label;
        tag.innerHTML = `<span class="ms-tag-label">${opt.label}</span><span class="ms-tag-x" data-value="${opt.value}">✕</span>`;
        tag.querySelector('.ms-tag-x').addEventListener('click', e => {
          e.stopPropagation();
          this._selected.delete(opt.value);
          this._renderOptions();
          this._renderTags();
          this._emit();
        });
        tags.appendChild(tag);
      });
    } else {
      const badge = document.createElement('span');
      badge.className = 'ms-tag-count';
      badge.textContent = `${items.length} selected`;
      tags.appendChild(badge);
    }
  }

  /* ── event wiring ───────────────────────────────────────────── */

  _attachEvents() {
    const { trigger, dropdown, search, selAll } = this._els;

    trigger.addEventListener('click', () => this._toggleDropdown());

    search.addEventListener('input', () => {
      const q = search.value.toLowerCase();
      this._filtered = this._options.filter(o => o.label.toLowerCase().includes(q));
      this._renderOptions();
    });
    search.addEventListener('click', e => e.stopPropagation());

    selAll.addEventListener('click', e => {
      e.stopPropagation();
      const allSel = this._filtered.length > 0 && this._filtered.every(o => this._selected.has(o.value));
      this._filtered.forEach(o => allSel ? this._selected.delete(o.value) : this._selected.add(o.value));
      this._renderOptions();
      this._renderTags();
      this._emit();
    });

    // Close on outside click
    document.addEventListener('click', e => {
      if (!this._els.wrapper.contains(e.target)) this._closeDropdown();
    });
  }

  _toggle(value) {
    if (this._selected.has(value)) this._selected.delete(value);
    else this._selected.add(value);
    this._renderOptions();
    this._renderTags();
    this._emit();
  }

  _toggleDropdown() {
    this._open ? this._closeDropdown() : this._openDropdown();
  }

  _openDropdown() {
    this._open = true;
    this._els.trigger.classList.add('open');
    this._els.dropdown.classList.add('open');
    setTimeout(() => this._els.search.focus(), 50);
  }

  _closeDropdown() {
    this._open = false;
    this._els.trigger.classList.remove('open');
    this._els.dropdown.classList.remove('open');
  }

  _emit() {
    this.dispatchEvent(new CustomEvent('change', {
      bubbles: true,
      detail: { value: this.value, selected: this.selected },
    }));
  }

  _uid() {
    return Math.random().toString(36).slice(2, 7);
  }
}

customElements.define('multi-select', MultiSelect);