/** @odoo-module **/

function updateLoanType(type) {
    const radioAdvance = document.getElementById('loan_type_advance');
    const radioHigh = document.getElementById('loan_type_high');
    const cardAdvance = document.getElementById('card_advance_salary');
    const cardHigh = document.getElementById('card_high_amount');
    const badgeAdvance = document.getElementById('badge_selected_advance');
    const badgeHigh = document.getElementById('badge_selected_high');
    const advanceInfoBox = document.getElementById('advance_salary_info_box');
    const highAmountContainer = document.getElementById('high_amount_container');
    const loanAmountInput = document.getElementById('loan_amount');
    const installmentSelect = document.getElementById('installment_months');
    const routingAdvance = document.getElementById('routing_text_advance');
    const routingHigh = document.getElementById('routing_text_high');

    const selectedType = type || (radioHigh && radioHigh.checked ? 'high_amount' : 'advance_salary');

    if (selectedType === 'advance_salary') {
        if (radioAdvance) radioAdvance.checked = true;
        if (radioHigh) radioHigh.checked = false;

        if (cardAdvance) cardAdvance.classList.add('active');
        if (cardHigh) cardHigh.classList.remove('active');

        if (badgeAdvance) badgeAdvance.style.display = 'inline-block';
        if (badgeHigh) badgeHigh.style.display = 'none';

        if (advanceInfoBox) advanceInfoBox.style.display = 'block';
        if (highAmountContainer) highAmountContainer.style.display = 'none';

        if (loanAmountInput) {
            loanAmountInput.required = false;
            loanAmountInput.value = '';
        }

        if (routingAdvance) routingAdvance.style.display = 'block';
        if (routingHigh) routingHigh.style.display = 'none';
    } else {
        if (radioAdvance) radioAdvance.checked = false;
        if (radioHigh) radioHigh.checked = true;

        if (cardAdvance) cardAdvance.classList.remove('active');
        if (cardHigh) cardHigh.classList.add('active');

        if (badgeAdvance) badgeAdvance.style.display = 'none';
        if (badgeHigh) badgeHigh.style.display = 'inline-block';

        if (advanceInfoBox) advanceInfoBox.style.display = 'none';
        if (highAmountContainer) highAmountContainer.style.display = 'block';

        if (loanAmountInput) {
            loanAmountInput.required = true;
            loanAmountInput.focus();
        }

        if (routingAdvance) routingAdvance.style.display = 'none';
        if (routingHigh) routingHigh.style.display = 'block';

        checkHighAmountRules();
    }
}

