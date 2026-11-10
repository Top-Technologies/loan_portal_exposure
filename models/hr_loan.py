# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .ethiopian_date_utils import (
    format_ethiopian_date,
    gregorian_to_ethiopian,
    ethiopian_to_gregorian,
    ETHIOPIAN_MONTHS_AMHARIC,
    get_ethiopian_days_in_month,
)

ETHIOPIAN_MONTH_SELECTION = [
    (str(i), f"{i} - {ETHIOPIAN_MONTHS_AMHARIC[i]}") for i in range(1, 14)
]


class HrLoan(models.Model):
    _name = 'hr.loan'
    _description = 'Employee Loan Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string="Loan Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        required=True,
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        related='company_id.currency_id'
    )
    loan_type = fields.Selection([
        ('advance_salary', 'Advance One Month Salary Loan'),
        ('high_amount', 'High Monetary Amount Loan'),
    ], string="Loan Category", required=True, default='advance_salary', tracking=True)

    loan_amount = fields.Monetary(
        string="Requested Amount",
        required=True,
        currency_field='currency_id',
        tracking=True
    )
    payment_date = fields.Date(
        string="Disbursement / Start Date",
        default=fields.Date.today,
        required=True
    )
    ethiopian_payment_date = fields.Char(
        string="Ethiopian Disbursement Date",
        compute="_compute_ethiopian_payment_date",
        store=True,
        help="Preferred disbursement date expressed in the Ethiopian calendar"
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
    installment_months = fields.Integer(
        string="Repayment Duration (Months)",
        default=1,
        required=True
    )
    installment_amount = fields.Monetary(
        string="Monthly Installment",
        compute="_compute_installment_amount",
        store=True,
        currency_field='currency_id'
    )
    reason = fields.Text(
        string="Reason / Purpose",
        required=True
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'hr_loan_ir_attachments_rel',
        'loan_id',
        'attachment_id',
        string="Attachments / Documents"
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_farm_manager', 'Waiting Farm Manager Approval'),
        ('waiting_hr', 'Waiting HR Approval'),
        ('waiting_gm', 'Waiting GM Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('paid', 'Fully Repaid'),
    ], string="Status", default='draft', store=True, copy=False)

    designated_approver_user_id = fields.Many2one(
        'res.users',
        string="Designated Approver",
        compute="_compute_designated_approver_user",
        store=True,
        help="The specific manager/officer responsible for reviewing this loan application."
    )

    farm_id = fields.Many2one(
        'farm.farm',
        string="Assigned Farm",
        compute="_compute_farm_info",
        store=True
    )
    farm_manager_id = fields.Many2one(
        'hr.employee',
        string="Farm Manager",
        compute="_compute_farm_info",
        store=True
    )
    approval_request_id = fields.Many2one(
        'approval.request',
        string="Approvals Module Request",
        copy=False,
        readonly=True
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string="Approved By",
        copy=False,
        readonly=True
    )
    approval_date = fields.Datetime(
        string="Approval Date",
        copy=False,
        readonly=True
    )
    rejection_reason = fields.Text(
        string="Rejection Reason",
        copy=False
    )
    is_portal_submitted = fields.Boolean(
        string="Submitted via Portal",
        default=False,
        copy=False
    )
    salary_attachment_id = fields.Many2one(
        'hr.salary.attachment',
        string="Linked Salary Attachment",
        copy=False,
        readonly=True
    )

    @api.depends('payment_date')
    def _compute_ethiopian_payment_date(self):
        for loan in self:
            if loan.payment_date:
                loan.ethiopian_payment_date = format_ethiopian_date(loan.payment_date, lang='am')
                ey, em, ed = gregorian_to_ethiopian(loan.payment_date)
                loan.eth_year_loan = ey
                loan.eth_month_loan = str(em)
                loan.eth_day_loan = ed
            else:
                loan.ethiopian_payment_date = ''

    @api.onchange('payment_date')
    def _onchange_payment_date(self):
        if self.payment_date:
            ey, em, ed = gregorian_to_ethiopian(self.payment_date)
            self.eth_year_loan = ey
            self.eth_month_loan = str(em)
            self.eth_day_loan = ed
            self.ethiopian_payment_date = format_ethiopian_date(self.payment_date, lang='am')

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
                self.ethiopian_payment_date = format_ethiopian_date(g_date, lang='am')
            except Exception:
                pass

    @api.depends('loan_amount', 'installment_months')
    def _compute_installment_amount(self):
        for loan in self:
            months = loan.installment_months if loan.installment_months > 0 else 1
            loan.installment_amount = round(loan.loan_amount / months, 2)

    @api.depends('employee_id')
    def _compute_farm_info(self):
        for loan in self:
            if loan.employee_id:
                farm = getattr(loan.employee_id, 'current_farm_id', False) or getattr(loan.employee_id, 'initial_farm_id', False)
                loan.farm_id = farm.id if farm else False
                loan.farm_manager_id = loan.employee_id.get_assigned_farm_manager().id if loan.employee_id else False
            else:
                loan.farm_id = False
                loan.farm_manager_id = False

    @api.constrains('loan_amount', 'installment_months')
    def _check_loan_rules(self):
        for loan in self:
            if loan.loan_amount <= 0:
                raise ValidationError(_("Loan amount must be greater than zero."))
            if loan.installment_months < 1:
                raise ValidationError(_("Repayment duration must be at least 1 month."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.loan') or _('New')
            if vals.get('loan_type') == 'advance_salary' and not vals.get('installment_months'):
                vals['installment_months'] = 3
                if not vals.get('loan_amount') and vals.get('employee_id'):
                    emp = self.env['hr.employee'].browse(vals['employee_id'])
                    wage = emp.get_monthly_salary_estimate()
                    if wage > 0:
                        vals['loan_amount'] = wage
        return super().create(vals_list)

    @api.model
    def _get_loan_approval_category_for_employee(self, loan_type, employee):
        """
        Finds the designated approval.category based on loan_type and employee classification:
        - loan_type: 'advance_salary' (Short Term) or 'high_amount' (Long Term / High Monetary)
        - employee: hr.employee record (classification: head_office, cpw, farm)
        """
        emp_type = getattr(employee, 'farm_employee_type', False) if employee else False
        if emp_type in ('head_office', 'jimma_head_office'):
            classification = 'head_office'
        elif emp_type == 'cpw':
            classification = 'cpw'
        elif emp_type in ('permanent', 'temporary', 'zemach'):
            classification = 'farm'
        else:
            classification = 'all'

        ApprovalCategory = self.env['approval.category'].sudo()

        # 1. Match category by explicit fields: loan_category_type and employee_classification
        if classification != 'all':
            cat = ApprovalCategory.search([
                ('loan_category_type', '=', loan_type),
                ('employee_classification', '=', classification),
                ('active', '=', True)
            ], limit=1)
            if cat:
                return cat

        # 2. Match by XML ID mapping if defined
        xml_map = {
            ('advance_salary', 'head_office'): 'loan_portal_exposure.approval_category_advance_salary_head_office',
            ('advance_salary', 'cpw'): 'loan_portal_exposure.approval_category_advance_salary_cpw',
            ('advance_salary', 'farm'): 'loan_portal_exposure.approval_category_advance_salary_farm',
            ('high_amount', 'head_office'): 'loan_portal_exposure.approval_category_high_amount_head_office',
            ('high_amount', 'cpw'): 'loan_portal_exposure.approval_category_high_amount_cpw',
            ('high_amount', 'farm'): 'loan_portal_exposure.approval_category_high_amount_farm',
        }
        ref_xml_id = xml_map.get((loan_type, classification))
        if ref_xml_id:
            cat = self.env.ref(ref_xml_id, raise_if_not_found=False)
            if cat and cat.active:
                return cat

        # 3. Match by name keywords
        kw_map = {'head_office': 'Head Office', 'cpw': 'CPW', 'farm': 'Farm'}
        kw = kw_map.get(classification)
        if kw:
            type_kw = 'Advance' if loan_type == 'advance_salary' else 'High'
            cat = ApprovalCategory.search([
                ('name', 'ilike', type_kw),
                ('name', 'ilike', kw),
                ('active', '=', True)
            ], limit=1)
            if cat:
                return cat

        # 4. Fallback to general category for loan_type
        cat = ApprovalCategory.search([
            ('loan_category_type', '=', loan_type),
            ('employee_classification', '=', 'all'),
            ('active', '=', True)
        ], limit=1)
        if cat:
            return cat

        # 5. Default XML IDs
        default_xml = 'loan_portal_exposure.approval_category_advance_salary_loan' if loan_type == 'advance_salary' else 'loan_portal_exposure.approval_category_high_amount_loan'
        return self.env.ref(default_xml, raise_if_not_found=False)

    def _get_loan_designated_approvers(self):
        """
        Determines the designated approver users from the Approval Category configured
        in the Approval module for this loan's type and employee classification.
        """
        self.ensure_one()
        category = self.approval_request_id.category_id if self.approval_request_id else False
        if not category:
            category = self._get_loan_approval_category_for_employee(self.loan_type, self.employee_id)

        if category and category.approver_ids:
            active_users = category.approver_ids.mapped('user_id').filtered(lambda u: u.active)
            if active_users:
                return active_users

        # Fallback if no approver configured on the approval category
        # NEVER use immediate manager (parent_id)!
        company = self.company_id or self.env.company
        fallback = company.loan_gm_user_id or self.env.ref('base.user_admin', raise_if_not_found=False)
        return fallback or self.env['res.users']

    def _get_loan_designated_approver_user(self):
        approvers = self._get_loan_designated_approvers()
        return approvers[0] if approvers else False

    @api.depends('employee_id', 'loan_type', 'company_id', 'farm_id', 'farm_manager_id')
    def _compute_designated_approver_user(self):
        for loan in self:
            loan.designated_approver_user_id = loan._get_loan_designated_approver_user()

    def action_submit(self):
        """ Submits the loan and routes to the appropriate approver """
        for loan in self:
            if loan.loan_type == 'high_amount' and not loan.attachment_ids:
                raise ValidationError(_(
                    "Supporting document is mandatory for High Monetary Amount Loan requests.\n\n"
                    "Please attach at least one supporting document before submitting."
                ))

            emp = loan.employee_id
            emp_type = getattr(emp, 'farm_employee_type', False) if emp else False

            if loan.loan_type == 'advance_salary':
                if emp_type in ('head_office', 'cpw', 'jimma_head_office'):
                    loan.write({'state': 'waiting_hr'})
                else:
                    loan.write({'state': 'waiting_farm_manager'})
            else:
                # High Monetary Amount always routes to GM / rule approver regardless of employee type
                loan.write({'state': 'waiting_gm'})

            # Create Approval Request in backend Approvals module if category exists
            loan._create_approval_request_record()

            # Set designated approver from approval category
            loan.designated_approver_user_id = loan._get_loan_designated_approver_user()

            # Notify designated approver and employee
            loan._notify_designated_approver()
            loan._send_mail_safe('loan_portal_exposure.email_template_loan_submitted_employee')
        return True

    def _create_approval_request_record(self):
        """ Creates a matching approval.request record in the Odoo Approvals module """
        self.ensure_one()
        ApprovalRequest = self.env['approval.request'].sudo()
        category = self._get_loan_approval_category_for_employee(self.loan_type, self.employee_id)

        if not category:
            category = self.env['approval.category'].sudo().search([('name', 'ilike', 'loan')], limit=1)

        if category:
            if category.manager_approval:
                category.sudo().write({'manager_approval': False})

            owner_user = self.employee_id.user_id or self.env.user
            req_vals = {
                'name': f"{self.name} - {self.employee_id.name} ({dict(self._fields['loan_type'].selection).get(self.loan_type)})",
                'category_id': category.id,
                'request_owner_id': owner_user.id,
                'amount': self.loan_amount,
                'reference': self.name,
                'date': fields.Datetime.now(),
                'date_confirmed': fields.Datetime.now(),
            }
            app_req = ApprovalRequest.create(req_vals)
            self.approval_request_id = app_req.id

            # Sync attachments to approval request
            if self.attachment_ids:
                for att in self.attachment_ids:
                    att.copy({'res_model': 'approval.request', 'res_id': app_req.id})

            # Populate approvers strictly from the category approvers
            approver_users = category.approver_ids.mapped('user_id').filtered(lambda u: u.active)
            if approver_users:
                app_req.approver_ids = [
                    (5, 0, 0)
                ] + [
                    (0, 0, {
                        'user_id': u.id,
                        'status': 'pending',
                        'required': True,
                        'sequence': 10 * idx,
                    }) for idx, u in enumerate(approver_users, 1)
                ]
            else:
                fallback_user = self._get_loan_designated_approver_user()
                if fallback_user:
                    app_req.approver_ids = [
                        (5, 0, 0),
                        (0, 0, {
                            'user_id': fallback_user.id,
                            'status': 'pending',
                            'required': True,
                            'sequence': 10,
                        })
                    ]

            # Post clean reference message without HTML tags or repayment
            app_req.message_post(
                body=_("Loan Application: Reference %s for %s. Amount: %s %s. Reason: %s") % (
                    self.name,
                    self.employee_id.name,
                    self.loan_amount,
                    self.currency_id.symbol or '',
                    self.reason
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

    def action_portal_farm_manager_approve(self):
        """ Executed by Farm Manager to approve farm loans """
        return self._do_approve_loan(approver_role="Farm Manager")

    def action_portal_hr_approve(self):
        """ Executed by HR Officer to approve Head Office / CPW advance salary loans """
        return self._do_approve_loan(approver_role="HR Officer")

    def action_portal_gm_approve(self):
        """ Executed by GM to approve High Monetary Amount Loans """
        return self._do_approve_loan(approver_role="General Manager (GM)")

    def _do_approve_loan(self, approver_role="Approver"):
        for loan in self:
            if loan.state not in ('waiting_farm_manager', 'waiting_hr', 'waiting_gm'):
                raise UserError(_("This loan is not pending approval."))

            loan.sudo().write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })

            # Auto create & sync open Salary Attachment and contract deduction
            loan._create_or_sync_salary_attachment()

            # Sync linked approval request
            if loan.approval_request_id:
                try:
                    loan.approval_request_id.sudo().action_approve()
                except Exception:
                    pass

            # Log clean chatter note
            loan.sudo().message_post(
                body=_("Approved by %s: %s on %s.") % (
                    approver_role,
                    self.env.user.name,
                    fields.Datetime.to_string(fields.Datetime.now())
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

            # Send automated confirmation email to HR Manager and Finance Manager for GM approved loans
            if loan.loan_type == 'high_amount' and loan.approved_by_id == loan.company_id.loan_gm_user_id:
                loan._notify_hr_and_finance_managers()

            # Notify employee
            loan._send_mail_safe('loan_portal_exposure.email_template_loan_approved_employee')

        return True

    def _create_or_sync_salary_attachment(self):
        """ Automatically creates/syncs an open salary attachment for approved loans and populates contract deductions """
        SalaryAttachment = self.env['hr.salary.attachment'].sudo()
        input_type = self.env.ref('hr_payroll.input_attachment_salary', raise_if_not_found=False)
        if not input_type:
            input_type = self.env['hr.payslip.input.type'].search([('code', 'in', ('ATTACH_SALARY', 'DEDUCTION'))], limit=1)

        for loan in self:
            if not loan.employee_id or loan.loan_amount <= 0:
                continue

            # Link to Category 2 Loan/Advance deduction on contract
            ded_type = 'long_term_loan' if loan.loan_type == 'high_amount' else 'advance'

            vals = {
                'employee_ids': [(6, 0, [loan.employee_id.id])],
                'other_input_type_id': input_type.id if input_type else False,
                'description': f"Approved Loan: {loan.name} - {loan.reason or dict(loan._fields['loan_type'].selection).get(loan.loan_type, '')}",
                'loan_deduction_type': ded_type,
                'has_total_amount': True,
                'total_amount': loan.loan_amount,
                'monthly_amount': loan.installment_amount,
                'date_start': loan.payment_date or fields.Date.today(),
                'no_end_date': False,
                'state': 'open',
                'company_id': loan.company_id.id,
            }

            if loan.salary_attachment_id:
                loan.salary_attachment_id.sudo().write(vals)
            else:
                att = SalaryAttachment.create(vals)
                loan.sudo().write({'salary_attachment_id': att.id})

    def action_view_salary_attachment(self):
        """ Opens the linked salary attachment form view """
        self.ensure_one()
        if not self.salary_attachment_id:
            raise UserError(_("No salary attachment is linked to this loan yet."))
        return {
            'name': _('Salary Attachment'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.salary.attachment',
            'view_mode': 'form',
            'res_id': self.salary_attachment_id.id,
        }

    def action_portal_reject(self, reason=""):
        """ Executed by Farm Manager or GM to reject loan """
        for loan in self:
            if loan.state in ['approved', 'rejected', 'cancelled', 'paid']:
                raise UserError(_("This loan cannot be rejected in its current status."))

            clean_reason = (reason or "").strip() or _("No reason provided.")
            loan.sudo().write({
                'state': 'rejected',
                'rejection_reason': clean_reason,
            })

            # Cancel linked salary attachment if any
            if loan.salary_attachment_id:
                loan.salary_attachment_id.sudo().write({'state': 'cancel'})

            # Sync linked approval request
            if loan.approval_request_id:
                try:
                    loan.approval_request_id.sudo().action_refuse()
                except Exception:
                    pass

            # Log clean chatter note
            loan.sudo().message_post(
                body=_("Rejected by %s. Reason: %s") % (
                    self.env.user.name,
                    clean_reason
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

            # Notify employee
            loan._send_mail_safe('loan_portal_exposure.email_template_loan_rejected_employee')

        return True

    def action_portal_cancel(self):
        """ Executed by employee to cancel pending request """
        for loan in self:
            if loan.state not in ['draft', 'waiting_farm_manager', 'waiting_hr', 'waiting_gm']:
                raise UserError(_("You can only cancel pending loan requests."))

            loan.sudo().write({'state': 'cancelled'})

            # Cancel linked salary attachment if any
            if loan.salary_attachment_id:
                loan.salary_attachment_id.sudo().write({'state': 'cancel'})

            if loan.approval_request_id:
                try:
                    loan.approval_request_id.sudo().action_cancel()
                except Exception:
                    pass

            loan.sudo().message_post(
                body=_("Cancelled by Employee: %s.") % self.env.user.name,
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

        return True

    def _notify_designated_approver(self):
        """ Dispatches notification email based on pending approval state """
        for loan in self:
            if loan.state == 'waiting_farm_manager':
                loan._notify_farm_manager()
            elif loan.state == 'waiting_gm':
                loan._notify_gm()
            elif loan.state == 'waiting_hr':
                loan._notify_hr()

    def _notify_hr(self):
        """ Dispatches notification email to the designated HR Officer """
        for loan in self:
            hr_user = loan.designated_approver_user_id
            if hr_user:
                loan._send_mail_safe('loan_portal_exposure.email_template_loan_submitted_hr')

    def _notify_farm_manager(self):
        """ Dispatches notification email to the Farm Manager """
        for loan in self:
            manager = loan.farm_manager_id.user_id if loan.farm_manager_id else False
            if manager:
                loan._send_mail_safe('loan_portal_exposure.email_template_loan_submitted_farm_manager')

    def _notify_gm(self):
        """ Dispatches notification email to the General Manager or designated rule approver """
        for loan in self:
            approver_user = loan.designated_approver_user_id or loan.company_id.loan_gm_user_id
            if approver_user:
                loan._send_mail_safe('loan_portal_exposure.email_template_loan_submitted_gm')

    def _notify_hr_and_finance_managers(self):
        """ Dispatches email to HR Manager and Finance Manager upon GM loan approval """
        for loan in self:
            loan._send_mail_safe('loan_portal_exposure.email_template_loan_gm_approved_hr_finance')

    def _send_mail_safe(self, template_xml_id):
        """ Safely sends email template without polluting document chatter """
        template = self.env.ref(template_xml_id, raise_if_not_found=False)
        if template:
            try:
                template.sudo().send_mail(
                    self.id,
                    force_send=True,
                    email_values={'model': False, 'res_id': False, 'auto_delete': True}
                )
            except Exception:
                pass
