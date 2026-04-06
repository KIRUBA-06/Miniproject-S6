function safeParseJsonScript(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  try {
    return JSON.parse(el.textContent);
  } catch (e) {
    return null;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const growth = safeParseJsonScript("growth-data");
  if (growth && document.getElementById("growthChart")) {
    new Chart(document.getElementById("growthChart"), {
      type: "line",
      data: {
        labels: growth.labels,
        datasets: [
          {
            label: "Coding Hours",
            data: growth.coding,
            borderColor: "#0a66c2",
            backgroundColor: "rgba(10,102,194,0.1)",
            tension: 0.3
          },
          {
            label: "Aptitude Hours",
            data: growth.aptitude,
            borderColor: "#ef6c00",
            backgroundColor: "rgba(239,108,0,0.1)",
            tension: 0.3
          }
        ]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }

  const readiness = safeParseJsonScript("readiness-data");
  if (readiness && document.getElementById("readinessChart")) {
    new Chart(document.getElementById("readinessChart"), {
      type: "bar",
      data: {
        labels: readiness.labels,
        datasets: [{
          label: "Readiness %",
          data: readiness.scores,
          backgroundColor: "#2e7d32"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { min: 0, max: 100 } }
      }
    });
  }

  const sgpa = safeParseJsonScript("sgpa-data");
  if (sgpa && document.getElementById("sgpaChart")) {
    new Chart(document.getElementById("sgpaChart"), {
      type: "line",
      data: {
        labels: sgpa.labels || [],
        datasets: [{
          label: "SGPA",
          data: sgpa.values || [],
          borderColor: "#1d6fd0",
          backgroundColor: "rgba(29,111,208,0.15)",
          tension: 0.3,
          fill: true
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { min: 0, max: 10 } }
      }
    });
  }
});
