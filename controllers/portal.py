# -*- coding: utf-8 -*-
import base64
from datetime import datetime, date
from werkzeug.exceptions import Forbidden, NotFound

from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression


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
        """ Builds domain for loans waiting for user's approval (as Farm Manager or GM) """
        domains = []
        is_gm = user.company_id.loan_gm_user_id.id == user.id or user.has_group('base.group_system')

        # 1. GM domain: high monetary amount loans waiting for GM
        if is_gm:
            domains.append([('state', '=', 'waiting_gm')])

        # 2. Farm Manager domain: advance salary loans from employees in managed farms or subordinates
        if employee:
            managed_farms = request.env['farm.farm'].sudo().search([('manager_id', '=', employee.id)])
            subordinates = employee.get_subordinate_employees() if hasattr(employee, 'get_subordinate_employees') else request.env['hr.employee'].sudo().search([('parent_id', '=', employee.id)])
            
            fm_criteria = []
            if managed_farms:
                fm_criteria.append(('farm_id', 'in', managed_farms.ids))
            if subordinates:
                fm_criteria.append(('employee_id', 'in', subordinates.ids))
            
            if fm_criteria:
                farm_filter = expression.OR([[(c[0], c[1], c[2])] for c in fm_criteria])
                domains.append(expression.AND([[('state', '=', 'waiting_farm_manager')], farm_filter]))

        if not domains:
            return []

        return expression.OR(domains)

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
        is_gm = user.company_id.loan_gm_user_id.id == user.id
        is_farm_manager = employee and (
            (loan.farm_id and loan.farm_id.manager_id.id == employee.id) or
            (loan.farm_manager_id and loan.farm_manager_id.id == employee.id) or
            (loan.employee_id.parent_id and loan.employee_id.parent_id.id == employee.id)
        )

        if mode == 'read':
            if not (is_owner or is_gm or is_farm_manager):
                raise Forbidden(_("You do not have permission to view this loan request."))
        elif mode == 'approve':
            if loan.loan_type == 'advance_salary' and not (is_farm_manager or is_gm):
                raise Forbidden(_("Only the Farm Manager can approve this Advance Salary Loan."))
            elif loan.loan_type == 'high_amount' and not is_gm:
                raise Forbidden(_("Only the General Manager (GM) can approve this High Amount Loan."))
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
                    if installment_months not in (6, 12):
                        installment_months = 6
                except (ValueError, TypeError):
                    installment_months = 6

                # High monetary loan rules validation
                if monthly_salary > 0 and loan_amount > 0:
                    if loan_amount > max_loan_amount:
                        errors.append(_("The requested loan amount (%(amt)s %(curr)s) exceeds the maximum allowed 4 times your monthly salary (Max: %(max_amt)s %(curr)s).") % {
                            'amt': loan_amount,
                            'curr': currency.symbol or '',
                            'max_amt': max_loan_amount
                        })
                    
                    monthly_ded = round(loan_amount / installment_months, 2)
                    if monthly_ded > (max_monthly_installment + 0.01):
                        errors.append(_("Monthly installment (%(ded)s %(curr)s/month) exceeds the maximum allowed 1/3 of your monthly salary (Max deduction: %(max_ded)s %(curr)s/month). Please choose 12 months duration or reduce the loan amount.") % {
                            'ded': monthly_ded,
                            'curr': currency.symbol or '',
                            'max_ded': max_monthly_installment
                        })

            if not reason:
                errors.append(_("Please provide a reason or purpose for the loan request."))

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

        values = {
            'page_name': 'loan_new',
            'employee': employee,
            'monthly_salary': monthly_salary,
            'max_loan_amount': max_loan_amount,
            'max_monthly_installment': max_monthly_installment,
            'advance_installment': advance_installment,
            'farm_manager': farm_manager,
            'gm_user': gm_user,
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
        is_gm = user.company_id.loan_gm_user_id.id == user.id
        is_farm_manager = employee and (
            (loan.farm_id and loan.farm_id.manager_id.id == employee.id) or
            (loan.farm_manager_id and loan.farm_manager_id.id == employee.id) or
            (loan.employee_id.parent_id and loan.employee_id.parent_id.id == employee.id)
        )

        can_approve = (loan.loan_type == 'advance_salary' and is_farm_manager) or (loan.loan_type == 'high_amount' and is_gm)

        values = {
            'page_name': 'loan_detail',
            'loan': loan,
            'employee': employee,
            'is_owner': is_owner,
            'is_gm': is_gm,
            'is_farm_manager': is_farm_manager,
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
            'all': {'label': _('All Approvals History'), 'domain': [('state', 'in', ['approved', 'rejected', 'waiting_farm_manager', 'waiting_gm'])]},
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
            if loan.loan_type == 'advance_salary':
                loan.action_portal_farm_manager_approve()
            else:
                loan.action_portal_gm_approve()
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
