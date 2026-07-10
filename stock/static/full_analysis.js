/**
 * FullAnalysis — fullscreen modal popup for tabbed stock analysis.
 *
 * Usage:
 *   FullAnalysis.open('002185');
 *   FullAnalysis.close();
 */
(function (global) {
    'use strict';

    const MODAL_ID = 'fullAnalysisModal';
    const STYLE_ID = 'fullAnalysisStyles';

    function injectStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = [
            `#${MODAL_ID}{position:fixed;inset:0;z-index:10060;background:rgba(15,23,42,.55);display:none;align-items:stretch;justify-content:center;padding:0}`,
            `#${MODAL_ID}.visible{display:flex}`,
            `#${MODAL_ID} .full-modal-frame{width:100%;height:100%;border:none;background:#fff;border-radius:0}`,
            `@media(min-width:900px){#${MODAL_ID}{padding:16px}#${MODAL_ID} .full-modal-frame{border-radius:10px;box-shadow:0 20px 60px rgba(0,0,0,.25)}}`,
        ].join('');
        document.head.appendChild(style);
    }

    function normalizeCode(stockCode) {
        const digits = String(stockCode || '').replace(/\D/g, '');
        return digits.padStart(6, '0').slice(-6);
    }

    function stockCodeFromIframe(iframe) {
        if (!iframe || !iframe.src || iframe.src === 'about:blank') return '';
        try {
            const path = new URL(iframe.src, window.location.origin).pathname;
            const match = path.match(/\/full-analysis\/(\d{6})/);
            return match ? match[1] : '';
        } catch (_) {
            return '';
        }
    }

    function transferToAnalysis(stockCode) {
        const code = normalizeCode(stockCode);
        if (!code) return;
        const target = '/analysis/' + code;
        if (window.location.pathname !== target) {
            window.location.href = target;
        }
    }

    function ensureModal() {
        injectStyles();
        let modal = document.getElementById(MODAL_ID);
        if (modal) return modal;

        modal = document.createElement('div');
        modal.id = MODAL_ID;
        modal.innerHTML = '<iframe class="full-modal-frame" allow="fullscreen"></iframe>';
        document.body.appendChild(modal);

        modal.addEventListener('click', function (e) {
            if (e.target === modal) FullAnalysis.close();
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && modal.classList.contains('visible')) {
                FullAnalysis.close();
            }
        });

        window.addEventListener('message', function (e) {
            if (e.data && e.data.type === 'fullAnalysisClose') {
                const modal = document.getElementById(MODAL_ID);
                const iframe = modal && modal.querySelector('iframe');
                const code = e.data.stockCode || stockCodeFromIframe(iframe);
                FullAnalysis.close(code);
            }
        });

        return modal;
    }

    const FullAnalysis = {
        open: function (stockCode) {
            const code = String(stockCode).replace(/\D/g, '').padStart(6, '0').slice(-6);
            if (!code) return;

            const modal = ensureModal();
            const iframe = modal.querySelector('iframe');
            iframe.src = '/full-analysis/' + code;
            modal.classList.add('visible');
            document.body.style.overflow = 'hidden';
        },

        close: function (stockCode) {
            const modal = document.getElementById(MODAL_ID);
            if (!modal) return;
            const iframe = modal.querySelector('iframe');
            const code = normalizeCode(stockCode || stockCodeFromIframe(iframe));
            modal.classList.remove('visible');
            if (iframe) iframe.src = 'about:blank';
            document.body.style.overflow = '';
            if (code) transferToAnalysis(code);
        },
    };

    global.FullAnalysis = FullAnalysis;
})(typeof window !== 'undefined' ? window : this);
