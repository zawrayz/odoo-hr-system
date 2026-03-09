{
    'name': 'HR Employee Extra Fields',
    'version': '1.0',
    'summary': 'Adds additional fields to employees',
    'description': 'Extends hr.employee model with employee code, blood group and joining date. Also generates automatic employee codes.',
    'category': 'Human Resources',
    'author': 'Zoraiz',
    'depends': ['hr'],
    'data': [
        'data/employee_sequence.xml',
        'views/employee_views.xml',
    ],
    'installable': True,
    'application': False,
}