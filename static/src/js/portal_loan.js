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
    const installmentInput = document.getElementById('installment_months');
    const ruleAlertContainer = document.getElementById('rule_alert_container');
    const ruleAlertBox = document.getElementById('rule_alert_box');
    const submitBtn = document.querySelector('#loan_application_form button[type="submit"]');

    if (!loanAmountInput || !installmentInput || !ruleAlertContainer || !ruleAlertBox) return;

    const amount = parseFloat(loanAmountInput.value) || 0.0;
    const months = parseInt(installmentInput.value, 10) || 1;
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
    const safeMonths = months > 0 ? months : 1;
    const monthlyDeduction = (amount / safeMonths).toFixed(2);

    if (salary > 0 && amount > (maxLoan + 0.01)) {
        // Exceeds 4x salary -> Warning, but allow to proceed (modal will confirm on submit)
        ruleAlertBox.className = 'alert alert-warning py-2 px-3 small rounded-3 mb-0';
        ruleAlertBox.innerHTML = `<strong><i class="fa fa-exclamation-triangle me-1"></i> Above Standard Guideline:</strong> Requested amount (${amount.toLocaleString()} ${currency}) exceeds your 4-month salary limit (<strong>${maxLoan.toLocaleString()} ${currency}</strong>).<br/><span class="mt-1 d-block text-muted">A confirmation popup will appear on submit. Estimated deduction: <strong>${monthlyDeduction} ${currency}/month</strong> for <strong>${safeMonths} Months</strong>.</span>`;
        if (submitBtn) submitBtn.disabled = false;
    } else if (salary > 0 && (amount / safeMonths) > (maxInstallment + 0.01)) {
        // Notice on deduction
        ruleAlertBox.className = 'alert alert-info py-2 px-3 small rounded-3 mb-0';
        ruleAlertBox.innerHTML = `<strong><i class="fa fa-info-circle me-1"></i> Repayment Plan:</strong> <strong>${safeMonths} Months</strong> at <strong>${monthlyDeduction} ${currency} / month</strong>.<br/><span class="small text-muted">Note: Monthly installment is higher than 1/3 standard salary deduction (${maxInstallment.toFixed(2)} ${currency}/mo).</span>`;
        if (submitBtn) submitBtn.disabled = false;
    } else {
        // Valid within guideline
        ruleAlertBox.className = 'alert alert-success py-2 px-3 small rounded-3 mb-0';
        ruleAlertBox.innerHTML = `<strong><i class="fa fa-check-circle me-1"></i> Repayment Plan:</strong> <strong>${safeMonths} Months</strong> at <strong>${monthlyDeduction} ${currency} / month</strong>.`;
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
    const installmentInput = document.getElementById('installment_months');
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
    if (installmentInput) {
        installmentInput.addEventListener('input', checkHighAmountRules);
        installmentInput.addEventListener('change', checkHighAmountRules);
    }

    // Preset buttons for duration
    document.querySelectorAll('.btn-duration-preset').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const m = btn.getAttribute('data-months');
            if (installmentInput) {
                installmentInput.value = m;
                checkHighAmountRules();
            }
        });
    });

    // Determine initial state from pre-checked radio or default
    if (radioHigh && radioHigh.checked) {
        updateLoanType('high_amount');
    } else {
        updateLoanType('advance_salary');
    }

    // Form Submission & 4x Salary Warning Modal Handling
    let salaryWarningConfirmed = false;

    if (loanForm) {
        loanForm.addEventListener('submit', (e) => {
            if (!loanForm.checkValidity()) return;

            const radioHigh = document.getElementById('loan_type_high');
            const isHigh = radioHigh && radioHigh.checked;
            const amount = parseFloat(loanAmountInput ? loanAmountInput.value : 0) || 0.0;
            const salary = parseFloat(loanAmountInput ? loanAmountInput.getAttribute('data-salary') : 0) || 0.0;
            const maxLoan = parseFloat(loanAmountInput ? loanAmountInput.getAttribute('data-max-loan') : 0) || (4 * salary);
            const currency = loanAmountInput ? (loanAmountInput.getAttribute('data-currency') || '') : '';

            if (isHigh && salary > 0 && amount > (maxLoan + 0.01) && !salaryWarningConfirmed) {
                e.preventDefault();
                e.stopPropagation();

                const modalElem = document.getElementById('loan_salary_warning_modal');
                const warnAmtElem = document.getElementById('modal_warn_loan_amount');
                const warnMaxElem = document.getElementById('modal_warn_max_limit');

                if (warnAmtElem) warnAmtElem.textContent = `${amount.toLocaleString()} ${currency}`;
                if (warnMaxElem) warnMaxElem.textContent = `${maxLoan.toLocaleString()} ${currency}`;

                if (modalElem && window.bootstrap && window.bootstrap.Modal) {
                    const modalInstance = window.bootstrap.Modal.getOrCreateInstance(modalElem);
                    modalInstance.show();

                    const confirmBtn = document.getElementById('btn_confirm_proceed_loan');
                    if (confirmBtn) {
                        confirmBtn.onclick = () => {
                            salaryWarningConfirmed = true;
                            modalInstance.hide();
                            if (loanForm.requestSubmit) {
                                loanForm.requestSubmit();
                            } else {
                                loanForm.submit();
                            }
                        };
                    }
                } else if (modalElem && window.$) {
                    window.$(modalElem).modal('show');
                    const confirmBtn = document.getElementById('btn_confirm_proceed_loan');
                    if (confirmBtn) {
                        confirmBtn.onclick = () => {
                            salaryWarningConfirmed = true;
                            window.$(modalElem).modal('hide');
                            loanForm.submit();
                        };
                    }
                } else {
                    const proceed = confirm(`You are asking for ${amount.toLocaleString()} ${currency}, which is more than your 4-month salary limit (${maxLoan.toLocaleString()} ${currency}). Do you want to proceed?`);
                    if (proceed) {
                        salaryWarningConfirmed = true;
                        loanForm.submit();
                    }
                }
                return;
            }

            // Normal submission loading state
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
