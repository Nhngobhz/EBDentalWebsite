document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("langDropdownBtn");
    const menu = document.getElementById("langDropdownMenu");
    const flagIcon = document.getElementById("langFlagIcon");
    const label = document.getElementById("langLabel");

    if (!btn || !menu) return;

    btn.addEventListener("click", (e) => {
        e.stopPropagation();
        menu.classList.toggle("open");
    });

    document.addEventListener("click", () => {
        menu.classList.remove("open");
    });

    document.querySelectorAll(".lang-option").forEach(option => {
        option.addEventListener("click", () => {
            const lang = option.getAttribute("data-lang");
            flagIcon.src = option.getAttribute("data-flag");
            label.textContent = option.getAttribute("data-label");
            menu.classList.remove("open");
            localStorage.setItem("eb_lang", lang);
            console.log("Language selected:", lang);
            // Actual translation swap will hook in here later
        });
    });
});