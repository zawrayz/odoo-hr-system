{
    "name": "HR Biometric Bridge",
    "version": "19.0.1.3.0",
    "summary": "Secure staging endpoint for biometric attendance punches",
    "category": "Human Resources",
    "author": "Blimp",
    "license": "LGPL-3",
    "depends": ["hr", "hr_attendance"],
    "data": [
        "security/ir.model.access.csv",
        "views/biometric_mapping_views.xml",
        "views/biometric_bridge_status_views.xml",
        "views/biometric_punch_views.xml",
        "views/biometric_attendance_views.xml",
    ],
    "installable": True,
    "application": False,
}
