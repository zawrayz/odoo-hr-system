{
    'name': 'HR Daily Work Report',
    'version': '1.0',
    'summary': 'Daily employee work reports for office, WFH, leave tracking, and performance planning',
    'category': 'Human Resources',
    'author': 'Zoraiz',
    'depends': ['hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/daily_work_report_views.xml',
        'views/daily_performance_plan_views.xml',
    ],
    'installable': True,
    'application': True,
}