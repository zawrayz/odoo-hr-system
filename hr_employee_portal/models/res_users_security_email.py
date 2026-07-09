from odoo import models


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _notify_security_setting_update(self, *args, **kwargs):
        """
        Suppress Odoo security notification emails for portal users only.

        This stops unwanted emails like:
        - Security Update: Login Changed
        - Security Update: Password Changed

        Internal/admin users keep normal Odoo security notifications.
        """
        portal_users = self.filtered(lambda user: user.share)

        # If the update is only for portal users, do not send security email.
        if portal_users and len(portal_users) == len(self):
            return False

        # If mixed recordset, allow notifications only for internal users.
        internal_users = self - portal_users
        if internal_users:
            return super(ResUsers, internal_users)._notify_security_setting_update(*args, **kwargs)

        return False
