document.addEventListener("DOMContentLoaded", function () {
    const confirmationDialog = document.getElementById("markDoneDialog");
    const cancelConfirmationButton = confirmationDialog.querySelector(".mark-done-cancel");
    const confirmButton = confirmationDialog.querySelector(".mark-done-confirm");
    let pendingForm = null;

    cancelConfirmationButton.addEventListener("click", function () {
        pendingForm = null;
        confirmationDialog.close();
    });

    confirmButton.addEventListener("click", function () {
        if (!pendingForm) {
            return;
        }
        const form = pendingForm;
        pendingForm = null;
        confirmationDialog.close();
        form.submit();
    });

    document.querySelectorAll(".approved-event-row").forEach(function (row) {
        const form = row.querySelector(".mark-done-form");

        form.addEventListener("submit", function (event) {
            event.preventDefault();
            pendingForm = form;
            confirmationDialog.showModal();
        });

        function toggleAction() {
            const isExpanded = row.getAttribute("aria-expanded") === "true";
            row.setAttribute("aria-expanded", String(!isExpanded));
            row.classList.toggle("is-selected", !isExpanded);
            form.hidden = isExpanded;
        }

        row.addEventListener("click", function (event) {
            if (event.target.closest("button, form")) {
                return;
            }
            toggleAction();
        });

        row.addEventListener("keydown", function (event) {
            if (event.target.closest("button, form")) {
                return;
            }
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                toggleAction();
            }
        });
    });
});
