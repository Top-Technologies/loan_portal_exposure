/** @odoo-module **/

/**
 * Ethiopian (Ge'ez) Calendar Engine & Dual Calendar Synchronizer for Loan Module
 */

const ETHIOPIAN_MONTHS = [
    { id: 1, am: 'መስከረም', en: 'Meskerem' },
    { id: 2, am: 'ጥቅምት', en: 'Tikimt' },
    { id: 3, am: 'ኅዳር', en: 'Hidar' },
    { id: 4, am: 'ታኅሣሥ', en: 'Tahsas' },
    { id: 5, am: 'ጥር', en: 'Tir' },
    { id: 6, am: 'የካቲት', en: 'Yekatit' },
    { id: 7, am: 'መጋቢት', en: 'Megabit' },
    { id: 8, am: 'ሚያዝያ', en: 'Miyazya' },
    { id: 9, am: 'ግንቦት', en: 'Ginbot' },
    { id: 10, am: 'ሰኔ', en: 'Sene' },
    { id: 11, am: 'ሐምሌ', en: 'Hamle' },
    { id: 12, am: 'ነሐሴ', en: 'Nehase' },
    { id: 13, am: 'ጳጉሜ', en: 'Pagume' }
];

const AMHARIC_WEEKDAYS = ['ሰኞ', 'ማክሰኞ', 'ረቡዕ', 'ሐሙስ', 'ዓርብ', 'ቅዳሜ', 'እሑድ'];

function gregorianToJdn(year, month, day) {
    const a = Math.floor((14 - month) / 12);
    const y = year + 4800 - a;
    const m = month + 12 * a - 3;
    return day + Math.floor((153 * m + 2) / 5) + 365 * y + Math.floor(y / 4) - Math.floor(y / 100) + Math.floor(y / 400) - 32045;
}

function jdnToGregorian(jdn) {
    const a = jdn + 32044;
    const b = Math.floor((4 * a + 3) / 146097);
    const c = a - Math.floor((146097 * b) / 4);
    const d = Math.floor((4 * c + 3) / 1461);
    const e = c - Math.floor((1461 * d) / 4);
    const m = Math.floor((5 * e + 2) / 153);
    const day = e - Math.floor((153 * m + 2) / 5) + 1;
    const month = m + 3 - 12 * Math.floor(m / 10);
    const year = 100 * b + d - 4800 + Math.floor(m / 10);
    return { year, month, day };
}

function ethiopianToJdn(year, month, day) {
    return (1723856 + 365) + 365 * (year - 1) + Math.floor(year / 4) + 30 * (month - 1) + day - 1;
}

function jdnToEthiopian(jdn) {
    const r = (jdn - 1723856) % 1461;
    const n = (r % 365) + 365 * Math.floor(r / 1460);
    const year = 4 * Math.floor((jdn - 1723856) / 1461) + Math.floor(r / 365) - Math.floor(r / 1460);
    const month = Math.floor(n / 30) + 1;
    const day = (n % 30) + 1;
    return { year, month, day };
}

export function gregorianToEthiopianDate(gDateStr) {
    if (!gDateStr) return null;
    const parts = gDateStr.split('-');
    if (parts.length < 3) return null;
    const gy = parseInt(parts[0], 10);
    const gm = parseInt(parts[1], 10);
    const gd = parseInt(parts[2], 10);
    const jdn = gregorianToJdn(gy, gm, gd);
    return jdnToEthiopian(jdn);
}

export function ethiopianToGregorianDate(ey, em, ed) {
    const jdn = ethiopianToJdn(parseInt(ey, 10), parseInt(em, 10), parseInt(ed, 10));
    const g = jdnToGregorian(jdn);
    const mm = String(g.month).padStart(2, '0');
    const dd = String(g.day).padStart(2, '0');
    return `${g.year}-${mm}-${dd}`;
}

