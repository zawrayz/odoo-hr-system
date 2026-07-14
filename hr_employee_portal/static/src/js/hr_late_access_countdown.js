document.addEventListener('DOMContentLoaded', function () {
    function findCountdownForForm(form) {
        var parent = form.parentElement;
        if (parent) {
            var countdown = parent.querySelector('.hr-late-access-countdown');
            if (countdown) {
                return countdown;
            }
        }

        var previous = form.previousElementSibling;
        while (previous) {
            var found = previous.querySelector ? previous.querySelector('.hr-late-access-countdown') : null;
            if (found) {
                return found;
            }
            previous = previous.previousElementSibling;
        }

        return document.querySelector('.hr-late-access-countdown');
    }

    function updateLateAccessForms() {
        document.querySelectorAll('.hr-late-access-form').forEach(function (form) {
            var expiresUtc = form.getAttribute('data-expires-utc');
            var countdown = findCountdownForForm(form);
            var submitButton = form.querySelector('button[type="submit"]');

            if (!expiresUtc) {
                if (countdown) {
                    countdown.textContent = 'Expiry time unavailable. Please refresh.';
                }
                return;
            }

            var expiryTime = new Date(expiresUtc).getTime();
            var now = Date.now();
            var diff = expiryTime - now;

            if (diff <= 0) {
                if (countdown) {
                    countdown.textContent = 'Expired. Please refresh the page or contact admin.';
                }
                if (submitButton) {
                    submitButton.disabled = true;
                    submitButton.classList.add('disabled');
                    submitButton.innerHTML = '<i class="fa fa-lock me-2"></i> Access Expired';
                }
                return;
            }

            var totalSeconds = Math.floor(diff / 1000);
            var hours = Math.floor(totalSeconds / 3600);
            var minutes = Math.floor((totalSeconds % 3600) / 60);
            var seconds = totalSeconds % 60;

            var label = '';
            if (hours > 0) {
                label += hours + 'h ';
            }
            label += minutes + 'm ' + seconds + 's';

            if (countdown) {
                countdown.textContent = label;
            }
        });
    }

    updateLateAccessForms();
    setInterval(updateLateAccessForms, 1000);

    document.querySelectorAll('.hr-late-access-form').forEach(function (form) {
        form.addEventListener('submit', function (event) {
            var expiresUtc = form.getAttribute('data-expires-utc');
            if (!expiresUtc) {
                return;
            }

            if (new Date(expiresUtc).getTime() <= Date.now()) {
                event.preventDefault();
                alert('Temporary access has expired. Please refresh the page or contact admin.');
            }
        });
    });
});
