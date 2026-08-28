# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    loan_gm_user_id = fields.Many2one(
        'res.users',
        string="General Manager (GM)",
        domain="[('share', '=', False)]",
        help="Designated General Manager responsible for reviewing and approving High Monetary Amount Loans."
    )
    loan_hr_manager_id = fields.Many2one(
        'res.users',
        string="HR Manager",
        domain="[('share', '=', False)]",
        help="HR Manager who receives automatic email confirmation when high monetary loans are approved."
    )
    loan_finance_manager_id = fields.Many2one(
        'res.users',
        string="Finance Manager",
        domain="[('share', '=', False)]",
        help="Finance Manager who receives automatic email confirmation for loan disbursement."
    )
    loan_advance_category_id = fields.Many2one(
        'approval.category',
        string="Advance Salary Approval Category"
    )
    loan_high_amount_category_id = fields.Many2one(
        'approval.category',
        string="High Amount Loan Approval Category"
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    loan_gm_user_id = fields.Many2one(
        related='company_id.loan_gm_user_id',
        string="General Manager (GM)",
        readonly=False
    )
    loan_hr_manager_id = fields.Many2one(
        related='company_id.loan_hr_manager_id',
        string="HR Manager",
        readonly=False
    )
    loan_finance_manager_id = fields.Many2one(
        related='company_id.loan_finance_manager_id',
        string="Finance Manager",
        readonly=False
    )
    loan_advance_category_id = fields.Many2one(
        related='company_id.loan_advance_category_id',
        string="Advance Salary Approval Category",
        readonly=False
    )
    loan_high_amount_category_id = fields.Many2one(
        related='company_id.loan_high_amount_category_id',
        string="High Amount Loan Approval Category",
        readonly=False
    )
