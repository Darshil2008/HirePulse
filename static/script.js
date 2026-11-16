// HirePulse Scroll Dock & Portal Interactivity
document.addEventListener("DOMContentLoaded", function () {
    console.log("HirePulse Platform initialized successfully.");
    const dock = document.getElementById("tjScrollDock");

    if (dock) {
        let lastScrollY = window.scrollY;

        window.addEventListener("scroll", function () {
            // When scrolled past the top hero/search area (~250px)
            if (window.scrollY > 250) {
                dock.classList.add("is-visible");
            } else {
                dock.classList.remove("is-visible");
            }
            lastScrollY = window.scrollY;
        }, { passive: true });
    }

    // Auto-dismiss alert banners after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    });
});
