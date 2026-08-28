# Loan Portal Exposure for Odoo 18 & 19 Enterprise

**Technical Name:** `loan_portal_exposure`  
**License:** LGPL-3  
**Category:** Human Resources/Loans  
**Compatible Versions:** Odoo 18.0 & Odoo 19.0 Enterprise  

---

## 🌟 Overview

**Loan Portal Exposure** unlocks self-service Employee Loan applications for free **Portal Users** and introduces two specialized approval flows tailored for agricultural and corporate workforce management:

1. **Advance One Month Salary Loan**:
   - Short-term loan up to 1 month salary for emergency cash assistance.
   - Routes to the employee's **Farm Manager** (who can also be a **Portal User**).
   - Farm Managers review and approve/reject directly in the portal dashboard (`/my/loans/to_approve`) or Approvals app.

2. **High Monetary Amount Loan**:
   - Higher loan sums with customizable repayment durations (installments), justification reasons, and attachments.
   - Routes directly to the **General Manager (GM)** via the native Odoo **Approvals Module** (`approval.request`).
   - Upon GM approval, the system **automatically dispatches official email notifications to the HR Manager and Finance Manager** confirming the approved amount and terms for disbursement and payroll scheduling.

---

## 🚀 Key Features

- **Portal Dashboard (`/my/loans`)**: View active loans, total borrowed amount, pending requests, and request history.
- **Dynamic Application Form (`/my/loans/new`)**: Live monthly wage reference, installment calculator, attachment upload, and approver route preview.
- **Approvals Module Integration**: Automatically generates `approval.request` records in the native Approvals app.
- **Approvals Dashboard (`/my/loans/to_approve`)**: Portal-based review for Farm Managers and the GM.
- **Clean Notifications**: Clear email templates and uncluttered chatter notes without raw HTML email dumps.

---

## ⚙️ Configuration

1. In **Settings $\rightarrow$ General Settings $\rightarrow$ Employee Loans & Approvals**:
   - Set the **General Manager (GM)**.
   - Set the **HR Manager**.
   - Set the **Finance Manager**.
2. Assign employees to their **Farm** (`farm.farm`) and assign the **Farm Manager**.
3. Portal employees can now log into `/my` and request loans!
