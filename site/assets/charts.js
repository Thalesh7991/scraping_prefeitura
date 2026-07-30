/* Wrappers finos sobre Chart.js - mantém as opções (grid discreto, sem legenda
   redundante, tooltip, altura controlada) consistentes em todas as páginas.

   Importante: todo <canvas> deve estar dentro de um <div class="chart-wrap"> com
   altura definida em CSS (position:relative) - sem isso, Chart.js em modo
   responsive entra num loop de redimensionamento (o container cresce sem limite). */

// Lê as cores já resolvidas do tema atual (claro/escuro) em vez de fixar uma cor só -
// assim o gráfico nasce correto tanto no modo claro quanto no escuro (o atributo
// data-theme já é definido antes deste script rodar, ver script inline no <head>).
const _estilo = getComputedStyle(document.documentElement);
const _corTexto = _estilo.getPropertyValue("--text-muted").trim() || "#7a7e87";
const _corBorda = _estilo.getPropertyValue("--border").trim() || "#e4e4e0";
const _corSurperficie = _estilo.getPropertyValue("--surface-raised").trim() || "#ffffff";
const _corInk = _estilo.getPropertyValue("--ink").trim() || "#12141a";

Chart.defaults.font.family = "'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif";
Chart.defaults.color = _corTexto;
Chart.defaults.borderColor = _corBorda;

const TOOLTIP_PADRAO = {
  backgroundColor: _corInk,
  titleColor: _corSurperficie,
  bodyColor: _corSurperficie,
  padding: 10,
  cornerRadius: 8,
  displayColors: false,
  titleFont: { weight: "600" },
  bodyFont: { weight: "500" },
};

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
      datasets: [{ data: valores, backgroundColor: cores, borderRadius: 6, maxBarThickness: 28 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: "y",
      animation: { duration: 300 },
      plugins: { legend: { display: false }, tooltip: TOOLTIP_PADRAO },
      scales: {
        x: { beginAtZero: true, grid: { color: _corBorda }, ticks: { precision: 0, font: { family: "'JetBrains Mono', monospace", size: 11 } } },
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
        tension: 0.35,
        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2.5,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: "circle" } },
        tooltip: TOOLTIP_PADRAO,
      },
      scales: {
        y: { beginAtZero: true, grid: { color: _corBorda }, ticks: { precision: 0, font: { family: "'JetBrains Mono', monospace", size: 11 } } },
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
      datasets: [{ data: valores, backgroundColor: cores, borderRadius: 6, maxBarThickness: 44 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      plugins: { legend: { display: false }, tooltip: TOOLTIP_PADRAO },
      scales: {
        y: { beginAtZero: true, grid: { color: _corBorda }, ticks: { precision: 0, font: { family: "'JetBrains Mono', monospace", size: 11 } } },
        x: { grid: { display: false } },
      },
    },
  });
}
