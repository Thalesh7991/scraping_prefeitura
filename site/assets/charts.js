/* Wrappers finos sobre Chart.js - mantém as opções (grid discreto, sem legenda
   redundante, tooltip, altura controlada) consistentes em todas as páginas.

   Importante: todo <canvas> deve estar dentro de um <div class="chart-wrap"> com
   altura definida em CSS (position:relative) - sem isso, Chart.js em modo
   responsive entra num loop de redimensionamento (o container cresce sem limite). */

Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', sans-serif";
Chart.defaults.color = "#7a7e87";
Chart.defaults.borderColor = "#e4e4e0";

// Chart.js aceita um array de strings por rótulo (uma linha por item) - em telas
// estreitas, um rótulo longo numa linha só é cortado (o texto fica alinhado à
// direita do eixo e o excesso "vaza" para fora da área do gráfico). Quebrar em
// duas linhas evita isso sem depender da largura real da tela.
function quebrarRotulo(texto, maxCaracteres = 18) {
  if (!texto || texto.length <= maxCaracteres) return texto;
  const meio = Math.floor(texto.length / 2);
  let corte = texto.lastIndexOf(" ", meio);
  if (corte === -1) corte = texto.indexOf(" ", meio);
  if (corte === -1) return texto;
  return [texto.slice(0, corte), texto.slice(corte + 1)];
}

function graficoBarrasHorizontais(canvasId, labels, valores, cores) {
  const ctx = document.getElementById(canvasId);
  const wrap = ctx.parentElement;
  wrap.style.height = `${Math.max(220, 44 + labels.length * 34)}px`;
  return new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels.map((l) => quebrarRotulo(l)),
      datasets: [{ data: valores, backgroundColor: cores, borderRadius: 4, maxBarThickness: 32 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, grid: { color: "#e4e4e0" }, ticks: { precision: 0 } },
        y: { grid: { display: false } },
      },
    },
  });
}

function graficoLinhaTempo(canvasId, labels, series) {
  // series: [{ label, data, color }]
  const ctx = document.getElementById(canvasId);
  return new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: series.map((s) => ({
        label: s.label,
        data: s.data,
        borderColor: s.color,
        backgroundColor: s.color,
        tension: 0.3,
        pointRadius: 3,
        borderWidth: 2,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, boxHeight: 10 } } },
      scales: {
        y: { beginAtZero: true, grid: { color: "#e4e4e0" }, ticks: { precision: 0 } },
        x: { grid: { display: false } },
      },
    },
  });
}

function graficoBarrasStatus(canvasId, labels, valores, cores) {
  const ctx = document.getElementById(canvasId);
  return new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{ data: valores, backgroundColor: cores, borderRadius: 4, maxBarThickness: 48 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, grid: { color: "#e4e4e0" }, ticks: { precision: 0 } },
        x: { grid: { display: false } },
      },
    },
  });
}