export function getDaysInEthiopianMonth(year, month) {
    if (month >= 1 && month <= 12) return 30;
    if (month === 13) {
        return (year % 4 === 3) ? 6 : 5;
    }
    return 30;
}

export function formatEthiopianDisplay(gDateStr) {
    const eth = gregorianToEthiopianDate(gDateStr);
    if (!eth) return '';
    const mObj = ETHIOPIAN_MONTHS[eth.month - 1];
    const mName = mObj ? `${mObj.am} (${mObj.en})` : `Month ${eth.month}`;

    const d = new Date(gDateStr + 'T00:00:00');
    const dayIdx = (d.getDay() + 6) % 7;
    const weekdayName = AMHARIC_WEEKDAYS[dayIdx] || '';

    return `${weekdayName}, ${eth.day} ${mName} ${eth.year} ዓ.ም.`;
}

// --- DOM Sync Engine for Loan Preferred Disbursement Date ---

let isSyncingLoan = false;

function populateEthiopianDayOptions(selectElem, year, month, currentVal) {
    if (!selectElem) return;
    const maxDays = getDaysInEthiopianMonth(year, month);
    selectElem.innerHTML = '';
    for (let d = 1; d <= maxDays; d++) {
        const opt = document.createElement('option');
        opt.value = d;
        opt.textContent = `${d}`;
        if (d === currentVal || (d === maxDays && currentVal > maxDays)) {
            opt.selected = true;
        }
        selectElem.appendChild(opt);
    }
}

export function syncGregorianToEthiopianLoan() {
    if (isSyncingLoan) return;
    isSyncingLoan = true;
    try {
        const gInput = document.getElementById('payment_date');
        if (!gInput || !gInput.value) return;

        const eth = gregorianToEthiopianDate(gInput.value);
        if (!eth) return;

        const yInput = document.getElementById('eth_year_loan');
        const mInput = document.getElementById('eth_month_loan');
        const dInput = document.getElementById('eth_day_loan');
        const badge = document.getElementById('eth_badge_payment_date');

        if (yInput) yInput.value = eth.year;
        if (mInput) mInput.value = eth.month;
        if (dInput) {
            populateEthiopianDayOptions(dInput, eth.year, eth.month, eth.day);
            dInput.value = eth.day;
        }

        if (badge) {
            badge.textContent = formatEthiopianDisplay(gInput.value);
        }

        renderInteractiveLoanMonthView();
    } finally {
        isSyncingLoan = false;
    }
}

export function syncEthiopianToGregorianLoan() {
    if (isSyncingLoan) return;
    isSyncingLoan = true;
    try {
        const yInput = document.getElementById('eth_year_loan');
        const mInput = document.getElementById('eth_month_loan');
        const dInput = document.getElementById('eth_day_loan');
        const gInput = document.getElementById('payment_date');
        const badge = document.getElementById('eth_badge_payment_date');

        if (!yInput || !mInput || !dInput || !gInput) return;

        const ey = parseInt(yInput.value, 10) || 2018;
        const em = parseInt(mInput.value, 10) || 1;
        let ed = parseInt(dInput.value, 10) || 1;

        const maxDays = getDaysInEthiopianMonth(ey, em);
        if (ed > maxDays) ed = maxDays;

        populateEthiopianDayOptions(dInput, ey, em, ed);

        const gDateStr = ethiopianToGregorianDate(ey, em, ed);
        gInput.value = gDateStr;
        gInput.dispatchEvent(new Event('change', { bubbles: true }));

        if (badge) {
            badge.textContent = formatEthiopianDisplay(gDateStr);
        }

        renderInteractiveLoanMonthView();
    } finally {
        isSyncingLoan = false;
    }
}

