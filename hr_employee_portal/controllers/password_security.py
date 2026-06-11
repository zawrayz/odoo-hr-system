from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.web.controllers.session import Session


def _is_portal_employee_user():
    user = request.env.user

    if not user or user._is_public():
        return False

    # Admin/internal users are allowed
    if user.has_group("base.group_user"):
        return False

    # Portal employees are blocked
    if user.has_group("base.group_portal"):
        return True

    return False


class HrPortalSecurityBlock(CustomerPortal):

    @http.route(['/my/security'], type='http', auth='user', website=True)
    def security(self, **kw):
        if _is_portal_employee_user():
            return request.redirect('/my/hr')
        return super().security(**kw)


class HrPortalSessionPasswordBlock(Session):

    @http.route('/web/session/change_password', type='json', auth='user')
    def change_password(self, fields):
        if _is_portal_employee_user():
            raise AccessDenied("Portal employees are not allowed to change their password.")
        return super().change_password(fields)