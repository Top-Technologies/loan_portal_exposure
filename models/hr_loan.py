# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


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
        ('waiting_gm', 'Waiting GM Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('paid', 'Fully Repaid'),
    ], string="Status", default='draft', store=True, copy=False)

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

    @api.constrains('loan_type', 'loan_amount', 'installment_months', 'employee_id')
    def _check_loan_rules(self):
        for loan in self:
            if not loan.employee_id:
                continue
            monthly_salary = loan.employee_id.get_monthly_salary_estimate()
            if loan.loan_type == 'advance_salary':
                if loan.installment_months != 3:
                    loan.installment_months = 3
            elif loan.loan_type == 'high_amount':
                if loan.installment_months not in (6, 12):
                    raise ValidationError(_("Repayment duration for High Monetary Amount Loan must be either 6 months or 12 months."))
                if monthly_salary > 0:
                    max_allowed_loan = round(4 * monthly_salary, 2)
                    if loan.loan_amount > max_allowed_loan:
                        raise ValidationError(_(
                            "The requested loan amount (%(amount)s %(curr)s) exceeds the maximum allowed limit of 4 times the monthly salary (Max: %(max_amt)s %(curr)s).",
                            amount=loan.loan_amount,
                            max_amt=max_allowed_loan,
                            curr=loan.currency_id.symbol or ''
                        ))
                    max_monthly_deduction = round(monthly_salary / 3.0, 2)
                    installment = round(loan.loan_amount / loan.installment_months, 2)
                    if installment > (max_monthly_deduction + 0.01):
                        raise ValidationError(_(
                            "The monthly installment (%(installment)s %(curr)s/month) exceeds the maximum allowed limit of 1/3 of the monthly salary (Max deduction: %(max_ded)s %(curr)s/month). Please choose 12 months duration or reduce the loan amount.",
                            installment=installment,
                            max_ded=max_monthly_deduction,
                            curr=loan.currency_id.symbol or ''
                        ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.loan') or _('New')
            if vals.get('loan_type') == 'advance_salary':
                vals['installment_months'] = 3
                if not vals.get('loan_amount') and vals.get('employee_id'):
                    emp = self.env['hr.employee'].browse(vals['employee_id'])
                    wage = emp.get_monthly_salary_estimate()
                    if wage > 0:
                        vals['loan_amount'] = wage
        return super().create(vals_list)

    def action_submit(self):
        """ Submits the loan and routes to the appropriate approver """
        for loan in self:
            if loan.loan_type == 'advance_salary':
                loan.write({'state': 'waiting_farm_manager'})
                # Create Approval Request in backend Approvals module if category exists
                loan._create_approval_request_record()
                # Notify Farm Manager
                loan._notify_farm_manager()
            else:
                loan.write({'state': 'waiting_gm'})
                # Create Approval Request in backend Approvals module for GM
                loan._create_approval_request_record()
                # Notify General Manager
                loan._notify_gm()

            loan._send_mail_safe('loan_portal_exposure.email_template_loan_submitted_employee')
        return True

    def _create_approval_request_record(self):
        """ Creates a matching approval.request record in the Odoo Approvals module """
        self.ensure_one()
        ApprovalRequest = self.env['approval.request'].sudo()
        category = False

        if self.loan_type == 'advance_salary':
            category = self.company_id.loan_advance_category_id or self.env.ref('loan_portal_exposure.approval_category_advance_salary_loan', raise_if_not_found=False)
        else:
            category = self.company_id.loan_high_amount_category_id or self.env.ref('loan_portal_exposure.approval_category_high_amount_loan', raise_if_not_found=False)

        if not category:
            category = self.env['approval.category'].sudo().search([('name', 'ilike', 'loan')], limit=1)

        if category:
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

            # Ensure specific approver is added
            if self.loan_type == 'advance_salary' and self.farm_manager_id and self.farm_manager_id.user_id:
                app_req.approver_ids = [(0, 0, {
                    'user_id': self.farm_manager_id.user_id.id,
                    'status': 'pending',
                    'required': True,
                })]
            elif self.loan_type == 'high_amount':
                gm_user = self.company_id.loan_gm_user_id or self.env.ref('base.user_admin', raise_if_not_found=False)
                if gm_user:
                    app_req.approver_ids = [(0, 0, {
                        'user_id': gm_user.id,
                        'status': 'pending',
                        'required': True,
                    })]

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
        """ Executed by Farm Manager to approve advance salary loans """
        for loan in self:
            if loan.state != 'waiting_farm_manager':
                raise UserError(_("This loan is not pending Farm Manager approval."))

            loan.sudo().write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })

            # Sync linked approval request
            if loan.approval_request_id:
                try:
                    loan.approval_request_id.sudo().action_approve()
                except Exception:
                    pass

            # Log clean chatter note
            loan.sudo().message_post(
                body=_("Approved by Farm Manager: %s on %s.") % (
                    self.env.user.name,
                    fields.Datetime.to_string(fields.Datetime.now())
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

            # Notify employee
            loan._send_mail_safe('loan_portal_exposure.email_template_loan_approved_employee')

        return True

    def action_portal_gm_approve(self):
        """ Executed by GM to approve High Monetary Amount Loans """
        for loan in self:
            if loan.state != 'waiting_gm':
                raise UserError(_("This loan is not pending GM approval."))

            loan.sudo().write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })

            # Sync linked approval request
            if loan.approval_request_id:
                try:
                    loan.approval_request_id.sudo().action_approve()
                except Exception:
                    pass

            # Log clean chatter note
            loan.sudo().message_post(
                body=_("Approved by General Manager (GM): %s on %s.") % (
                    self.env.user.name,
                    fields.Datetime.to_string(fields.Datetime.now())
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

            # Send automated confirmation email to HR Manager and Finance Manager
            loan._notify_hr_and_finance_managers()

            # Notify employee
            loan._send_mail_safe('loan_portal_exposure.email_template_loan_approved_employee')

        return True

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
            if loan.state not in ['draft', 'waiting_farm_manager', 'waiting_gm']:
                raise UserError(_("You can only cancel pending loan requests."))

            loan.sudo().write({'state': 'cancelled'})

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

    def _notify_farm_manager(self):
        """ Dispatches notification email to the Farm Manager """
        for loan in self:
            manager = loan.farm_manager_id.user_id if loan.farm_manager_id else False
            if manager:
                loan._send_mail_safe('loan_portal_exposure.email_template_loan_submitted_farm_manager')

    def _notify_gm(self):
        """ Dispatches notification email to the General Manager """
        for loan in self:
            gm_user = loan.company_id.loan_gm_user_id
            if gm_user:
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
