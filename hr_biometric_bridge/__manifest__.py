{
    "name": "HR Biometric Bridge",
    "version": "19.0.1.1.0",
    "summary": "Secure staging endpoint for biometric attendance punches",
    "category": "Human Resources",
    "author": "Blimp",
    "license": "LGPL-3",
    "depends": ["hr"],
    "data": [
        "security/ir.model.access.csv",
        "views/biometric_punch_views.xml",
    ],
    "installable": True,
    "application": False,
}
