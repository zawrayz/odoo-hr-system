# Odoo HR System Project Guidelines (GEMINI.md)

This document establishes the permanent project context, architecture, important behaviors, and development rules for this Odoo HR project. All future Gemini CLI sessions MUST adhere strictly to the mandates defined herein.

---

## 1. Project & Repository Context
* **Repository:** `zawrayz/odoo-hr-system`
* **Local Workspace Path:** `C:\Users\PMLS\Odoo_Custom_Addons\odoo-hr-system`
* **Project Status:** This is an Odoo 19 HR management system featuring an employee portal and comprehensive admin HR functionality. The existing application is considered stable; treat existing working behavior as intentional.

---

## 2. Important Development Workflow
All changes must proceed via this strict sequence:
1. **Always inspect** the current code before planning or making changes.
2. **Never assume** the remote GitHub version is identical to the local working tree.
3. **Check `git status`** first before modifying anything.
4. **Preserve existing uncommitted changes** in the workspace.
5. **Never overwrite, reset, restore, or delete** unrelated user changes.
6. **Make the smallest possible change** required to implement the requested feature.
7. **Do not modify** unrelated modules or files.
8. **Before committing**, run `git diff` and verify that only the intended changes exist.
9. **Validate/test** Python code by checking for syntax/compilation errors.
10. **Never commit or push** unless explicitly instructed by the user.
11. **Restart Windows Odoo service** before testing any Python controller or backend changes.
12. **Hard-refresh the browser** (or rebuild/reload Odoo assets) after frontend/CSS modifications.
13. **Prefer local testing** before committing or pushing changes to GitHub.

---

## 3. Leave-Request Attendance Overlay Feature

### System Architecture
* **Relevant Backend Controller Logic:** `hr_employee_portal/controllers/portal.py`
* **Leave Request Model:** `hr.employee.portal.request`
* **Relevant Request Types:** `sick_leave`, `casual_leave`
* **Request States:** `submitted`, `approved`, `rejected`

### Attendance Display Behavior
* **SUBMITTED:** A submitted Sick or Casual leave request displays as **`LR`** (Leave Requested, Pending Approval).
* **APPROVED:** 
  * Approved Sick Leave displays as **`S`**
  * Approved Casual Leave displays as **`C`**
* **REJECTED:** A rejected leave request is excluded from the overlay, allowing the normal attendance-register or default attendance logic to apply.

### Priority Rules (Attendance Matrix Cell)
Leave-request overlay has **higher priority** than the hard attendance-register code. 

The cell code resolution sequence is:
1. **Post-Employment Check:** If the date is after the employee's `last_working_date`, display `'-'`.
2. **Leave-Request Overlay:** If there is an active Sick/Casual leave overlay (`LR`, `S`, or `C`), display the overlay code.
3. **Hard Attendance Register:** Otherwise, display the existing hard attendance-register code (from `register_map`).
4. **Weekend/Holiday/Default Logic:** If neither exists, fall back to weekend, holiday, or default `'-'` logic.

The working priority resolution logic:
```python
if after_last_working_date:
    code = '-'
else:
    overlay_code = leave_overlay.get(target_date)
    if overlay_code:
        code = overlay_code
    else:
        code = register_map.get(target_date)
```

---

## 4. Frontend & Styling
* **Styling File:** `hr_employee_portal/static/src/css/hr_employee_portal.css`
* **`LR` Cell CSS Rule:**
  ```css
  .hr-code-LR {
      background: #d1fae5;
      color: #065f46;
      border: 2px solid #10b981;
  }
  ```
* **Guardrails:** Do NOT change this CSS styling or modify any CSS files unless explicitly instructed by the user.

---

## 5. Expected User Experience Flow
1. **Submission:** Employee submits a Sick or Casual Leave request.
2. **Immediate Visibility:** The attendance date cell immediately updates to a green **`LR`**.
3. **Admin Decision:**
   * **Approved:** The cell switches to **`S`** (Sick) or **`C`** (Casual).
   * **Rejected:** The leave overlay disappears, and the cell immediately reverts to its normal attendance-register code or default status.

*Note: This behavior is already verified working. Do not "fix" or rewrite it unless a future change specifically requires it.*

---

## 6. Git & Workspace Safety Rules
To protect the local development environment and prevent code loss, **NEVER** run:
* `git reset --hard`
* `git restore` on user files
* `git clean`

When making a requested change:
1. **Inspect** relevant files.
2. **Explain** what will change.
3. **Make the minimal edit** (using surgical replacements rather than wholesale overwriting).
4. **Show the resulting diff** to the user.
5. **Validate & compile check**.
6. **Wait for explicit user approval** before any commit/push action.

---

## 7. Preservation & Stability Policy
* No speculative refactoring.
* No cleanups of unrelated code.
* No architecture changes unless explicitly requested.
* Before modifying anything in the future, always identify:
  * Which file controls the behavior.
  * What existing logic currently does.
  * What exact behavior the user wants.
  * What the smallest, safest change is to accomplish the goal.
## 8. Current Verified Baseline

As of August 24, 2026, the leave-request attendance overlay was tested successfully on the local Windows Odoo installation.

Verified behavior:
- Submitted Sick Leave → green `LR`
- Submitted Casual Leave → green `LR`
- Approved Sick Leave → `S`
- Approved Casual Leave → `C`
- Leave requests correctly override existing attendance-register codes
- Python controller passed `python -m py_compile`
- Odoo Windows service was restarted and the behavior was verified in the running application
- The working implementation was committed and pushed to GitHub

Treat this as the known-good baseline. Future changes must preserve this behavior unless the user explicitly requests otherwise.
