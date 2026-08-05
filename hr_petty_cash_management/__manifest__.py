{
    'name': 'HR Petty Cash Management',
    'version': '19.0.1.0.0',
    'summary': 'Petty cash management for the BLIMP Finance section',
    'category': 'Human Resources',
    'author': 'Zoraiz',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'hr_employee_portal',
    ],
    'data': [
        'views/petty_cash_portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'hr_petty_cash_management/static/src/css/petty_cash_portal.css',
        ],
    },
    'installable': True,
    'application': False,
}