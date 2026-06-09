(function () {
    function initHrPortalChatbot() {
        var launcher = document.getElementById("hrPortalChatLauncher");
        var widget = document.getElementById("hrPortalChatWidget");
        var closeBtn = document.getElementById("hrPortalChatClose");

        if (!launcher || !widget || !closeBtn) {
            return;
        }

        if (launcher.dataset.chatbotBound === "1") {
            return;
        }

        launcher.dataset.chatbotBound = "1";

        launcher.addEventListener("click", function () {
            if (widget.style.display === "none" || widget.style.display === "") {
                widget.style.display = "block";
            } else {
                widget.style.display = "none";
            }
        });

        closeBtn.addEventListener("click", function () {
            widget.style.display = "none";
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                widget.style.display = "none";
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initHrPortalChatbot);
    } else {
        initHrPortalChatbot();
    }

    window.addEventListener("load", initHrPortalChatbot);
})();