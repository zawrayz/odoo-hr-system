{
    'name': 'HR Invoice Management',
    'version': '19.0.1.0.0',
    'summary': 'Admin invoice management for Blimp HR portal',
    'category': 'Human Resources',
    'author': 'Zoraiz',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'mail',
        'hr_employee_portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/invoice_sequence.xml',
        'views/invoice_views.xml',
        'views/portal_invoice_templates.xml',
        'report/invoice_report.xml',
    ],
    'installable': True,
    'application': False,
}