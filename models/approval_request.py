# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    loan_ids = fields.One2many(
        'hr.loan',
        'approval_request_id',
        string="Linked Employee Loans"
    )

    def action_approve(self, approver=None):
        res = super().action_approve(approver=approver)
        for req in self:
            if req.request_status == 'approved':
                for loan in req.loan_ids.filtered(lambda l: l.state in ['waiting_farm_manager', 'waiting_gm']):
                    if loan.loan_type == 'high_amount':
                        loan.action_portal_gm_approve()
                    else:
                        loan.action_portal_farm_manager_approve()
        return res

    def action_refuse(self, approver=None):
        res = super().action_refuse(approver=approver)
        for req in self:
            if req.request_status == 'refused':
                for loan in req.loan_ids.filtered(lambda l: l.state in ['waiting_farm_manager', 'waiting_gm']):
                    loan.action_portal_reject(reason="Refused via Approvals Module.")
        return res
