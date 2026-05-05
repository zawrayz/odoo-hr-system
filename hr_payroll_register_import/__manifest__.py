{
    'name': 'HR Payroll Register Import',
    'version': '19.0.1.0.0',
    'summary': 'Import monthly payroll register and connect payroll data to employee/admin portal',
    'category': 'Human Resources',
    'author': 'Zoraiz',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'hr_employee_extra_fields',
        'hr_employee_portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/payroll_register_views.xml',
    ],
    'installable': True,
    'application': False,
}