function checkHighAmountRules() {
    const loanAmountInput = document.getElementById('loan_amount');
    const installmentSelect = document.getElementById('installment_months');
    const ruleAlertContainer = document.getElementById('rule_alert_container');
    const ruleAlertBox = document.getElementById('rule_alert_box');
    const submitBtn = document.querySelector('#loan_application_form button[type="submit"]');

    if (!loanAmountInput || !installmentSelect || !ruleAlertContainer || !ruleAlertBox) return;

    const amount = parseFloat(loanAmountInput.value) || 0.0;
    const months = parseInt(installmentSelect.value) || 6;
    const salary = parseFloat(loanAmountInput.getAttribute('data-salary')) || 0.0;
    const maxLoan = parseFloat(loanAmountInput.getAttribute('data-max-loan')) || (4 * salary);
    const maxInstallment = parseFloat(loanAmountInput.getAttribute('data-max-installment')) || (salary / 3.0);
    const currency = loanAmountInput.getAttribute('data-currency') || '';

    if (amount <= 0) {
        ruleAlertContainer.style.display = 'none';
        if (submitBtn) submitBtn.disabled = false;
        return;
    }

    ruleAlertContainer.style.display = 'block';
    const monthlyDeduction = (amount / months).toFixed(2);

    if (salary > 0 && amount > (maxLoan + 0.01)) {
        // Exceeds 4x salary
        ruleAlertBox.className = 'alert alert-danger py-2 px-3 small rounded-3 mb-0';
        ruleAlertBox.innerHTML = `<strong><i class="fa fa-exclamation-triangle me-1"></i> Loan Limit Exceeded:</strong> Requested amount (${amount.toLocaleString()} ${currency}) exceeds the maximum 4x salary limit of <strong>${maxLoan.toLocaleString()} ${currency}</strong>.`;
        if (submitBtn) submitBtn.disabled = true;
    } else if (salary > 0 && (amount / months) > (maxInstallment + 0.01)) {
        // Exceeds 1/3 salary deduction
        ruleAlertBox.className = 'alert alert-danger py-2 px-3 small rounded-3 mb-0';
        ruleAlertBox.innerHTML = `<strong><i class="fa fa-exclamation-circle me-1"></i> Installment Cap Exceeded:</strong> Monthly installment (${monthlyDeduction} ${currency}/mo) exceeds the maximum allowed 1/3 of your monthly salary (<strong>${maxInstallment.toFixed(2)} ${currency}/mo</strong>).<br/><span class="mt-1 d-block">💡 <em>Tip: Switch to <strong>12 Months</strong> duration or reduce the loan amount.</em></span>`;
        if (submitBtn) submitBtn.disabled = true;
    } else {
        // Valid
        ruleAlertBox.className = 'alert alert-success py-2 px-3 small rounded-3 mb-0';
        ruleAlertBox.innerHTML = `<strong><i class="fa fa-check-circle me-1"></i> Repayment Plan:</strong> <strong>${months} Months</strong> at <strong>${monthlyDeduction} ${currency} / month</strong>. (Within maximum allowed 1/3 monthly salary deduction limit).`;
        if (submitBtn) submitBtn.disabled = false;
    }
}

// Global hooks
window.setLoanType = updateLoanType;
window.checkHighAmountRules = checkHighAmountRules;

function initLoanForm() {
    const radioAdvance = document.getElementById('loan_type_advance');
    const radioHigh = document.getElementById('loan_type_high');
    const loanAmountInput = document.getElementById('loan_amount');
    const installmentSelect = document.getElementById('installment_months');
    const loanForm = document.getElementById('loan_application_form');
    const processingOverlay = document.getElementById('loan_processing_overlay');

    if (radioAdvance) {
        radioAdvance.addEventListener('change', () => updateLoanType('advance_salary'));
    }
    if (radioHigh) {
        radioHigh.addEventListener('change', () => updateLoanType('high_amount'));
    }

    if (loanAmountInput) {
        loanAmountInput.addEventListener('input', checkHighAmountRules);
        loanAmountInput.addEventListener('change', checkHighAmountRules);
    }
    if (installmentSelect) {
        installmentSelect.addEventListener('change', checkHighAmountRules);
    }

    // Determine initial state from pre-checked radio or default
    if (radioHigh && radioHigh.checked) {
        updateLoanType('high_amount');
    } else {
        updateLoanType('advance_salary');
    }

    // Form Submission Loading Indicator
    if (loanForm) {
        loanForm.addEventListener('submit', () => {
            if (!loanForm.checkValidity()) return;

            const submitBtn = loanForm.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fa fa-circle-o-notch fa-spin me-2"></i> Submitting Loan Application...';
            }
            if (processingOverlay) {
                processingOverlay.style.display = 'flex';
            }
        });
    }

    // Approval / Rejection Action Loaders
    document.querySelectorAll('form[action*="/my/loans/"]').forEach((form) => {
        if (form.id === 'loan_application_form') return;
        form.addEventListener('submit', () => {
            const btn = form.querySelector('button[type="submit"]');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<i class="fa fa-circle-o-notch fa-spin me-1"></i> Processing...';
            }
            if (processingOverlay) {
                const title = document.getElementById('loan_processing_loader_title');
                const text = document.getElementById('loan_processing_loader_text');
                if (title) title.innerText = 'Processing Loan Decision...';
                if (text) text.innerText = 'Updating record and sending notifications. Please wait...';
                processingOverlay.style.display = 'flex';
            }
        });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLoanForm);
} else {
    initLoanForm();
}
