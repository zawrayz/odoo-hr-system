from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied
from odoo.addons.portal.controllers.portal import CustomerPortal


def _is_blocked_portal_employee():
    user = request.env.user

    if not user or user._is_public():
        return False

    # Internal users/admins are allowed
    if user.has_group("base.group_user"):
        return False

    # Portal users are blocked
    if user.has_group("base.group_portal"):
        return True

    return False


class HrPortalPasswordSecurity(CustomerPortal):

    @http.route(['/my/security'], type='http', auth='user', website=True)
    def security(self, **kw):
        if _is_blocked_portal_employee():
            return request.redirect('/my/hr')
        return super().security(**kw)


class HrPortalPasswordChangeBlock(http.Controller):

    @http.route('/web/session/change_password', type='json', auth='user')
    def change_password(self, fields):
        if _is_blocked_portal_employee():
            raise AccessDenied("Portal employees are not allowed to change their password.")
        return request.env['ir.http']._dispatch()