(function (global) {
    const STORAGE_KEY = 'stock_recent_visits';
    const MAX_ITEMS = 10;

    function load() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return [];
            const list = JSON.parse(raw);
            return Array.isArray(list) ? list : [];
        } catch {
            return [];
        }
    }

    function save(list) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(list.slice(0, MAX_ITEMS)));
    }

    function record(code, name) {
        const normalized = String(code || '').trim();
        if (!/^\d{6}$/.test(normalized)) return;

        const displayName = (name || '').trim() || normalized;
        const list = load().filter(item => item.code !== normalized);
        list.unshift({
            code: normalized,
            name: displayName,
            visitedAt: Date.now()
        });
        save(list);
    }

    function render(containerId, options) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const opts = options || {};
        const list = load();
        container.innerHTML = '';

        if (list.length === 0) {
            const empty = document.createElement('div');
            empty.className = opts.emptyClass || 'recent-empty';
            empty.textContent = opts.emptyText || '暂无访问记录';
            container.appendChild(empty);
            return;
        }

        list.forEach(item => {
            const chip = document.createElement('div');
            chip.className = opts.chipClass || 'stock-chip';
            chip.setAttribute('data-code', item.code);
            chip.textContent = `${item.code} ${item.name}`;
            chip.addEventListener('click', function () {
                window.location.href = `/analysis/${item.code}`;
            });
            container.appendChild(chip);
        });
    }

    global.RecentStocks = { load, record, render };
})(window);
