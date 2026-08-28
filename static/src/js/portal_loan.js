/** @odoo-module **/

function updateLoanType(type) {
    const radioAdvance = document.getElementById('loan_type_advance');
    const radioHigh = document.getElementById('loan_type_high');
    const cardAdvance = document.getElementById('card_advance_salary');
    const cardHigh = document.getElementById('card_high_amount');
    const badgeAdvance = document.getElementById('badge_selected_advance');
    const badgeHigh = document.getElementById('badge_selected_high');
    const advanceInfoBox = document.getElementById('advance_salary_info_box');
    const loanAmountContainer = document.getElementById('loan_amount_container');
    const loanAmountInput = document.getElementById('loan_amount');
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
        if (loanAmountContainer) loanAmountContainer.style.display = 'none';

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
        if (loanAmountContainer) loanAmountContainer.style.display = 'block';

        if (loanAmountInput) {
            loanAmountInput.required = true;
            loanAmountInput.focus();
        }

        if (routingAdvance) routingAdvance.style.display = 'none';
        if (routingHigh) routingHigh.style.display = 'block';
    }
}

// Global hook for inline onclick handlers
window.setLoanType = updateLoanType;

function initLoanForm() {
    const radioAdvance = document.getElementById('loan_type_advance');
    const radioHigh = document.getElementById('loan_type_high');

    if (radioAdvance) {
        radioAdvance.addEventListener('change', () => updateLoanType('advance_salary'));
    }
    if (radioHigh) {
        radioHigh.addEventListener('change', () => updateLoanType('high_amount'));
    }

    // Determine initial state from pre-checked radio or default
    if (radioHigh && radioHigh.checked) {
        updateLoanType('high_amount');
    } else {
        updateLoanType('advance_salary');
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLoanForm);
} else {
    initLoanForm();
}
