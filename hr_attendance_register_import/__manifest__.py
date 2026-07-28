{
    'name': 'HR Attendance Register Import',
    'version': '19.0.1.0.0',
    'summary': 'Import monthly attendance register and sync daily work reports to attendance codes',
    'category': 'Human Resources',
    'author': 'Zoraiz',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'hr_employee_extra_fields',
        'hr_daily_work_report',
    ],
    'data': [
        'data/management_auto_attendance_cron.xml',
        'security/ir.model.access.csv',
        'views/attendance_register_views.xml',
    ],
    'installable': True,
    'application': False,
}