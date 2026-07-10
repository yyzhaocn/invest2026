/**
 * Compact stock switcher for analysis headers.
 * StockHeaderInput.init({ routeBase: '/analysis', currentCode: '002185' });
 */
(function (global) {
    'use strict';

    const STYLE_ID = 'stockHeaderInputStyles';

    function injectStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = [
            '.stock-switcher{position:relative;display:inline-flex;align-items:center;vertical-align:middle}',
            '.stock-switcher-form{display:flex;align-items:center;gap:4px}',
            '.stock-switcher-input{width:108px;padding:4px 8px;border:1px solid rgba(0,0,0,.12);border-radius:6px;font-size:13px;background:rgba(255,255,255,.85);color:#2c3e50}',
            '.stock-switcher-input:focus{outline:none;border-color:#3498db;box-shadow:0 0 0 2px rgba(52,152,219,.15)}',
            '.stock-switcher-btn{padding:4px 8px;border:1px solid rgba(0,0,0,.12);border-radius:6px;background:rgba(255,255,255,.75);cursor:pointer;font-size:13px;line-height:1;color:#555}',
            '.stock-switcher-btn:hover{background:#f0f0f0;color:#333}',
            '.stock-switcher-suggestions{display:none;position:absolute;top:calc(100% + 4px);left:0;min-width:220px;max-height:240px;overflow-y:auto;background:#fff;border:1px solid #ddd;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.12);z-index:2000}',
            '.stock-switcher-suggestions.show{display:block}',
            '.stock-switcher-item{padding:8px 12px;cursor:pointer;display:flex;justify-content:space-between;gap:8px;font-size:13px}',
            '.stock-switcher-item:hover,.stock-switcher-item.active{background:#f0f7ff}',
            '.stock-switcher-item .code{font-weight:600;color:#3498db;flex-shrink:0}',
            '.stock-switcher-item .name{color:#555;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
        ].join('');
        document.head.appendChild(style);
    }

    function normalizeCode(code) {
        const digits = String(code || '').replace(/\D/g, '');
        return digits.padStart(6, '0').slice(-6);
    }

    const StockHeaderInput = {
        init: function (options) {
            injectStyles();
            const routeBase = (options && options.routeBase) || '/analysis';
            const currentCode = normalizeCode(options && options.currentCode);
            const form = document.getElementById('stockSwitchForm');
            const input = document.getElementById('stockSwitchInput');
            const list = document.getElementById('stockSwitchSuggestions');
            if (!form || !input || !list) return;

            let timer = null;
            let activeIndex = -1;
            let suggestions = [];

            function navigate(code) {
                const c = normalizeCode(code);
                if (!c) return;
                if (c === currentCode) {
                    input.value = '';
                    hideSuggestions();
                    return;
                }
                const target = routeBase.replace(/\/$/, '') + '/' + c;
                window.location.href = target;
            }

            async function search(query) {
                const res = await fetch('/api/stock/search?q=' + encodeURIComponent(query) + '&limit=8');
                const data = await res.json();
                if (!data.success) throw new Error(data.error || '搜索失败');
                return data.data || [];
            }

            async function resolve(query) {
                const q = query.trim();
                if (!q) return null;
                if (/^\d{6}$/.test(q)) return q;
                const items = await search(q);
                return items.length ? items[0].code : null;
            }

            function hideSuggestions() {
                list.classList.remove('show');
                list.innerHTML = '';
                activeIndex = -1;
                suggestions = [];
            }

            function setActive(index) {
                activeIndex = index;
                list.querySelectorAll('.stock-switcher-item').forEach(function (el, i) {
                    el.classList.toggle('active', i === index);
                });
            }

            function render(items) {
                suggestions = items;
                activeIndex = -1;
                list.innerHTML = '';
                if (!items.length) {
                    hideSuggestions();
                    return;
                }
                items.forEach(function (item, index) {
                    const row = document.createElement('div');
                    row.className = 'stock-switcher-item';
                    row.innerHTML = '<span class="code">' + item.code + '</span><span class="name">' + item.name + '</span>';
                    row.addEventListener('mousedown', function (e) {
                        e.preventDefault();
                        navigate(item.code);
                    });
                    row.addEventListener('mouseenter', function () { setActive(index); });
                    list.appendChild(row);
                });
                list.classList.add('show');
            }

            function scheduleSearch() {
                clearTimeout(timer);
                const q = input.value.trim();
                if (!q || /^\d{6}$/.test(q)) {
                    hideSuggestions();
                    return;
                }
                timer = setTimeout(function () {
                    search(q).then(render).catch(function () { hideSuggestions(); });
                }, 250);
            }

            form.addEventListener('submit', async function (e) {
                e.preventDefault();
                const q = input.value.trim();
                if (!q) return;
                if (activeIndex >= 0 && suggestions[activeIndex]) {
                    navigate(suggestions[activeIndex].code);
                    return;
                }
                try {
                    const code = await resolve(q);
                    if (code) navigate(code);
                    else input.select();
                } catch (_) {
                    input.select();
                }
            });

            input.addEventListener('input', scheduleSearch);
            input.addEventListener('keydown', function (e) {
                if (!list.classList.contains('show') || !suggestions.length) return;
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    setActive(Math.min(activeIndex + 1, suggestions.length - 1));
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    setActive(Math.max(activeIndex - 1, 0));
                } else if (e.key === 'Escape') {
                    hideSuggestions();
                }
            });
            input.addEventListener('blur', function () {
                setTimeout(hideSuggestions, 150);
            });
        },
    };

    global.StockHeaderInput = StockHeaderInput;
})(typeof window !== 'undefined' ? window : this);
