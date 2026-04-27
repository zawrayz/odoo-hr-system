(function () {
    function initHrPortalChatbot() {
        var launcher = document.getElementById("hrPortalChatLauncher");
        var widget = document.getElementById("hrPortalChatWidget");
        var closeBtn = document.getElementById("hrPortalChatClose");

        if (!launcher || !widget || !closeBtn) {
            console.log("HR chatbot widget elements not found.");
            return;
        }

        if (launcher.dataset.chatbotBound === "1") {
            return;
        }

        launcher.dataset.chatbotBound = "1";

        launcher.addEventListener("click", function () {
            widget.classList.toggle("is-open");
            console.log("HR chatbot launcher clicked.");
        });

        closeBtn.addEventListener("click", function () {
            widget.classList.remove("is-open");
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                widget.classList.remove("is-open");
            }
        });

        console.log("HR chatbot initialized.");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initHrPortalChatbot);
    } else {
        initHrPortalChatbot();
    }

    window.addEventListener("load", initHrPortalChatbot);
})();