{
    'name': 'HR Employee Update Import',
    'version': '19.0.1.0.0',
    'summary': 'Upload Excel file and update existing employees by Employee Code',
    'category': 'Human Resources',
    'author': 'Zoraiz Zia / Ihsan Mehmood',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'hr_employee_extra_fields',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/employee_update_import_views.xml',
    ],
    'installable': True,
    'application': False,
}