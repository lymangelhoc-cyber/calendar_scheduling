document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.querySelector(".table-search-input");
    const searchableRows = Array.from(document.querySelectorAll(".table-search-row"));
    const noMatchesRow = document.querySelector(".table-search-no-matches");

    if (!searchInput || !noMatchesRow || searchableRows.length === 0) {
        return;
    }

    searchInput.addEventListener("input", function () {
        const query = searchInput.value.trim().toLocaleLowerCase();
        let visibleCount = 0;

        searchableRows.forEach(function (row) {
            const matches = row.textContent.toLocaleLowerCase().includes(query);
            row.hidden = !matches;
            if (matches) {
                visibleCount += 1;
            }
        });

        noMatchesRow.hidden = visibleCount > 0;
    });
});
