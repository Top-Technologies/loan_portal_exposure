# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.addons.mail.tools.parser import parse_res_ids


class MailActivitySchedule(models.TransientModel):
    _inherit = 'mail.activity.schedule'

    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        compute="_compute_employee_financials"
    )
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        compute="_compute_employee_financials"
    )
    has_outstanding_liabilities = fields.Boolean(
        string="Has Outstanding Liabilities",
        compute="_compute_employee_financials"
    )
    outstanding_loan_balance = fields.Monetary(
        string="Outstanding Loans Balance",
        compute="_compute_employee_financials",
        currency_field='currency_id'
    )
    outstanding_attachment_balance = fields.Monetary(
        string="Outstanding Salary Attachments",
        compute="_compute_employee_financials",
        currency_field='currency_id'
    )
    total_outstanding_liability = fields.Monetary(
        string="Total Outstanding Financial Liability",
        compute="_compute_employee_financials",
        currency_field='currency_id'
    )
    active_loan_ids = fields.Many2many(
        'hr.loan',
        string="Active Loans",
        compute="_compute_employee_financials"
    )
    open_attachment_ids = fields.Many2many(
        'hr.salary.attachment',
        string="Open Salary Attachments",
        compute="_compute_employee_financials"
    )

    @api.depends('res_model', 'res_ids')
    def _compute_employee_financials(self):
        for wizard in self:
            emp = False
            if wizard.res_model == 'hr.employee':
                res_ids = parse_res_ids(wizard.res_ids, self.env)
                if res_ids:
                    emp = self.env['hr.employee'].browse(res_ids[0])
                elif self.env.context.get('active_id'):
                    emp = self.env['hr.employee'].browse(self.env.context.get('active_id'))

            if not emp or not emp.exists():
                wizard.employee_id = False
                wizard.currency_id = False
                wizard.has_outstanding_liabilities = False
                wizard.outstanding_loan_balance = 0.0
                wizard.outstanding_attachment_balance = 0.0
                wizard.total_outstanding_liability = 0.0
                wizard.active_loan_ids = False
                wizard.open_attachment_ids = False
                continue

            wizard.employee_id = emp.id
            wizard.currency_id = emp.company_id.currency_id.id or self.env.company.currency_id.id

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
