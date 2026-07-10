/** Global shortcuts: H → home, S → 动态选股, / → stock input (when present) */
(function () {
    if (window.parent !== window) return;

    const STOCK_INPUT_SELECTORS = [
        '#stockSwitchInput',
        '#stockCodeInput',
        '#singleStockInput',
    ];

    function isTypingTarget(el) {
        if (!el) return false;
        const tag = el.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
        return !!el.isContentEditable;
    }

    function isVisibleInput(el) {
        if (!el || el.disabled || el.hidden) return false;
        const style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden';
    }

    function findStockInput() {
        for (const selector of STOCK_INPUT_SELECTORS) {
            const el = document.querySelector(selector);
            if (isVisibleInput(el)) return el;
        }
        return null;
    }

    function normalizedPath() {
        const path = window.location.pathname.replace(/\/+$/, '');
        return path || '/';
    }

    function isHomePage() {
        return normalizedPath() === '/';
    }

    function isFavoritesPage() {
        return normalizedPath() === '/favorites';
    }

    function focusStockInput() {
        const input = findStockInput();
        if (!input) return false;
        input.focus({ preventScroll: false });
        if (typeof input.select === 'function') {
            input.select();
        }
        input.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
        return true;
    }

    document.addEventListener('keydown', function (e) {
        if (e.ctrlKey || e.metaKey || e.altKey) return;

        if (e.key === '/') {
            const stockInput = findStockInput();
            if (!stockInput) return;
            if (document.activeElement === stockInput) return;
            if (isTypingTarget(document.activeElement)) return;
            e.preventDefault();
            focusStockInput();
            return;
        }

        if (isTypingTarget(document.activeElement)) return;

        if (e.key === 'h' || e.key === 'H') {
            if (isHomePage()) return;
            e.preventDefault();
            window.location.href = '/';
            return;
        }
        if (e.key === 's' || e.key === 'S') {
            if (isFavoritesPage()) return;
            e.preventDefault();
            window.location.href = '/favorites';
        }
    });
})();
