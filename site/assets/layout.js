/* Cabeçalho, navegação e rodapé compartilhados por todas as páginas - um só lugar
   para editar em vez de repetir o mesmo HTML em cada .html. */

const PAGINAS_NAV = [
  { id: "index", label: "Visão geral", href: "index.html" },
  { id: "vereador", label: "Vereadores", href: "vereador.html" },
  { id: "comparar", label: "Comparar", href: "comparar.html" },
  { id: "tipos", label: "Por tipo", href: "tipos.html" },
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
      </div>`;
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
