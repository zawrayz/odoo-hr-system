/** @odoo-module **/

function setupPayrollZoom() {
    const scaleTarget = document.querySelector('[data-payroll-table-scale]');
    const controls = document.querySelector('[data-payroll-zoom-controls]');
    const zoomValue = document.querySelector('[data-payroll-zoom-value]');

    if (!scaleTarget || !controls || !zoomValue) {
        return;
    }

    const minZoom = 0.40;
    const maxZoom = 1.20;
    const step = 0.10;
    const defaultZoom = Number(scaleTarget.dataset.payrollDefaultZoom || '0.55');
    let currentZoom = defaultZoom;

    const applyZoom = () => {
        currentZoom = Math.min(maxZoom, Math.max(minZoom, currentZoom));
        scaleTarget.style.zoom = String(currentZoom);
        zoomValue.textContent = `${Math.round(currentZoom * 100)}%`;
    };

    controls.addEventListener('click', (event) => {
        const button = event.target.closest('[data-payroll-zoom-action]');
        if (!button) {
            return;
        }

        const action = button.dataset.payrollZoomAction;

        if (action === 'in') {
            currentZoom += step;
        } else if (action === 'out') {
            currentZoom -= step;
        } else if (action === 'reset') {
            currentZoom = defaultZoom;
        }

        applyZoom();
    });

    applyZoom();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupPayrollZoom);
} else {
    setupPayrollZoom();
}