export function renderInteractiveLoanMonthView() {
    const container = document.getElementById('eth_calendar_grid_loan');
    if (!container) return;

    const yInput = document.getElementById('eth_year_loan');
    const mInput = document.getElementById('eth_month_loan');
    const dInput = document.getElementById('eth_day_loan');

    if (!yInput || !mInput || !dInput) return;

    const year = parseInt(yInput.value, 10) || 2018;
    const month = parseInt(mInput.value, 10) || 1;
    const selectedDay = parseInt(dInput.value, 10) || 1;
    const maxDays = getDaysInEthiopianMonth(year, month);

    const firstDayGStr = ethiopianToGregorianDate(year, month, 1);
    const firstDayDate = new Date(firstDayGStr + 'T00:00:00');
    const firstDayWeekday = (firstDayDate.getDay() + 6) % 7;

    let html = `
        <div class="eth-mini-calendar p-2 border rounded-3 bg-white shadow-xs">
            <div class="d-flex justify-content-between align-items-center mb-2 px-1">
                <span class="fw-bold small text-primary">
                    ${ETHIOPIAN_MONTHS[month - 1].am} (${ETHIOPIAN_MONTHS[month - 1].en}) ${year} ዓ.ም.
                </span>
                <span class="badge bg-light text-secondary border small">የቀን ምርጫ</span>
            </div>
            <div class="eth-grid-weekdays d-flex text-center text-muted small fw-bold mb-1">
                ${AMHARIC_WEEKDAYS.map(w => `<div class="flex-fill" style="width: 14.28%; font-size: 0.72rem;">${w.substring(0, 3)}</div>`).join('')}
            </div>
            <div class="eth-grid-days d-flex flex-wrap text-center">
    `;

    for (let i = 0; i < firstDayWeekday; i++) {
        html += `<div class="eth-day-cell empty" style="width: 14.28%; height: 30px;"></div>`;
    }

    for (let d = 1; d <= maxDays; d++) {
        const isSelected = d === selectedDay;
        const activeClass = isSelected ? 'btn-primary active text-white fw-bold shadow-sm' : 'btn-outline-light text-dark';
        html += `
            <div class="eth-day-cell p-0" style="width: 14.28%; height: 32px;">
                <button type="button" class="btn btn-sm w-100 h-100 p-0 eth-day-btn ${activeClass}" 
                        data-day="${d}" style="font-size: 0.8rem; border-radius: 6px;">
                    ${d}
                </button>
            </div>
        `;
    }

    html += `
            </div>
        </div>
    `;

    container.innerHTML = html;

    container.querySelectorAll('.eth-day-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const clickedDay = parseInt(btn.getAttribute('data-day'), 10);
            if (dInput) {
                dInput.value = clickedDay;
                syncEthiopianToGregorianLoan();
            }
        });
    });
}

export function initLoanDualCalendar() {
    const paymentDateInput = document.getElementById('payment_date');
    const ethYearLoan = document.getElementById('eth_year_loan');
    const ethMonthLoan = document.getElementById('eth_month_loan');
    const ethDayLoan = document.getElementById('eth_day_loan');

    if (!paymentDateInput) return;

    paymentDateInput.addEventListener('change', syncGregorianToEthiopianLoan);

    if (ethYearLoan) {
        ethYearLoan.addEventListener('change', syncEthiopianToGregorianLoan);
        ethYearLoan.addEventListener('input', syncEthiopianToGregorianLoan);
    }
    if (ethMonthLoan) {
        ethMonthLoan.addEventListener('change', syncEthiopianToGregorianLoan);
    }
    if (ethDayLoan) {
        ethDayLoan.addEventListener('change', syncEthiopianToGregorianLoan);
    }

    if (paymentDateInput.value) {
        syncGregorianToEthiopianLoan();
    }
}

window.LoanEthiopianCalendar = {
    gregorianToEthiopianDate,
    ethiopianToGregorianDate,
    formatEthiopianDisplay,
    syncGregorianToEthiopianLoan,
    syncEthiopianToGregorianLoan,
    renderInteractiveLoanMonthView,
    initLoanDualCalendar
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLoanDualCalendar);
} else {
    initLoanDualCalendar();
}
