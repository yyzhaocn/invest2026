(function (global) {
    'use strict';

    const STYLE_ID = 'chart-hover-styles';
    const POPUP_ID = 'chartHoverPopup';
    let hideTimer = null;
    let activeTab = 'day';
    let activePayload = null;

    function normalizeCode(raw) {
        const text = String(raw || '').trim().toUpperCase();
        const match = text.match(/(\d{6})/);
        return match ? match[1] : '';
    }

    function chartNid(code) {
        const c = String(code).padStart(6, '0');
        return ((c.startsWith('6') || c.startsWith('9')) ? '1.' : '0.') + c;
    }

    function withTs(url) {
        if (!url) return '';
        return url + (url.includes('?') ? '&' : '?') + 't=' + Date.now();
    }

    function intradayUrl(code, base) {
        if (base) return withTs(base);
        return 'https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token=44c9d251add88e27b65ed86506f6e5da&nid='
            + chartNid(code) + '&timespan=' + Date.now();
    }

    function klineUrl(code, period, base) {
        if (period === 'day' && base) return withTs(base);
        const typeMap = { day: '', week: 'W', month: 'M' };
        const kType = typeMap[period] || '';
        return 'https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid=' + chartNid(code)
            + '&type=' + kType + '&unitWidth=-6&ef=&formula=MACD&AT=1&imageType=KXL&timespan=' + Date.now();
    }

    function chartUrlForTab(code, tab, opts) {
        const options = opts || {};
        if (tab === 'intraday') return intradayUrl(code, options.intraday);
        return klineUrl(code, tab, options.kline);
    }

    function parseNumber(raw) {
        if (raw == null || raw === '') return null;
        const text = String(raw).replace(/<[^>]+>/g, '').replace(/,/g, '').replace('+', '').trim();
        const num = parseFloat(text);
        return Number.isNaN(num) ? null : num;
    }

    function formatPrice(raw) {
        const num = parseNumber(raw);
        return num == null ? '--' : num.toFixed(2);
    }

    function formatChange(raw) {
        const num = parseNumber(raw);
        if (num == null) return { text: '--', cls: 'neutral' };
        const sign = num > 0 ? '+' : '';
        return { text: sign + num.toFixed(2) + '%', cls: num > 0 ? 'up' : num < 0 ? 'down' : 'neutral' };
    }

    function ensureStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = [
            '.stock-chart-hover,.stock-hover-name,.kline-hover-chart{cursor:pointer;border-bottom:1px dashed #3498db}',
            '.chart-hover-popup{position:fixed;z-index:10050;pointer-events:auto;background:#fff;border:1px solid #d0d7de;border-radius:10px;box-shadow:0 12px 32px rgba(15,23,42,.18);padding:0;display:none;width:520px;overflow:hidden}',
            '.chart-hover-popup.visible{display:block}',
            '.chart-hover-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:12px 14px 8px;border-bottom:1px solid #eef1f4}',
            '.chart-hover-title strong{font-size:16px;color:#1f2937;margin-right:8px}',
            '.chart-hover-title span{font-size:13px;color:#94a3b8}',
            '.chart-hover-quote{text-align:right;white-space:nowrap}',
            '.chart-hover-price{font-size:22px;font-weight:700;line-height:1.1}',
            '.chart-hover-price.up,.chart-hover-change.up{color:#e74c3c}',
            '.chart-hover-price.down,.chart-hover-change.down{color:#27ae60}',
            '.chart-hover-price.neutral,.chart-hover-change.neutral{color:#64748b}',
            '.chart-hover-change{font-size:13px;margin-top:2px}',
            '.chart-hover-tabs{display:flex;gap:6px;padding:8px 14px 0}',
            '.chart-hover-tab{border:1px solid #e2e8f0;background:#f8fafc;color:#475569;border-radius:6px 6px 0 0;padding:5px 14px;font-size:12px;cursor:pointer}',
            '.chart-hover-tab.active{background:#fff;border-bottom-color:#fff;color:#ea580c;font-weight:600;box-shadow:0 -1px 0 #fff}',
            '.chart-hover-main{padding:0 10px 10px;background:#fff}',
            '.chart-hover-main img{display:block;width:100%;height:320px;object-fit:contain;background:#fafafa;border:1px solid #eef1f4;border-radius:6px}',
        ].join('');
        document.head.appendChild(style);
    }

    function ensurePopup() {
        ensureStyles();
        if (document.getElementById(POPUP_ID)) return;
        const popup = document.createElement('div');
        popup.id = POPUP_ID;
        popup.className = 'chart-hover-popup';
        popup.innerHTML = [
            '<div class="chart-hover-head">',
            '  <div class="chart-hover-title"><strong id="chartHoverName"></strong><span id="chartHoverCode"></span></div>',
            '  <div class="chart-hover-quote">',
            '    <div class="chart-hover-price" id="chartHoverPrice">--</div>',
            '    <div class="chart-hover-change" id="chartHoverChange">--</div>',
            '  </div>',
            '</div>',
            '<div class="chart-hover-tabs">',
            '  <button type="button" class="chart-hover-tab" data-tab="intraday">分时</button>',
            '  <button type="button" class="chart-hover-tab active" data-tab="day">日K</button>',
            '  <button type="button" class="chart-hover-tab" data-tab="week">周K</button>',
            '  <button type="button" class="chart-hover-tab" data-tab="month">月K</button>',
            '</div>',
            '<div class="chart-hover-main"><img id="chartHoverMainImg" alt="行情图" referrerpolicy="no-referrer"></div>',
        ].join('');
        document.body.appendChild(popup);

        popup.querySelectorAll('.chart-hover-tab').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                setActiveTab(btn.dataset.tab || 'day');
            });
        });
        popup.addEventListener('mouseenter', cancelHide);
        popup.addEventListener('mouseleave', scheduleHide);
    }

    function setActiveTab(tab) {
        activeTab = tab || 'day';
        const popup = document.getElementById(POPUP_ID);
        if (!popup) return;
        popup.querySelectorAll('.chart-hover-tab').forEach(function (btn) {
            btn.classList.toggle('active', btn.dataset.tab === activeTab);
        });
        if (activePayload) {
            document.getElementById('chartHoverMainImg').src = chartUrlForTab(
                activePayload.code, activeTab, activePayload.opts
            );
        }
    }

    function movePopup(e) {
        const popup = document.getElementById(POPUP_ID);
        if (!popup || !popup.classList.contains('visible')) return;
        const pad = 18;
        let x = e.clientX + pad;
        let y = e.clientY + pad;
        popup.style.visibility = 'hidden';
        popup.classList.add('visible');
        const rect = popup.getBoundingClientRect();
        popup.style.visibility = '';
        if (x + rect.width > window.innerWidth - 8) x = e.clientX - rect.width - pad;
        if (y + rect.height > window.innerHeight - 8) y = e.clientY - rect.height - pad;
        popup.style.left = Math.max(8, x) + 'px';
        popup.style.top = Math.max(8, y) + 'px';
    }

    function cancelHide() {
        if (hideTimer) {
            clearTimeout(hideTimer);
            hideTimer = null;
        }
    }

    function scheduleHide() {
        cancelHide();
        hideTimer = setTimeout(hidePopup, 180);
    }

    function hidePopup() {
        cancelHide();
        const popup = document.getElementById(POPUP_ID);
        if (popup) popup.classList.remove('visible');
        activePayload = null;
    }

    function payloadFromEl(el) {
        const code = normalizeCode(el.dataset.code || el.textContent);
        if (!code) return null;
        return {
            code: code,
            name: el.dataset.name || code,
            price: el.dataset.price || '',
            change: el.dataset.change || '',
            opts: {
                intraday: el.dataset.intraday || '',
                kline: el.dataset.kline || '',
            },
        };
    }

    function showPopup(e, payload, tab) {
        if (!payload || !payload.code) return;
        ensurePopup();
        activePayload = payload;
        activeTab = tab || 'day';

        document.getElementById('chartHoverName').textContent = payload.name || payload.code;
        document.getElementById('chartHoverCode').textContent = payload.code;

        const chg = formatChange(payload.change);
        const priceEl = document.getElementById('chartHoverPrice');
        const changeEl = document.getElementById('chartHoverChange');
        priceEl.textContent = formatPrice(payload.price);
        priceEl.className = 'chart-hover-price ' + chg.cls;
        changeEl.textContent = chg.text;
        changeEl.className = 'chart-hover-change ' + chg.cls;

        setActiveTab(activeTab);
        document.getElementById(POPUP_ID).classList.add('visible');
        movePopup(e);
    }

    function bindHover(el, payload, tab) {
        if (!el || el.dataset.chartHoverBound) return;
        const data = payload || payloadFromEl(el);
        if (!data || !data.code) return;
        el.dataset.chartHoverBound = '1';
        el.classList.add('stock-chart-hover');
        el.addEventListener('mouseenter', function (e) {
            cancelHide();
            showPopup(e, data, tab);
        });
        el.addEventListener('mousemove', movePopup);
        el.addEventListener('mouseleave', scheduleHide);
    }

    function bindFavorites(root) {
        ensurePopup();
        const scope = root || document;
        scope.querySelectorAll('.stock-chart-hover:not([data-chart-hover-bound])').forEach(function (el) {
            bindHover(el);
        });
        scope.querySelectorAll('.kline-hover-chart:not([data-chart-hover-bound])').forEach(function (el) {
            bindHover(el, null, 'day');
        });
    }

    function enhanceTable(table) {
        if (!table || table.dataset.chartHoverTable) return;
        table.dataset.chartHoverTable = '1';
        bindFavorites(table);
    }

    function init(root) {
        ensurePopup();
        const scope = root || document;
        scope.querySelectorAll('#stockTable, #dataTable, .table-container table').forEach(enhanceTable);
        bindFavorites(scope);
    }

    global.ChartHover = {
        init: init,
        bindFavorites: bindFavorites,
        bindHover: bindHover,
        enhanceTable: enhanceTable,
        show: showPopup,
        hide: hidePopup,
    };
}(window));
