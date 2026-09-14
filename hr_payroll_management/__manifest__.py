{
    'name': 'HR Payroll Management',
    'version': '19.0.1.0.0',
    'summary': 'Payroll workspace inside the BLIMP Finance section',
    'category': 'Human Resources',
    'author': 'Zoraiz',
    'license': 'LGPL-3',
    'depends': [
        'hr_petty_cash_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/payroll_seed_data.xml',
        'views/payroll_portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'hr_payroll_management/static/src/css/payroll_portal.css',
            'hr_payroll_management/static/src/js/payroll_portal.js',
        ],
    },
    'installable': True,
    'application': False,
}
