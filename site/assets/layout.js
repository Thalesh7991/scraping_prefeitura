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
        <img class="brasao" alt="Brasão de Botucatu"
             src="https://www.camarabotucatu.sp.gov.br/images/brasao-cidade.png"
             onerror="this.style.display='none'">
        <div class="header-text">
          <h1>Câmara de Vereadores de Botucatu em Dados</h1>
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
      Dados coletados automaticamente do site oficial da Câmara Municipal de Botucatu
      (camarabotucatu.sp.gov.br). Projeto independente, sem vínculo oficial com a Câmara
      ou a Prefeitura de Botucatu.
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
