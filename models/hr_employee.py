# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    loan_ids = fields.One2many(
        'hr.loan',
        'employee_id',
        string="Loans"
    )
    loan_count = fields.Integer(
        string="Loans Count",
        compute="_compute_loan_stats"
    )
    active_loan_amount = fields.Monetary(
        string="Active Loans Total",
        compute="_compute_loan_stats",
        currency_field='currency_id'
    )
    outstanding_loan_balance = fields.Monetary(
        string="Outstanding Loans Balance",
        compute="_compute_loan_stats",
        currency_field='currency_id',
        help="Remaining principal/balance of approved loans."
    )
    outstanding_attachment_balance = fields.Monetary(
        string="Outstanding Salary Attachments",
        compute="_compute_loan_stats",
        currency_field='currency_id',
        help="Remaining balance on open salary attachments."
    )
    total_outstanding_liability = fields.Monetary(
        string="Total Outstanding Liabilities",
        compute="_compute_loan_stats",
        currency_field='currency_id',
        help="Combined sum of outstanding loans and salary attachments."
    )
    has_outstanding_liabilities = fields.Boolean(
        string="Has Outstanding Liabilities",
        compute="_compute_loan_stats"
    )
    active_loans_count = fields.Integer(
        string="Active Loans Count",
        compute="_compute_loan_stats"
    )
    active_attachments_count = fields.Integer(
        string="Active Attachments Count",
        compute="_compute_loan_stats"
    )

    @api.depends('loan_ids', 'loan_ids.state', 'loan_ids.loan_amount', 'loan_ids.salary_attachment_id.remaining_amount', 'salary_attachment_ids', 'salary_attachment_ids.state', 'salary_attachment_ids.remaining_amount', 'salary_attachment_ids.total_amount')
    def _compute_loan_stats(self):
        for emp in self:
            all_loans = emp.loan_ids
            active_loans = all_loans.filtered(lambda l: l.state == 'approved')
            emp.loan_count = len(all_loans)
            emp.active_loans_count = len(active_loans)
            emp.active_loan_amount = sum(active_loans.mapped('loan_amount'))

            # Compute outstanding loan balance from linked salary attachments or principal
            loan_rem = 0.0
            for l in active_loans:
                if l.salary_attachment_id and l.salary_attachment_id.state == 'open':
                    loan_rem += (l.salary_attachment_id.remaining_amount or l.loan_amount)
                elif not l.salary_attachment_id:
                    loan_rem += l.loan_amount
            emp.outstanding_loan_balance = loan_rem

            # Open salary attachments
            open_attachments = emp.salary_attachment_ids.filtered(lambda a: a.state == 'open')
            emp.active_attachments_count = len(open_attachments)
            emp.outstanding_attachment_balance = sum(open_attachments.mapped('remaining_amount'))

            emp.total_outstanding_liability = emp.outstanding_loan_balance + emp.outstanding_attachment_balance
            emp.has_outstanding_liabilities = emp.total_outstanding_liability > 0

    def get_assigned_farm_manager(self):
        """ Resolves the designated Farm Manager for this employee """
        self.ensure_one()
        # 1. From current active farm
        farm = getattr(self, 'current_farm_id', False) or getattr(self, 'initial_farm_id', False)
        if farm and farm.manager_id:
            return farm.manager_id

        # 2. Fallback to direct parent / manager
        if self.parent_id:
            return self.parent_id

        return self.env['hr.employee'].browse()

    def get_monthly_salary_estimate(self):
        """ Calculates baseline monthly salary for advance salary loan reference """
        self.ensure_one()
        # Check active contract wage
        if hasattr(self, 'contract_id') and self.contract_id and self.contract_id.wage:
            return self.contract_id.wage

        if hasattr(self, 'matrix_basic_wage') and self.matrix_basic_wage:
            return self.matrix_basic_wage

        # For temporary farm workers, check farm daily temporary rate * 26 working days
        farm = getattr(self, 'current_farm_id', False) or getattr(self, 'initial_farm_id', False)
        if farm and hasattr(farm, 'temporary_rate_ids') and farm.temporary_rate_ids:
            active_rate = farm.temporary_rate_ids.filtered(lambda r: r.active)[:1]
            if active_rate:
                return active_rate.full_day_rate * 26.0

        return 0.0

    def action_view_employee_loans(self):
        self.ensure_one()
        return {
            'name': _('Loans for %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'hr.loan',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_view_employee_attachments(self):
        self.ensure_one()
        return {
            'name': _('Salary Attachments for %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'hr.salary.attachment',
            'view_mode': 'list,form',
            'domain': [('employee_ids', 'in', self.id)],
            'context': {'default_employee_ids': [(4, self.id)]},
        }
