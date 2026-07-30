/* Cabeçalho, navegação e rodapé compartilhados por todas as páginas - um só lugar
   para editar em vez de repetir o mesmo HTML em cada .html. */

const PAGINAS_NAV = [
  { id: "index", label: "Visão geral", href: "index.html" },
  { id: "vereador", label: "Vereadores", href: "vereador.html" },
  { id: "comparar", label: "Comparar", href: "comparar.html" },
  { id: "buscar", label: "Buscar", href: "buscar.html" },
];

function montarLayout(paginaAtiva) {
  const header = document.getElementById("site-header");
  const nav = document.getElementById("site-nav");
  const footer = document.getElementById("site-footer");

  if (header) {
    header.innerHTML = `
      <div class="container">
        <div class="brandmark" aria-hidden="true">CB</div>
        <div class="header-text">
          <h1>Câmara de Botucatu em Dados</h1>
          <p id="header-caption">Carregando dados...</p>
        </div>
        <button type="button" class="theme-toggle" id="theme-toggle" aria-label="Alternar modo escuro/claro" title="Alternar modo escuro/claro">
          <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
          <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12.5A8 8 0 1 1 11.5 4a6.5 6.5 0 0 0 8.5 8.5Z"/></svg>
        </button>
      </div>`;
    const botaoTema = document.getElementById("theme-toggle");
    if (botaoTema) {
      botaoTema.addEventListener("click", () => {
        const explicito = document.documentElement.getAttribute("data-theme");
        const sistemaEscuro = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
        const atual = explicito || (sistemaEscuro ? "dark" : "light");
        const proximo = atual === "dark" ? "light" : "dark";
        localStorage.setItem("tema", proximo);
        location.reload();
      });
    }
  }

  if (nav) {
    nav.innerHTML =
      `<div class="container">` +
      PAGINAS_NAV.map(
        (p) => `<a href="${p.href}" class="${p.id === paginaAtiva ? "active" : ""}">${p.label}</a>`
      ).join("") +
      `</div>`;
  }

  if (footer) {
    footer.innerHTML = `<div class="container">
      <p style="margin:0">
        Projeto independente de acompanhamento legislativo. Sem vínculo oficial com a
        Câmara ou a Prefeitura de Botucatu.
      </p>
      <div class="fonte-oficial">
        <img alt="" aria-hidden="true"
             src="https://www.camarabotucatu.sp.gov.br/images/brasao-cidade.png"
             onerror="this.style.display='none'">
        <span>Dados coletados automaticamente do site oficial da Câmara Municipal de Botucatu (camarabotucatu.sp.gov.br).</span>
      </div>
    </div>`;
  }
}

function atualizarCabecalho(meta) {
  const el = document.getElementById("header-caption");
  if (!el) return;
  const atualizado = meta.gerado_em
    ? new Date(meta.gerado_em).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })
    : "desconhecida";
  el.textContent =
    `Veja o que os vereadores em exercício têm proposto desde o início do mandato atual ` +
    `(${meta.legislatura_atual_inicio_display}). Última atualização: ${atualizado}.`;
}
