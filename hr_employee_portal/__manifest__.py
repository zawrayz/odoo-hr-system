{
    'name': 'HR Employee Portal',
    'version': '1.0',
    'summary': 'Employee self-service portal for HR',
    'category': 'Human Resources',
    'author': 'Zoraiz',
    'depends': [
        'portal',
        'hr',
        'hr_attendance',
        'hr_holidays',
        'hr_employee_extra_fields',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_templates.xml',
        'views/hr_chatbot_menu.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'hr_employee_portal/static/src/css/hr_employee_portal.css',
            'hr_employee_portal/static/src/js/hr_employee_portal_chatbot.js',
        ],
    },
    'installable': True,
    'application': False,
}