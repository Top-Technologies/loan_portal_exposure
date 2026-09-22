# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from .ethiopian_date_utils import (
    ethiopian_to_gregorian,
    gregorian_to_ethiopian,
    format_ethiopian_date,
    ETHIOPIAN_MONTHS_AMHARIC,
    get_ethiopian_days_in_month,
)

ETHIOPIAN_MONTH_SELECTION = [
    (str(i), f"{i} - {ETHIOPIAN_MONTHS_AMHARIC[i]}") for i in range(1, 14)
]


class ApprovalCategory(models.Model):
    _inherit = 'approval.category'

    def init(self):
        super().init()
        try:
            with self.env.cr.savepoint():
                adv_cat = self.env.ref('loan_portal_exposure.approval_category_advance_salary_loan', raise_if_not_found=False)
                if adv_cat and adv_cat.manager_approval == 'required':
                    adv_cat.sudo().write({'manager_approval': 'approver'})
        except Exception:
            pass


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    loan_ids = fields.One2many(
        'hr.loan',
        'approval_request_id',
        string="Linked Employee Loans"
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        default=lambda self: self.env.user.employee_id,
        tracking=True,
        help="The employee for whom the loan is being requested (the user themselves or on behalf of another employee)."
    )
    is_loan_category = fields.Boolean(
        string="Is Loan Request",
        compute="_compute_is_loan_category",
        store=True
    )
    loan_type = fields.Selection([
        ('advance_salary', 'Advance One Month Salary Loan'),
        ('high_amount', 'High Monetary Amount Loan'),
    ], string="Loan Type", compute="_compute_loan_type", store=True, readonly=True)

    installment_months = fields.Integer(
        string="Repayment Duration (Months)",
        default=1,
        help="Number of monthly installments to repay the loan."
    )
    payment_date = fields.Date(
        string="Disbursement / Start Date",
        default=fields.Date.today,
        help="Preferred disbursement date for the loan."
    )
    ethiopian_payment_date = fields.Char(
        string="Ethiopian Disbursement Date",
        compute="_compute_ethiopian_payment_date",
        store=True,
        help="Preferred disbursement date in the Ethiopian (Amharic) calendar."
    )
    eth_month_loan = fields.Selection(
        ETHIOPIAN_MONTH_SELECTION,
        string="Ethiopian Month (ወር)"
    )
    eth_day_loan = fields.Integer(
        string="Ethiopian Day (ቀን)",
        default=1
    )
    eth_year_loan = fields.Integer(
        string="Ethiopian Year (ዓመት)",
        default=2018
    )

    @api.depends('category_id')
    def _compute_is_loan_category(self):
        adv_cat = self.env.ref('loan_portal_exposure.approval_category_advance_salary_loan', raise_if_not_found=False)
        high_cat = self.env.ref('loan_portal_exposure.approval_category_high_amount_loan', raise_if_not_found=False)
        for req in self:
            req.is_loan_category = bool(
                (adv_cat and req.category_id == adv_cat) or
                (high_cat and req.category_id == high_cat) or
                (req.category_id and 'loan' in (req.category_id.name or '').lower())
            )

    @api.depends('category_id')
    def _compute_loan_type(self):
        adv_cat = self.env.ref('loan_portal_exposure.approval_category_advance_salary_loan', raise_if_not_found=False)
        for req in self:
            if (adv_cat and req.category_id == adv_cat) or (req.category_id and 'advance' in (req.category_id.name or '').lower()):
                req.loan_type = 'advance_salary'
                req.installment_months = 3
            else:
                req.loan_type = 'high_amount'
                if not req.installment_months or req.installment_months == 3:
                    req.installment_months = 12

    @api.depends('payment_date')
    def _compute_ethiopian_payment_date(self):
        for req in self:
            if req.payment_date:
                req.ethiopian_payment_date = format_ethiopian_date(req.payment_date, lang='am', include_weekday=True)
                ey, em, ed = gregorian_to_ethiopian(req.payment_date)
                req.eth_year_loan = ey
                req.eth_month_loan = str(em)
                req.eth_day_loan = ed
            else:
                req.ethiopian_payment_date = ''

    @api.onchange('payment_date')
    def _onchange_payment_date(self):
        if self.payment_date:
            ey, em, ed = gregorian_to_ethiopian(self.payment_date)
            self.eth_year_loan = ey
            self.eth_month_loan = str(em)
            self.eth_day_loan = ed
            self.ethiopian_payment_date = format_ethiopian_date(self.payment_date, lang='am', include_weekday=True)

    @api.onchange('eth_year_loan', 'eth_month_loan', 'eth_day_loan')
    def _onchange_ethiopian_date_parts(self):
        if self.eth_year_loan and self.eth_month_loan and self.eth_day_loan:
            try:
                ey = int(self.eth_year_loan)
                em = int(self.eth_month_loan)
                ed = int(self.eth_day_loan)
                max_days = get_ethiopian_days_in_month(ey, em)
                if ed > max_days:
                    ed = max_days
                    self.eth_day_loan = ed
                g_date = ethiopian_to_gregorian(ey, em, ed)
                self.payment_date = g_date
                self.ethiopian_payment_date = format_ethiopian_date(g_date, lang='am', include_weekday=True)
            except Exception:
                pass

    @api.onchange('employee_id', 'category_id', 'request_owner_id')
    def _onchange_employee_or_category(self):
        adv_cat = self.env.ref('loan_portal_exposure.approval_category_advance_salary_loan', raise_if_not_found=False)
        is_advance = (adv_cat and self.category_id == adv_cat) or (self.category_id and 'advance' in (self.category_id.name or '').lower())
        if is_advance:
            self.loan_type = 'advance_salary'
            self.installment_months = 3
            if self.employee_id:
                salary = self.employee_id.get_monthly_salary_estimate()
                if salary > 0:
                    self.amount = salary
        else:
            self.loan_type = 'high_amount'
            if not self.installment_months or self.installment_months == 3:
                self.installment_months = 12

        if self.is_loan_category:
            self._compute_approver_ids()

    @api.depends('category_id', 'request_owner_id', 'employee_id', 'loan_type')
    def _compute_approver_ids(self):
        super()._compute_approver_ids()
        for req in self:
            if not req.is_loan_category:
                continue

            emp = req.employee_id or req.request_owner_id.employee_id
            approver_user_ids = []

            if req.loan_type == 'advance_salary':
                # 1. Employee's direct manager
                if emp and emp.parent_id and emp.parent_id.user_id:
                    approver_user_ids.append(emp.parent_id.user_id.id)
                # 2. Employee's Farm Manager
                farm = (emp.current_farm_id or emp.initial_farm_id) if emp else False
                if farm and farm.manager_id and farm.manager_id.user_id:
                    if farm.manager_id.user_id.id not in approver_user_ids:
                        approver_user_ids.append(farm.manager_id.user_id.id)
                # 3. Fallback to GM / Loan Admin
                if not approver_user_ids:
                    gm_user = req.company_id.loan_gm_user_id or self.env.ref('base.user_admin', raise_if_not_found=False)
                    if gm_user:
                        approver_user_ids.append(gm_user.id)
            else:  # high_amount
                gm_user = req.company_id.loan_gm_user_id or self.env.ref('base.user_admin', raise_if_not_found=False)
                if gm_user:
                    approver_user_ids.append(gm_user.id)

            if approver_user_ids:
                existing_uids = req.approver_ids.mapped('user_id.id')
                new_commands = []
                for uid in approver_user_ids:
                    if uid not in existing_uids:
                        new_commands.append(fields.Command.create({
                            'user_id': uid,
                            'status': 'new',
                            'required': True,
                            'sequence': 10,
                        }))
                if new_commands:
                    req.update({'approver_ids': new_commands})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            category_id = vals.get('category_id')
            if category_id:
                category = self.env['approval.category'].browse(category_id)
                if category and category.automated_sequence and not category.sequence_id:
                    # Fix missing sequence in database so next_by_id() does not query id=false
                    seq_code = category.sequence_code or 'LOAN'
                    sequence = self.env['ir.sequence'].sudo().create({
                        'name': f"Approval Sequence {seq_code}",
                        'padding': 4,
                        'prefix': f"{seq_code}/%(year)s/",
                        'company_id': category.company_id.id if category.company_id else False,
                    })
                    category.sudo().sequence_id = sequence.id

        created_requests = super().create(vals_list)
        for req in created_requests:
            if req.is_loan_category:
                req._create_or_update_linked_loan()
        return created_requests

    def _create_or_update_linked_loan(self):
        """ Creates or updates the linked hr.loan record for this approval request. """
        HrLoan = self.env['hr.loan'].sudo()
        for req in self:
            if not req.is_loan_category:
                continue

            employee = req.employee_id or req.request_owner_id.employee_id
            if not employee:
                continue

            loan = req.loan_ids[:1]
            loan_vals = {
                'employee_id': employee.id,
                'company_id': req.company_id.id or employee.company_id.id,
                'loan_type': req.loan_type or 'advance_salary',
                'loan_amount': req.amount or 0.0,
                'payment_date': req.payment_date or fields.Date.today(),
                'installment_months': req.installment_months or (3 if req.loan_type == 'advance_salary' else 12),
                'reason': req.reason and req.reason.strip() or req.name or _('Loan Application via Approvals'),
                'approval_request_id': req.id,
                'is_portal_submitted': False,
            }

            if loan:
                loan.write(loan_vals)
            else:
                initial_state = 'waiting_farm_manager' if req.loan_type == 'advance_salary' else 'waiting_gm'
                loan_vals['state'] = initial_state
                loan = HrLoan.create(loan_vals)

    def action_confirm(self):
        for req in self:
            if req.is_loan_category:
                # Ensure category does not block users who don't have an HR manager set
                if req.category_id.manager_approval == 'required':
                    req.category_id.sudo().write({'manager_approval': 'approver'})
                # If approvers are missing, recompute
                if not req.approver_ids:
                    req._compute_approver_ids()
                # Ensure at least 1 approver exists so approval_minimum passes
                if not req.approver_ids:
                    fallback_user = req.company_id.loan_gm_user_id or self.env.ref('base.user_admin', raise_if_not_found=False) or self.env.user
                    req.write({
                        'approver_ids': [fields.Command.create({
                            'user_id': fallback_user.id,
                            'status': 'new',
                            'required': True,
                            'sequence': 10,
                        })]
                    })

        res = super().action_confirm()
        for req in self:
            if req.is_loan_category:
                req._create_or_update_linked_loan()
        return res

    def action_approve(self, approver=None):
        res = super().action_approve(approver=approver)
        for req in self:
            if req.request_status == 'approved' and req.is_loan_category:
                if not req.loan_ids:
                    req._create_or_update_linked_loan()
                for loan in req.loan_ids.filtered(lambda l: l.state in ['draft', 'waiting_farm_manager', 'waiting_gm']):
                    if loan.loan_type == 'high_amount':
                        loan.action_portal_gm_approve()
                    else:
                        loan.action_portal_farm_manager_approve()
        return res

    def action_refuse(self, approver=None):
        res = super().action_refuse(approver=approver)
        for req in self:
            if req.request_status == 'refused':
                for loan in req.loan_ids.filtered(lambda l: l.state in ['draft', 'waiting_farm_manager', 'waiting_gm']):
                    loan.action_portal_reject(reason=_("Refused in Approvals module by %s.") % self.env.user.name)
        return res

    def action_view_linked_loans(self):
        self.ensure_one()
        loans = self.loan_ids
        action = self.env["ir.actions.actions"]._for_xml_id("loan_portal_exposure.action_hr_loan")
        if len(loans) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = loans.id
        else:
            action['domain'] = [('id', 'in', loans.ids)]
        return action

    def action_cancel(self):
        res = super().action_cancel()
        for req in self:
            for loan in req.loan_ids.filtered(lambda l: l.state in ['draft', 'waiting_farm_manager', 'waiting_gm']):
                loan.action_portal_cancel()
        return res
