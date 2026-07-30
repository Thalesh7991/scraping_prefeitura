/* Carregamento e utilidades de dados - a categorização (família/status) já vem
   pronta do JSON (calculada em Python, ver src/export_json.py); este arquivo só
   busca, agrega e formata para exibição. */

const CamaraData = (() => {
  let cachePromise = null;

  function carregar() {
    if (!cachePromise) {
      cachePromise = Promise.all([
        fetch("data/proposituras.json").then((r) => r.json()),
        fetch("data/vereadores.json").then((r) => r.json()),
        fetch("data/meta.json").then((r) => r.json()),
        fetch("data/remuneracao.json").then((r) => r.json()),
      ]).then(([proposituras, vereadores, meta, remuneracao]) => {
        const vereadoresPorId = {};
        vereadores.forEach((v) => (vereadoresPorId[v.id] = v));
        return { proposituras, vereadores, vereadoresPorId, meta, remuneracao };
      });
    }
    return cachePromise;
  }

  function formatarData(iso) {
    if (!iso) return "";
    const [ano, mes, dia] = iso.split("-");
    return `${dia}/${mes}/${ano}`;
  }

  function formatarNumero(n) {
    return Number(n).toLocaleString("pt-BR");
  }

  function formatarMoeda(n) {
    if (n === null || n === undefined) return "—";
    return Number(n).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }

  const NOMES_MES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];

  function agrupar(lista, chave) {
    const contagem = {};
    for (const item of lista) {
      const k = typeof chave === "function" ? chave(item) : item[chave];
      contagem[k] = (contagem[k] || 0) + 1;
    }
    return contagem;
  }

  function autoresDe(propositura, vereadoresPorId) {
    return (propositura.autores || []).map((id) => vereadoresPorId[id]).filter(Boolean);
  }

  const MINUSCULAS = new Set(["de", "da", "do", "das", "dos", "e"]);

  function tituloCase(texto) {
    if (!texto) return "";
    return texto
      .toLowerCase()
      .split(" ")
      .map((palavra, i) => (i > 0 && MINUSCULAS.has(palavra) ? palavra : palavra.charAt(0).toUpperCase() + palavra.slice(1)))
      .join(" ");
  }

  // O município reconhece o vereador pelo apelido muito mais do que pelo nome
  // completo - por isso o apelido é o nome de exibição padrão em todo o site.
  function nomeExibicao(vereador) {
    if (!vereador) return "";
    return vereador.apelido ? tituloCase(vereador.apelido) : tituloCase(vereador.nome);
  }

  function escapeHtml(valor) {
    if (valor === null || valor === undefined) return "";
    return String(valor)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  const TAMANHO_PAGINA = 25;
  const _estadoTabela = {};

  function tabelaProposituras(containerId, lista) {
    _estadoTabela[containerId] = { lista, visivel: TAMANHO_PAGINA };
    _renderizarTabela(containerId);
  }

  function _renderizarTabela(containerId) {
    const estado = _estadoTabela[containerId];
    const container = document.getElementById(containerId);
    if (!estado.lista.length) {
      container.innerHTML = '<p class="empty-state">Nenhuma proposta encontrada.</p>';
      return;
    }

    const visiveis = estado.lista.slice(0, estado.visivel);
    const linhas = visiveis
      .map((p) => {
        const cor = CORES_STATUS[p.status] || CORES_STATUS["Outra situação"];
        const doc = p.pdf_url
          ? `<a class="btn" href="${escapeHtml(p.pdf_url)}" target="_blank" rel="noopener">Ver documento</a>`
          : "";
        return `<tr>
          <td>${formatarData(p.data)}</td>
          <td>${escapeHtml(p.tipo)}</td>
          <td>${p.numero ?? ""}</td>
          <td>${p.ano ?? ""}</td>
          <td><span class="status-pill" style="background:${cor}">${escapeHtml(p.situacao)}</span></td>
          <td class="wrap">${escapeHtml(p.ementa)}</td>
          <td>${doc}</td>
        </tr>`;
      })
      .join("");

    const restantes = estado.lista.length - visiveis.length;
    const botaoId = `${containerId}-mostrar-mais`;
    const rodape = `<p class="section-caption" style="margin:.75rem 0 0">
        Mostrando ${formatarNumero(visiveis.length)} de ${formatarNumero(estado.lista.length)}
        ${restantes > 0 ? `<button class="btn" id="${botaoId}" style="margin-left:.75rem">Mostrar mais</button>` : ""}
      </p>`;

    container.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Data</th><th>Tipo</th><th>Número</th><th>Ano</th><th>Situação</th><th class="wrap">Assunto</th><th>Documento</th></tr></thead>
      <tbody>${linhas}</tbody>
    </table></div>${rodape}`;

    const botao = document.getElementById(botaoId);
    if (botao) {
      botao.addEventListener("click", () => {
        estado.visivel += TAMANHO_PAGINA;
        _renderizarTabela(containerId);
      });
    }
  }

  const FAMILIAS_ORDEM = [
    "Normativos",
    "Fiscalização/Solicitações",
    "Manifestações políticas",
    "Outros",
  ];

  const CORES_FAMILIA = {
    "Normativos": "#2a78d6",
    "Fiscalização/Solicitações": "#eb6834",
    "Manifestações políticas": "#1baf7a",
    "Outros": "#eda100",
  };

  const STATUS_ORDEM = ["Aprovado", "Rejeitado", "Em tramitação", "Arquivado/Retirado", "Outra situação"];
  const CORES_STATUS = {
    "Aprovado": "#0ca30c",
    "Rejeitado": "#d03b3b",
    "Em tramitação": "#d98c00",
    "Arquivado/Retirado": "#ec835a",
    "Outra situação": "#7a7e87",
  };

  const COR_CATEGORIA_CERIMONIAL = "#eda100";
  const COR_CATEGORIA_SUBSTANTIVA = "#2a78d6";
  const COR_CATEGORIA_RESIDUAL = "#7a7e87";
  const CATEGORIA_RESIDUAL_NOME = "Outros/Não identificado";

  // Cor por assunto: dourado = cerimonial/simbólico, azul = com efeito prático, cinza =
  // não identificado - a lista do que é cerimonial vem do meta.json (calculada em Python,
  // nunca duplicada aqui).
  function corCategoria(categoria, categoriasCerimoniais) {
    if (categoria === CATEGORIA_RESIDUAL_NOME) return COR_CATEGORIA_RESIDUAL;
    return (categoriasCerimoniais || []).includes(categoria) ? COR_CATEGORIA_CERIMONIAL : COR_CATEGORIA_SUBSTANTIVA;
  }

  return {
    carregar,
    formatarData,
    formatarNumero,
    formatarMoeda,
    agrupar,
    autoresDe,
    escapeHtml,
    tituloCase,
    nomeExibicao,
    tabelaProposituras,
    FAMILIAS_ORDEM,
    CORES_FAMILIA,
    STATUS_ORDEM,
    CORES_STATUS,
    corCategoria,
    NOMES_MES,
  };
})();
