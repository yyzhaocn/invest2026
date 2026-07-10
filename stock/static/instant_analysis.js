/**
 * InstantAnalysis — fullscreen modal popup for live stock analysis.
 *
 * Usage:
 *   InstantAnalysis.open('002185');
 *   InstantAnalysis.close();
 */
(function (global) {
    'use strict';

    const MODAL_ID = 'instantAnalysisModal';
    const STYLE_ID = 'instantAnalysisStyles';

    function injectStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = [
            `#${MODAL_ID}{position:fixed;inset:0;z-index:10060;background:rgba(15,23,42,.55);display:none;align-items:stretch;justify-content:center;padding:0}`,
            `#${MODAL_ID}.visible{display:flex}`,
            `#${MODAL_ID} .instant-modal-frame{width:100%;height:100%;border:none;background:#fff;border-radius:0}`,
            `@media(min-width:900px){#${MODAL_ID}{padding:16px}#${MODAL_ID} .instant-modal-frame{border-radius:10px;box-shadow:0 20px 60px rgba(0,0,0,.25)}}`,
        ].join('');
        document.head.appendChild(style);
    }

    function ensureModal() {
        injectStyles();
        let modal = document.getElementById(MODAL_ID);
        if (modal) return modal;

        modal = document.createElement('div');
        modal.id = MODAL_ID;
        modal.innerHTML = '<iframe class="instant-modal-frame" allow="fullscreen"></iframe>';
        document.body.appendChild(modal);

        modal.addEventListener('click', function (e) {
            if (e.target === modal) InstantAnalysis.close();
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && modal.classList.contains('visible')) {
                InstantAnalysis.close();
            }
        });

        window.addEventListener('message', function (e) {
            if (e.data && e.data.type === 'instantAnalysisClose') {
                InstantAnalysis.close();
            }
        });

        return modal;
    }

    const InstantAnalysis = {
        open: function (stockCode) {
            const code = String(stockCode).replace(/\D/g, '').padStart(6, '0').slice(-6);
            if (!code) return;

            const modal = ensureModal();
            const iframe = modal.querySelector('iframe');
            iframe.src = '/analysis/' + code;
            modal.classList.add('visible');
            document.body.style.overflow = 'hidden';
        },

        close: function () {
            const modal = document.getElementById(MODAL_ID);
            if (!modal) return;
            modal.classList.remove('visible');
            const iframe = modal.querySelector('iframe');
            if (iframe) iframe.src = 'about:blank';
            document.body.style.overflow = '';
        },
    };

    global.InstantAnalysis = InstantAnalysis;
})(typeof window !== 'undefined' ? window : this);
