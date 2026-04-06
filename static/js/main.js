document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("sidebarToggle");
  const sidebar = document.getElementById("sidebar");

  if (toggle && sidebar) {
    const mq = window.matchMedia("(max-width: 980px)");

    const updateToggleState = () => {
      if (!mq.matches) {
        sidebar.classList.remove("open");
      }
    };

    updateToggleState();
    mq.addEventListener("change", updateToggleState);

    toggle.addEventListener("click", () => {
      if (mq.matches) {
        sidebar.classList.toggle("open");
        toggle.setAttribute("aria-expanded", sidebar.classList.contains("open") ? "true" : "false");
      } else {
        sidebar.classList.toggle("is-hidden");
        toggle.setAttribute("aria-expanded", sidebar.classList.contains("is-hidden") ? "false" : "true");
      }
    });
  }
});
