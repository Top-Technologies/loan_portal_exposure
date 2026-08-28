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

    @api.depends('loan_ids', 'loan_ids.state', 'loan_ids.loan_amount')
    def _compute_loan_stats(self):
        for emp in self:
            active_loans = emp.loan_ids.filtered(lambda l: l.state == 'approved')
            emp.loan_count = len(emp.loan_ids)
            emp.active_loan_amount = sum(active_loans.mapped('loan_amount'))

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
            'name': _('Loans for %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.loan',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
