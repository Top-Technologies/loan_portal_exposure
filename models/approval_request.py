# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
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

    loan_category_type = fields.Selection([
        ('none', 'Not a Loan Category'),
        ('advance_salary', 'Advance One Month Salary Loan (Short Term)'),
        ('high_amount', 'High Monetary Amount Loan (Long Term)'),
    ], string="Loan Category Type", default='none')

    employee_classification = fields.Selection([
        ('all', 'All Classifications'),
        ('head_office', 'Head Office (ዋና መ/ቤት)'),
        ('cpw', 'CPW'),
        ('farm', 'Farm (የእርሻ)'),
    ], string="Applicable Classification", default='all',
       help="Specify which employee classification this loan approval category applies to.")

    def init(self):
        super().init()
        try:
            with self.env.cr.savepoint():
                # Set manager_approval to NULL for all loan categories
                # so the employee's immediate manager is NEVER automatically injected as an approver.
                self.env.cr.execute("""
                    UPDATE approval_category
                    SET manager_approval = NULL
                    WHERE (name->>'en_US' ILIKE '%loan%' OR sequence_code ILIKE 'LOAN%' OR loan_category_type != 'none')
                      AND manager_approval IS NOT NULL;
                """)
                high_cat = self.env.ref('loan_portal_exposure.approval_category_high_amount_loan', raise_if_not_found=False)
                if high_cat and high_cat.requirer_document != 'required':
                    high_cat.sudo().write({'requirer_document': 'required'})
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

    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        related='company_id.currency_id',
        readonly=True
    )
    employee_monthly_salary = fields.Monetary(
        string="Monthly Base Salary",
        compute="_compute_loan_salary_compliance",
        currency_field="currency_id",
        store=True,
        help="Monthly base wage/salary of the employee from active contract or employee record."
    )
    loan_standard_limit = fields.Monetary(
        string="Standard 4-Month Limit",
        compute="_compute_loan_salary_compliance",
        currency_field="currency_id",
        store=True,
        help="Standard 4-month salary limit per company loan policy."
    )
    loan_standard_status = fields.Selection([
        ('on_standard', 'On Standard'),
        ('above_standard', 'Above Standard'),
        ('no_salary', 'Salary Undetermined'),
    ], string="Policy Assessment", compute="_compute_loan_salary_compliance", store=True)
    loan_standard_note = fields.Char(
        string="Policy Assessment Note",
        compute="_compute_loan_salary_compliance",
        store=True
    )
    loan_has_attachment = fields.Boolean(
        string="Has Supporting Document",
        compute="_compute_loan_has_attachment"
    )

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

    @api.depends('category_id', 'category_id.loan_category_type')
    def _compute_is_loan_category(self):
        for req in self:
            cat = req.category_id
            req.is_loan_category = bool(
                cat and (
                    cat.loan_category_type in ('advance_salary', 'high_amount') or
                    'loan' in (cat.name or '').lower() or
                    'advance' in (cat.name or '').lower() or
                    (cat.sequence_code and cat.sequence_code.startswith('LOAN'))
                )
            )

    @api.depends('category_id', 'category_id.loan_category_type')
    def _compute_loan_type(self):
        for req in self:
            cat = req.category_id
            if cat and cat.loan_category_type == 'advance_salary':
                req.loan_type = 'advance_salary'
                req.installment_months = 3
            elif cat and cat.loan_category_type == 'high_amount':
                req.loan_type = 'high_amount'
                if not req.installment_months or req.installment_months == 3:
                    req.installment_months = 12
            elif cat and ('advance' in (cat.name or '').lower() or '1-month' in (cat.name or '').lower()):
                req.loan_type = 'advance_salary'
                req.installment_months = 3
            else:
                req.loan_type = 'high_amount'
                if not req.installment_months or req.installment_months == 3:
                    req.installment_months = 12

    @api.depends('attachment_number', 'loan_ids', 'loan_ids.attachment_ids')
    def _compute_loan_has_attachment(self):
        for req in self:
            count = req.attachment_number
            if not count and req.loan_ids:
                count = sum(len(loan.attachment_ids) for loan in req.loan_ids)
            if not count and req.id:
                count = self.env['ir.attachment'].sudo().search_count([
                    ('res_model', '=', 'approval.request'),
                    ('res_id', '=', req.id)
                ])
            req.loan_has_attachment = bool(count > 0)

    @api.depends('employee_id', 'amount', 'category_id', 'loan_type', 'company_id')
    def _compute_loan_salary_compliance(self):
        for req in self:
            currency = req.currency_id or self.env.company.currency_id
            curr_symbol = currency.symbol or currency.name or ''
            if req.is_loan_category and req.employee_id:
                salary = req.employee_id.get_monthly_salary_estimate()
                req.employee_monthly_salary = salary
                standard_limit = round(salary * 4.0, 2)
                req.loan_standard_limit = standard_limit

                if salary <= 0:
                    req.loan_standard_status = 'no_salary'
                    req.loan_standard_note = _("Salary is not configured on employee contract / profile.")
                elif req.amount <= standard_limit:
                    req.loan_standard_status = 'on_standard'
                    req.loan_standard_note = _("On Standard: Requested %(amt).2f %(curr)s is within the standard 4-month limit (%(limit).2f %(curr)s).",
                                               amt=req.amount, limit=standard_limit, curr=curr_symbol)
                else:
                    diff = req.amount - standard_limit
                    req.loan_standard_status = 'above_standard'
                    req.loan_standard_note = _("Above Standard: Requested %(amt).2f %(curr)s exceeds the standard 4-month limit (%(limit).2f %(curr)s) by %(diff).2f %(curr)s.",
                                               amt=req.amount, limit=standard_limit, diff=diff, curr=curr_symbol)
            else:
                req.employee_monthly_salary = 0.0
                req.loan_standard_limit = 0.0
                req.loan_standard_status = False
                req.loan_standard_note = False

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

    @api.onchange('employee_id', 'category_id', 'request_owner_id', 'amount')
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

        self._compute_loan_salary_compliance()
        if self.is_loan_category:
            self._compute_approver_ids()

    @api.depends('category_id', 'request_owner_id', 'employee_id', 'loan_type')
    def _compute_approver_ids(self):
        super()._compute_approver_ids()
        for req in self:
            if not req.is_loan_category:
                continue

            # Ensure manager_approval is False for loan categories so immediate manager is NEVER added
            if req.category_id and req.category_id.manager_approval:
                req.category_id.sudo().write({'manager_approval': False})

            # Strictly respect the approver users configured on the Approval module category
            if req.category_id and req.category_id.approver_ids:
                cat_users = req.category_id.approver_ids.mapped('user_id').filtered(lambda u: u.active)
                if cat_users:
                    req.approver_ids = [
                        (5, 0, 0)
                    ] + [
                        (0, 0, {
                            'user_id': u.id,
                            'status': 'new',
                            'required': True,
                            'sequence': 10 * idx,
                        }) for idx, u in enumerate(cat_users, 1)
                    ]
                    continue

            # Fallback only if category has no approvers configured yet
            # NEVER fallback to employee's immediate manager (parent_id)!
            company = req.company_id or self.env.company
            fallback_user = company.loan_gm_user_id or self.env.ref('base.user_admin', raise_if_not_found=False) or self.env.user
            if fallback_user:
                req.approver_ids = [
                    (5, 0, 0),
                    (0, 0, {
                        'user_id': fallback_user.id,
                        'status': 'new',
                        'required': True,
                        'sequence': 10,
                    })
                ]

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
                emp_type = getattr(employee, 'farm_employee_type', False)
                if req.loan_type == 'advance_salary':
                    initial_state = 'waiting_hr' if emp_type in ('head_office', 'cpw', 'jimma_head_office') else 'waiting_farm_manager'
                else:
                    initial_state = 'waiting_gm'
                loan_vals['state'] = initial_state
                loan = HrLoan.create(loan_vals)

    def action_confirm(self):
        for req in self:
            if req.is_loan_category:
                # Mandatory Supporting Document Check for High Monetary Amount Loans
                if req.loan_type == 'high_amount':
                    req._compute_loan_has_attachment()
                    if not req.loan_has_attachment:
                        raise UserError(_(
                            "Supporting document is mandatory for High Monetary Amount Loan requests.\n\n"
                            "Please attach at least one document (via the 'Attach Document' button) before confirming / submitting."
                        ))

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
                        'approver_ids': [
                            (5, 0, 0),
                            (0, 0, {
                                'user_id': fallback_user.id,
                                'status': 'new',
                                'required': True,
                                'sequence': 10,
                            })
                        ]
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
                for loan in req.loan_ids.filtered(lambda l: l.state in ['draft', 'waiting_farm_manager', 'waiting_hr', 'waiting_gm']):
                    if loan.state == 'waiting_hr':
                        loan.action_portal_hr_approve()
                    elif loan.state == 'waiting_gm':
                        loan.action_portal_gm_approve()
                    else:
                        loan.action_portal_farm_manager_approve()
        return res

    def action_refuse(self, approver=None):
        res = super().action_refuse(approver=approver)
        for req in self:
            if req.request_status == 'refused':
                for loan in req.loan_ids.filtered(lambda l: l.state in ['draft', 'waiting_farm_manager', 'waiting_hr', 'waiting_gm']):
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
            for loan in req.loan_ids.filtered(lambda l: l.state in ['draft', 'waiting_farm_manager', 'waiting_hr', 'waiting_gm']):
                loan.action_portal_cancel()
        return res
