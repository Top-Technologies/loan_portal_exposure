# -*- coding: utf-8 -*-
{
    'name': 'Loan Portal Exposure',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Loans',
    'summary': 'Expose Advance Salary Loans and High Monetary Amount Loans to Portal Users with Farm Manager and GM Approvals Module Integration',
    'description': """
Loan Portal Exposure for Odoo 18 & 19 Enterprise
================================================
Empowers workforce employees to apply for and track employee loans directly from the Odoo Customer Portal:

1. **Advance One Month Salary Loan**:
   - Short-term loan up to 1 month salary.
   - Routes to the employee's Farm Manager (who can be a Portal User or Internal User).
   - Farm Managers review and Approve/Reject directly from the portal dashboard (`/my/loans/to_approve`) or Approvals app.

2. **High Monetary Amount Loan**:
   - Long-term loan with flexible installment repayment terms and attachment justification.
   - Routes directly to the General Manager (GM) via the native Odoo Approvals module (`approval.request`).
   - Upon GM approval, the system automatically dispatches official confirmation emails to the HR Manager and Finance Manager.

3. **Approvals Module Integration**:
   - Seamlessly generates `approval.request` records for internal management oversight.
   - Real-time synchronization between portal approvals and backend Approvals app.
    """,
    'author': 'Custom Development',
    'website': 'https://www.odoo.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'portal',
        'hr',
        'mail',
        'approvals',
        'farm_management',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/approval_category_data.xml',
        'data/mail_template_data.xml',
        'views/hr_loan_views.xml',
        'views/hr_employee_views.xml',
        'views/res_config_settings_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'loan_portal_exposure/static/src/css/portal_loan.css',
            'loan_portal_exposure/static/src/js/portal_loan.js',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
