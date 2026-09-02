# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='employee_id.company_id.currency_id'
    )
    has_outstanding_liabilities = fields.Boolean(
        string='Has Outstanding Liabilities',
        compute='_compute_employee_liabilities'
    )
    outstanding_loan_balance = fields.Monetary(
        string='Outstanding Loans Balance',
        compute='_compute_employee_liabilities',
        currency_field='currency_id'
    )
    outstanding_attachment_balance = fields.Monetary(
        string='Outstanding Salary Attachments',
        compute='_compute_employee_liabilities',
        currency_field='currency_id'
    )
    total_outstanding_liability = fields.Monetary(
        string='Total Outstanding Financial Liability',
        compute='_compute_employee_liabilities',
        currency_field='currency_id'
    )
    active_loan_ids = fields.Many2many(
        'hr.loan',
        string='Active Loans',
        compute='_compute_employee_liabilities'
    )
    open_attachment_ids = fields.Many2many(
        'hr.salary.attachment',
        string='Open Salary Attachments',
        compute='_compute_employee_liabilities'
    )

    @api.depends('employee_id')
    def _compute_employee_liabilities(self):
        for wizard in self:
            emp = wizard.employee_id
            if not emp:
                wizard.has_outstanding_liabilities = False
                wizard.outstanding_loan_balance = 0.0
                wizard.outstanding_attachment_balance = 0.0
                wizard.total_outstanding_liability = 0.0
                wizard.active_loan_ids = False
                wizard.open_attachment_ids = False
                continue

            active_loans = emp.loan_ids.filtered(lambda l: l.state == 'approved')
            open_attachments = emp.salary_attachment_ids.filtered(lambda a: a.state == 'open')

            wizard.active_loan_ids = active_loans
            wizard.open_attachment_ids = open_attachments

            loan_rem = 0.0
            for l in active_loans:
                if l.salary_attachment_id and l.salary_attachment_id.state == 'open':
                    loan_rem += (l.salary_attachment_id.remaining_amount or l.loan_amount)
                elif not l.salary_attachment_id:
                    loan_rem += l.loan_amount

            wizard.outstanding_loan_balance = loan_rem
            wizard.outstanding_attachment_balance = sum(open_attachments.mapped('remaining_amount'))
            wizard.total_outstanding_liability = loan_rem + wizard.outstanding_attachment_balance
            wizard.has_outstanding_liabilities = wizard.total_outstanding_liability > 0

    def action_register_departure(self):
        res = super().action_register_departure()
        for wizard in self:
            emp = wizard.employee_id
            if wizard.has_outstanding_liabilities:
                msg_body = _(
                    "<b>⚠️ Offboarding / Resignation Clearance Summary:</b><br/>"
                    "Employee marked for departure with outstanding liabilities:<br/>"
                    "• <b>Active Loans Balance:</b> %(loans).2f %(curr)s (%(l_cnt)s active)<br/>"
                    "• <b>Open Salary Attachments:</b> %(atts).2f %(curr)s (%(a_cnt)s open)<br/>"
                    "• <b>Total Unsettled Liability:</b> <strong style='color: #dc3545;'>%(total).2f %(curr)s</strong><br/>"
                    "<i>Please ensure full recovery / settlement during final payroll calculation.</i>"
                ) % {
                    'loans': wizard.outstanding_loan_balance,
                    'curr': wizard.currency_id.symbol or 'ETB',
                    'l_cnt': len(wizard.active_loan_ids),
                    'atts': wizard.outstanding_attachment_balance,
                    'a_cnt': len(wizard.open_attachment_ids),
                    'total': wizard.total_outstanding_liability,
                }
                emp.message_post(
                    body=msg_body,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
        return res
