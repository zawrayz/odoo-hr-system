from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrDailyPerformancePlan(models.Model):
    _name = 'hr.daily.performance.plan'
    _description = 'HR Daily Performance & Project Plan'
    _order = 'plan_date desc, id desc'

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
        related='employee_id.user_id',
        store=True,
        readonly=True,
    )

    plan_date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
    )

    task_id = fields.Char(
        string='Task ID',
        required=True,
    )

    project_name = fields.Char(
        string='Project',
        required=True,
    )

    task_description = fields.Text(
        string='Task Description',
        required=True,
    )

    priority_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], string='Priority Level', required=True, default='medium')

    status = fields.Selection([
        ('pending', 'Pending'),
        ('underprocess', 'Under Process'),
        ('completed', 'Completed'),
        ('hold', 'On Hold'),
    ], string='Status', required=True, default='pending')

    completion_percent = fields.Float(
        string='Completion (%)',
        default=0.0,
    )

    supervisor_remarks = fields.Text(
        string='Supervisor Remarks',
    )

    @api.depends('employee_id', 'plan_date', 'task_id')
    def _compute_name(self):
        for rec in self:
            employee_name = rec.employee_id.name or 'Employee'
            task_id = rec.task_id or 'Task'
            plan_date = rec.plan_date or ''
            rec.name = f"{employee_name} - {task_id} - {plan_date}"

    @api.constrains('completion_percent')
    def _check_completion_percent(self):
        for rec in self:
            if rec.completion_percent < 0 or rec.completion_percent > 100:
                raise ValidationError("Completion percentage must be between 0 and 100.")

    @api.constrains('task_id', 'task_description', 'project_name')
    def _check_required_texts(self):
        for rec in self:
            if not (rec.task_id or '').strip():
                raise ValidationError("Task ID is required.")
            if not (rec.project_name or '').strip():
                raise ValidationError("Project is required.")
            if not (rec.task_description or '').strip():
                raise ValidationError("Task Description is required.")
    def write(self, vals):
        if self.env.context.get('employee_portal_edit'):
            forbidden_fields = {'employee_id', 'completion_percent', 'supervisor_remarks', 'user_id', 'name'}
            blocked = forbidden_fields.intersection(set(vals.keys()))
            if blocked:
                raise ValidationError("You are not allowed to update restricted performance fields from the employee portal.")
        return super().write(vals)        