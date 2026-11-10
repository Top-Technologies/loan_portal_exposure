# -*- coding: utf-8 -*-
import base64
from datetime import datetime, date
from werkzeug.exceptions import Forbidden, NotFound

from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression
from ..models.ethiopian_date_utils import ethiopian_to_gregorian, format_ethiopian_date


class LoanCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        user = request.env.user
        employee = self._get_current_employee()

        if employee:
            values['loans_count'] = request.env['hr.loan'].sudo().search_count([
                ('employee_id', '=', employee.id)
            ])
        else:
            values['loans_count'] = 0

        # Approvals counter for Farm Managers and GM
        to_approve_domain = self._get_to_approve_domain(user, employee)
        if to_approve_domain:
            values['loans_to_approve_count'] = request.env['hr.loan'].sudo().search_count(to_approve_domain)
        else:
            values['loans_to_approve_count'] = 0

        return values

    def _get_current_employee(self):
        """ Helper to retrieve the current user's linked employee """
        return request.env.user.get_portal_employee() if hasattr(request.env.user, 'get_portal_employee') else request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)

    def _get_to_approve_domain(self, user, employee):
        """ Builds domain for loans waiting for user's approval based on Approval module approvers """
        is_admin = user.has_group('base.group_system')
        if is_admin:
            return [('state', 'in', ('waiting_hr', 'waiting_farm_manager', 'waiting_gm'))]

        # Match loans where user is the designated approver or configured as an approver on the Approval module category
        return [
            ('state', 'in', ('waiting_hr', 'waiting_farm_manager', 'waiting_gm')),
            '|', '|',
            ('designated_approver_user_id', '=', user.id),
            ('approval_request_id.approver_ids.user_id', '=', user.id),
            ('approval_request_id.category_id.approver_ids.user_id', '=', user.id)
        ]

    def _check_loan_access(self, loan_id, mode='read'):
        """ Security verification verifying access rights on loan record """
        user = request.env.user
        employee = self._get_current_employee()
        loan = request.env['hr.loan'].sudo().browse(loan_id)

        if not loan.exists():
            raise NotFound()

        # System admins & HR officers have full access
        if user.has_group('hr.group_hr_user') or user.has_group('base.group_system'):
            return loan

        is_owner = employee and loan.employee_id.id == employee.id
        is_admin = user.has_group('base.group_system')

        # Check if user is an assigned approver from the Approval module
        is_rule_approver = bool(
            loan.approval_request_id and (
                user.id in loan.approval_request_id.approver_ids.mapped('user_id.id') or
                user.id in loan.approval_request_id.category_id.approver_ids.mapped('user_id.id')
            )
        )
        is_designated_approver = (loan.designated_approver_user_id.id == user.id) or is_rule_approver or is_admin

        if mode == 'read':
            if not (is_owner or is_designated_approver):
                raise Forbidden(_("You do not have permission to view this loan request."))
        elif mode == 'approve':
            if loan.state not in ('waiting_hr', 'waiting_farm_manager', 'waiting_gm'):
                raise Forbidden(_("This loan is not pending approval."))
            if not is_designated_approver:
                raise Forbidden(_("Only the designated approver assigned on the Approval module can approve this loan."))
        elif mode == 'cancel':
            if not is_owner:
                raise Forbidden(_("You can only cancel your own loan requests."))

        return loan

    # -------------------------------------------------------------------------
    # My Loans Dashboard & History
    # -------------------------------------------------------------------------

    @http.route(['/my/loans', '/my/loans/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_loans(self, page=1, sortby=None, filterby=None, **kw):
        employee = self._get_current_employee()
        if not employee:
            return request.render('time_off_portal_exposure.portal_no_employee_linked', {
                'page_name': 'loan_no_employee'
            })

        Loan = request.env['hr.loan'].sudo()

        sortings = {
            'date_desc': {'label': _('Date (Newest)'), 'order': 'id desc'},
            'date_asc': {'label': _('Date (Oldest)'), 'order': 'id asc'},
            'amount_desc': {'label': _('Amount (Highest)'), 'order': 'loan_amount desc'},
            'amount_asc': {'label': _('Amount (Lowest)'), 'order': 'loan_amount asc'},
        }
        if not sortby or sortby not in sortings:
            sortby = 'date_desc'
        order = sortings[sortby]['order']

        filters = {
            'all': {'label': _('All Loans'), 'domain': []},
            'pending': {'label': _('Pending Approval'), 'domain': [('state', 'in', ['waiting_farm_manager', 'waiting_gm'])]},
            'approved': {'label': _('Approved'), 'domain': [('state', '=', 'approved')]},
            'rejected': {'label': _('Rejected'), 'domain': [('state', '=', 'rejected')]},
            'cancelled': {'label': _('Cancelled'), 'domain': [('state', '=', 'cancelled')]},
        }
        if not filterby or filterby not in filters:
            filterby = 'all'

        base_domain = [('employee_id', '=', employee.id)]
        domain = expression.AND([base_domain, filters[filterby]['domain']])

        total_loans = Loan.search_count(domain)
        pager = portal_pager(
            url="/my/loans",
            url_args={'sortby': sortby, 'filterby': filterby},
            total=total_loans,
            page=page,
            step=10
        )

        loans = Loan.search(domain, order=order, limit=10, offset=pager['offset'])

        # Metrics
        all_emp_loans = Loan.search([('employee_id', '=', employee.id)])
        active_loans = all_emp_loans.filtered(lambda l: l.state == 'approved')
        total_active_amount = sum(active_loans.mapped('loan_amount'))
        pending_count = len(all_emp_loans.filtered(lambda l: l.state in ['waiting_farm_manager', 'waiting_gm']))

        # Can user approve any loans?
        to_approve_domain = self._get_to_approve_domain(request.env.user, employee)
        can_approve = bool(to_approve_domain)

        values = {
            'page_name': 'loan_dashboard',
            'employee': employee,
            'loans': loans,
            'active_loans_count': len(active_loans),
            'total_active_amount': total_active_amount,
            'pending_count': pending_count,
            'can_approve': can_approve,
            'pager': pager,
            'sortby': sortby,
            'sortings': sortings,
            'filterby': filterby,
            'filters': filters,
            'default_url': '/my/loans',
            'currency': employee.company_id.currency_id,
        }
        return request.render('loan_portal_exposure.portal_my_loans_dashboard', values)

    # -------------------------------------------------------------------------
    # Apply for a New Loan
    # -------------------------------------------------------------------------

    @http.route(['/my/loans/new'], type='http', auth='user', methods=['GET', 'POST'], website=True, csrf=True)
    def portal_my_loans_new(self, **post):
        employee = self._get_current_employee()
        if not employee:
            return request.render('time_off_portal_exposure.portal_no_employee_linked', {
                'page_name': 'loan_no_employee'
            })

        errors = []
        monthly_salary = employee.get_monthly_salary_estimate()
        max_loan_amount = round(4 * monthly_salary, 2)
        max_monthly_installment = round(monthly_salary / 3.0, 2)
        advance_installment = round(monthly_salary / 3.0, 2) if monthly_salary > 0 else 0.0
        farm_manager = employee.get_assigned_farm_manager()
        gm_user = request.env.company.loan_gm_user_id
        currency = employee.company_id.currency_id

        if request.httprequest.method == 'POST':
            loan_type = post.get('loan_type', 'advance_salary')
            payment_date_str = post.get('payment_date')
            reason = post.get('reason', '').strip()
            attachment = request.httprequest.files.get('attachment')

            # Ethiopian date conversion fallback if Gregorian date input was empty
            if not payment_date_str and post.get('eth_year_loan') and post.get('eth_month_loan') and post.get('eth_day_loan'):
                try:
                    g_dt = ethiopian_to_gregorian(post['eth_year_loan'], post['eth_month_loan'], post['eth_day_loan'])
                    payment_date_str = g_dt.strftime('%Y-%m-%d')
                except Exception:
                    pass

            if loan_type == 'advance_salary':
                loan_amount = monthly_salary if monthly_salary > 0 else 0.0
                installment_months = 3
            else:
                loan_amount_str = post.get('loan_amount', '0').strip()
                try:
                    loan_amount = float(loan_amount_str)
                    if loan_amount <= 0:
                        errors.append(_("Loan amount must be greater than zero."))
                except ValueError:
                    errors.append(_("Please enter a valid numeric loan amount."))
                    loan_amount = 0.0

                try:
                    installment_months = int(post.get('installment_months', '6'))
                    if installment_months < 1:
                        installment_months = 1
                except (ValueError, TypeError):
                    installment_months = 6

            if not reason:
                errors.append(_("Please provide a reason or purpose for the loan request."))

            if loan_type == 'high_amount' and not (attachment and getattr(attachment, 'filename', False)):
                errors.append(_("Supporting document is mandatory for High Monetary Amount Loan requests. Please upload a supporting document."))

            if not errors:
                try:
                    loan_vals = {
                        'employee_id': employee.id,
                        'company_id': employee.company_id.id,
                        'loan_type': loan_type,
                        'loan_amount': loan_amount,
                        'payment_date': payment_date_str or fields.Date.today(),
                        'installment_months': installment_months,
                        'reason': reason,
                        'is_portal_submitted': True,
                    }

                    loan = request.env['hr.loan'].sudo().create(loan_vals)

                    # Handle file attachment
                    if attachment and attachment.filename:
                        file_content = attachment.read()
                        attachment_record = request.env['ir.attachment'].sudo().create({
                            'name': attachment.filename,
                            'datas': base64.b64encode(file_content),
                            'res_model': 'hr.loan',
                            'res_id': loan.id,
                            'type': 'binary',
                        })
                        loan.sudo().write({'attachment_ids': [(4, attachment_record.id)]})

                    # Submit loan into workflow
                    loan.sudo().action_submit()

                    return request.redirect(f'/my/loans/{loan.id}?submitted=1')

                except Exception as e:
                    errors.append(str(e))

        adv_cat = request.env['hr.loan'].sudo()._get_loan_approval_category_for_employee('advance_salary', employee)
        high_cat = request.env['hr.loan'].sudo()._get_loan_approval_category_for_employee('high_amount', employee)

        adv_approvers = adv_cat.approver_ids.mapped('user_id.name') if adv_cat else []
        high_approvers = high_cat.approver_ids.mapped('user_id.name') if high_cat else []

        adv_approver_name = ", ".join(adv_approvers) if adv_approvers else "Designated Short Term Approver"
        high_approver_name = ", ".join(high_approvers) if high_approvers else "Designated Long Term Approver"

        values = {
            'page_name': 'loan_new',
            'employee': employee,
            'monthly_salary': monthly_salary,
            'max_loan_amount': max_loan_amount,
            'max_monthly_installment': max_monthly_installment,
            'advance_installment': advance_installment,
            'farm_manager': farm_manager,
            'gm_user': gm_user,
            'adv_approver_name': adv_approver_name,
            'high_approver_name': high_approver_name,
            'errors': errors,
            'post': post,
            'today': fields.Date.today(),
            'currency': currency,
        }
        return request.render('loan_portal_exposure.portal_my_loans_new', values)

    # -------------------------------------------------------------------------
    # Loan Details View & Chatter
    # -------------------------------------------------------------------------

    @http.route(['/my/loans/<int:loan_id>'], type='http', auth='user', website=True)
    def portal_my_loan_detail(self, loan_id, submitted=None, **kw):
        loan = self._check_loan_access(loan_id, mode='read')
        employee = self._get_current_employee()

        user = request.env.user
        is_owner = employee and loan.employee_id.id == employee.id
        is_admin = user.has_group('base.group_system')
        is_rule_approver = bool(
            loan.approval_request_id and (
                user.id in loan.approval_request_id.approver_ids.mapped('user_id.id') or
                user.id in loan.approval_request_id.category_id.approver_ids.mapped('user_id.id')
            )
        )
        is_designated_approver = (loan.designated_approver_user_id.id == user.id) or is_rule_approver or is_admin

        can_approve = False
        if loan.state in ('waiting_hr', 'waiting_farm_manager', 'waiting_gm'):
            if is_designated_approver or is_admin:
                can_approve = True

        values = {
            'page_name': 'loan_detail',
            'loan': loan,
            'employee': employee,
            'is_owner': is_owner,
            'can_approve': can_approve,
            'submitted': bool(submitted),
            'token': kw.get('token'),
            'object': loan,
            'currency': loan.currency_id,
        }
        return request.render('loan_portal_exposure.portal_my_loan_detail', values)

    # -------------------------------------------------------------------------
    # Cancel Loan (by Employee)
    # -------------------------------------------------------------------------

    @http.route(['/my/loans/<int:loan_id>/cancel'], type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def portal_my_loan_cancel(self, loan_id, **kw):
        loan = self._check_loan_access(loan_id, mode='cancel')
        try:
            loan.action_portal_cancel()
        except Exception as e:
            return request.redirect(f'/my/loans/{loan_id}?error={str(e)}')
        return request.redirect(f'/my/loans/{loan_id}')

    # -------------------------------------------------------------------------
    # Loans to Approve (For Farm Managers & GM)
    # -------------------------------------------------------------------------

    @http.route(['/my/loans/to_approve', '/my/loans/to_approve/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_loans_to_approve(self, page=1, filterby=None, sortby=None, **kw):
        user = request.env.user
        employee = self._get_current_employee()

        to_approve_domain = self._get_to_approve_domain(user, employee)
        if not to_approve_domain:
            return request.render('loan_portal_exposure.portal_not_a_loan_approver', {
                'page_name': 'loan_not_approver'
            })

        Loan = request.env['hr.loan'].sudo()

        sortings = {
            'date_desc': {'label': _('Date (Newest)'), 'order': 'id desc'},
            'date_asc': {'label': _('Date (Oldest)'), 'order': 'id asc'},
            'amount_desc': {'label': _('Amount (Highest)'), 'order': 'loan_amount desc'},
        }
        if not sortby or sortby not in sortings:
            sortby = 'date_desc'
        order = sortings[sortby]['order']

        filters = {
            'pending': {'label': _('Pending My Approval'), 'domain': []},
            'advance_salary': {'label': _('Advance Salary Loans'), 'domain': [('loan_type', '=', 'advance_salary')]},
            'high_amount': {'label': _('High Amount Loans'), 'domain': [('loan_type', '=', 'high_amount')]},
            'all': {'label': _('All Approvals History'), 'domain': [('state', 'in', ['approved', 'rejected', 'waiting_farm_manager', 'waiting_hr', 'waiting_gm'])]},
        }
        if not filterby or filterby not in filters:
            filterby = 'pending'

        if filterby == 'pending':
            domain = to_approve_domain
        else:
            domain = expression.AND([to_approve_domain, filters[filterby]['domain']])

        total_requests = Loan.search_count(domain)
        pager = portal_pager(
            url="/my/loans/to_approve",
            url_args={'sortby': sortby, 'filterby': filterby},
            total=total_requests,
            page=page,
            step=10
        )

        loans = Loan.search(domain, order=order, limit=10, offset=pager['offset'])
        pending_count = Loan.search_count(to_approve_domain)

        values = {
            'page_name': 'loan_to_approve',
            'employee': employee,
            'loans': loans,
            'pending_count': pending_count,
            'pager': pager,
            'sortby': sortby,
            'sortings': sortings,
            'filterby': filterby,
            'filters': filters,
            'default_url': '/my/loans/to_approve',
            'currency': request.env.company.currency_id,
        }
        return request.render('loan_portal_exposure.portal_my_loans_to_approve', values)

    # -------------------------------------------------------------------------
    # Actions: Approve / Reject
    # -------------------------------------------------------------------------

    @http.route(['/my/loans/<int:loan_id>/approve'], type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def portal_my_loan_approve(self, loan_id, redirect_to=None, **kw):
        loan = self._check_loan_access(loan_id, mode='approve')
        try:
            if loan.state == 'waiting_hr':
                loan.action_portal_hr_approve()
            elif loan.state == 'waiting_gm':
                loan.action_portal_gm_approve()
            else:
                loan.action_portal_farm_manager_approve()
        except Exception as e:
            return request.redirect(f'/my/loans/{loan_id}?error={str(e)}')

        if redirect_to == 'to_approve':
            return request.redirect('/my/loans/to_approve?approved=1')
        return request.redirect(f'/my/loans/{loan_id}?approved=1')

    @http.route(['/my/loans/<int:loan_id>/reject'], type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def portal_my_loan_reject(self, loan_id, rejection_reason=None, redirect_to=None, **kw):
        loan = self._check_loan_access(loan_id, mode='approve')
        try:
            loan.action_portal_reject(reason=rejection_reason or "")
        except Exception as e:
            return request.redirect(f'/my/loans/{loan_id}?error={str(e)}')

        if redirect_to == 'to_approve':
            return request.redirect('/my/loans/to_approve?rejected=1')
        return request.redirect(f'/my/loans/{loan_id}?rejected=1')
