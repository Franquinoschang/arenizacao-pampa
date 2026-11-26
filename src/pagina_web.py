"""Página web do projeto (docs/index.html): mapa interativo e relatório a partir dos CSVs de resultados.

Usado pela etapa 10 do notebook. A identidade visual segue DESIGN.md, na raiz do repositório. Os números do texto e dos
gráficos vêm de data/processed/, então a página sempre reflete a última rodada do notebook.
"""

import html
import json
import shutil
from pathlib import Path

import pandas as pd

# Classes do mapa e cores da página (DESIGN.md). As cores das classes só aparecem no mapa e nos gráficos.
CLASSES_MAPA = {1: "Areal", 2: "Campo", 3: "Lavoura", 4: "Silvicultura", 5: "Água", 6: "Vegetação Nativa"}
CORES_WEB = {1: "#E4572E", 2: "#A8C66C", 3: "#F2C14E", 4: "#7A5900", 5: "#2E86C1", 6: "#2D6A4F"}
COR_LAVOURA_EXPOSTA = "#C99A3B"   # subclasse de treino 7, tom de palha mais escuro que a Lavoura
COR_OUTRAS_MB = "#B9B4C7"         # classes do MapBiomas sem equivalente no projeto

# MapBiomas: grupos para o gráfico "para onde vai o Areal" (códigos da legenda -> grupo, cor)
GRUPOS_MB = [
    ("Praia, duna e areal", [23], CORES_WEB[1]),
    ("Outras áreas não vegetadas", [25], "#8E7F6A"),
    ("Mosaico de usos", [21], COR_OUTRAS_MB),
    ("Lavoura", [18, 19, 20, 35, 36, 39, 40, 41, 46, 47, 48, 62], CORES_WEB[3]),
    ("Campo e pastagem", [12, 15], CORES_WEB[2]),
    ("Floresta e silvicultura", [3, 4, 6, 9], CORES_WEB[6]),
    ("Água e áreas alagadas", [11, 31, 33], CORES_WEB[5]),
]

VARIAVEIS_ASSINATURA = {
    "FREQ_EXPOSTO": "Frequência de solo exposto",
    "NDVI_medio": "NDVI médio",
    "NDVI_amp": "Amplitude do NDVI",
    "NDVI_min": "NDVI mínimo",
    "BSI_med": "BSI mediano",
}


def br(valor, casas=2):
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _vento():
    caminho = "M0 12 Q75 3 150 12" + "".join(f" T{x} 12" for x in range(300, 1201, 150))
    return (f'<svg class="vento" viewBox="0 0 1200 24" preserveAspectRatio="none" aria-hidden="true">'
            f'<path d="{caminho}"/></svg>')


def _metricas(arquivo):
    if not arquivo.exists():
        return None
    df = pd.read_csv(arquivo, index_col=0)
    # Valores com precisão total: o arredondamento para exibição é feito uma vez só, na página
    linhas = [{"classe": c, "precisao": round(df.loc[c, "precision"], 6), "recall": round(df.loc[c, "recall"], 6),
               "f1": round(df.loc[c, "f1-score"], 6), "n": int(df.loc[c, "support"])}
              for c in df.index if c not in ("accuracy", "macro avg", "weighted avg")]
    return {"linhas": linhas, "acuracia": round(df.loc["accuracy", "f1-score"], 6),
            "f1_macro": round(df.loc["macro avg", "f1-score"], 6)}


def _barras_area(areas):
    total = areas.sum()
    linhas = []
    for c in [1] + [c for c in CLASSES_MAPA if c != 1]:
        km2 = areas.get(c, 0.0)
        linhas.append(
            f'<div class="barra-linha"><span>{CLASSES_MAPA[c]}</span>'
            f'<span class="trilho"><span class="barra" style="width:{100 * km2 / areas.max():.1f}%;'
            f'background:{CORES_WEB[c]}"></span></span>'
            f'<span class="valor">{br(km2)} km² · {br(100 * km2 / total, 1)}%</span></div>')
    return "".join(linhas)


def _empilhada(partes, total_rotulo):
    # partes: lista de (rótulo, km², cor); barra única 100% com legenda
    total = sum(p[1] for p in partes)
    blocos = "".join(
        f'<span style="width:{100 * km2 / total:.2f}%;background:{cor}" '
        f'title="{html.escape(rot)}: {br(km2)} km² ({br(100 * km2 / total, 1)}%)"></span>'
        for rot, km2, cor in partes if km2 > 0)
    def pct(km2):
        return "&lt;1%" if 100 * km2 / total < 1 else f"{br(100 * km2 / total, 0)}%"

    legenda = "".join(
        f'<li><span class="cor" style="background:{cor}"></span>{html.escape(rot)}'
        f'<b>{pct(km2)}</b></li>' for rot, km2, cor in partes if km2 > 0)
    return (f'<div class="empilhada" role="img" aria-label="{html.escape(total_rotulo)}">{blocos}</div>'
            f'<ul class="legenda-empilhada">{legenda}</ul>')


def _matriz_mapbiomas(tabela):
    colunas = [c for c in list(CLASSES_MAPA.values()) + ["Outras"] if c in tabela.columns]
    linhas_html = []
    for classe in [c for c in CLASSES_MAPA.values() if c in tabela.index]:
        linha = tabela.loc[classe, colunas]
        total = linha.sum()
        celulas = []
        for col in colunas:
            frac = linha[col] / total if total else 0
            escura = " escura" if frac > 0.45 else ""
            celulas.append(f'<td class="calor{escura}" style="--a:{frac:.3f}" '
                           f'title="{classe} neste mapa e {col} no MapBiomas: {br(linha[col])} km²">'
                           f'{br(100 * frac, 0)}%</td>')
        linhas_html.append(f'<tr><th scope="row">{classe}</th>{"".join(celulas)}</tr>')
    cabecalho = "".join(f'<th scope="col">{c}</th>' for c in colunas)
    return (f'<table class="matriz"><thead><tr><th></th>{cabecalho}</tr></thead>'
            f'<tbody>{"".join(linhas_html)}</tbody></table>')


def gerar_pagina(*, pasta_processados, pasta_web, pasta_figuras, ano, ano_mapbiomas, limites, areais_geojson,
                 bacia_geojson, tem_mb, periodos_s2=(), areal_por_mb=None, n_cenas=None, logos=(), repo_url="",
                 site_url="https://franquinoschang.github.io/arenizacao-pampa/"):
    """Gera pasta_web/index.html.

    limites: (oeste, sul, leste, norte) em graus. periodos_s2: [(arquivo, rótulo)] das imagens Sentinel-2 de
    fundo em pasta_web, a mediana do ano primeiro. areal_por_mb: {código MapBiomas: km²} do Areal deste mapa,
    calculado dos GeoTIFFs (opcional; sem ele, usa a tabela de comparação, com "Outras" agrupadas).
    """
    proc, web = Path(pasta_processados), Path(pasta_web)
    oeste, sul, leste, norte = limites

    # --- Dados -------------------------------------------------------------------------------------------
    areas = pd.read_csv(proc / f"area_por_classe_{ano}.csv").set_index("classe")["area_km2"]
    area_areal, area_total = areas.get(1, 0.0), areas.sum()

    metricas = {
        "ee": _metricas(proc / f"metricas_teste_mapa_ee_{ano}.csv"),
        "mapa": _metricas(proc / f"metricas_teste_mapa_{ano}.csv"),
        "treino": _metricas(proc / f"metricas_teste_{ano}.csv"),
    }
    principal = metricas["ee"] or metricas["mapa"]
    f1_areal = next(l["f1"] for l in principal["linhas"] if l["classe"] == "Areal")

    amostras = pd.read_csv(proc / f"amostras_variaveis_{ano}.csv")
    n_treino = int((amostras["conjunto"] == "treino").sum())
    n_teste = int((amostras["conjunto"] == "teste").sum())
    nomes_treino = {**CLASSES_MAPA, 7: "Lavoura exposta"}
    cores_treino = {**CORES_WEB, 7: COR_LAVOURA_EXPOSTA}
    assinatura = {"classes": [], "variaveis": VARIAVEIS_ASSINATURA, "valores": {}}
    for c in [1, 7, 3, 2, 6, 4, 5]:
        sub = amostras[amostras["classe"] == c]
        if sub.empty:
            continue
        assinatura["classes"].append({"nome": nomes_treino[c], "cor": cores_treino[c]})
        for v in VARIAVEIS_ASSINATURA:
            q = sub[v].quantile([0.25, 0.5, 0.75]).round(6).tolist()
            assinatura["valores"].setdefault(v, []).append(q)

    ajuste = pd.read_csv(proc / "ajuste_hiperparametros_rf.csv").sort_values("mean_test_score", ascending=False)
    melhor = ajuste.iloc[0]
    profundidade = "sem limite" if pd.isna(melhor["param_max_depth"]) else str(int(melhor["param_max_depth"]))

    importancia = pd.read_csv(proc / f"importancia_por_classe_{ano}.csv", index_col=0)
    dados_importancia = {"variaveis": importancia.index.tolist(),
                         "classes": importancia.columns.tolist(),
                         "valores": {c: importancia[c].round(6).tolist() for c in importancia.columns}}

    qc = pd.read_csv(proc / f"qc_areais_{ano}.csv")
    qc_resumo = qc.groupby("status").agg(n=("poligono", "size"), ha=("area_ha", "sum"))

    # Comparações com o MapBiomas e a SEMA-RS
    tabela_mb = pd.read_csv(proc / f"comparacao_mapbiomas_{ano}.csv", index_col=0)
    iguais = [c for c in tabela_mb.index if c in tabela_mb.columns]
    concordancia_mb = sum(tabela_mb.loc[c, c] for c in iguais) / tabela_mb.to_numpy().sum()
    if areal_por_mb:
        partes_mb = [(rot, sum(areal_por_mb.get(k, 0.0) for k in cods), cor) for rot, cods, cor in GRUPOS_MB]
        resto = sum(areal_por_mb.values()) - sum(p[1] for p in partes_mb)
        if resto > 0:
            partes_mb.append(("Outras", resto, "#DDD8E6"))
    else:
        linha = tabela_mb.loc["Areal"]
        partes_mb = [(f"{col} (MapBiomas)" if col != "Outras" else "Outras classes", linha[col],
                      CORES_WEB.get({v: k for k, v in CLASSES_MAPA.items()}.get(col), COR_OUTRAS_MB))
                     for col in linha.index]
    areal_mb_23 = partes_mb[0][1] if areal_por_mb else tabela_mb.loc["Areal"].get("Areal", 0.0)
    areal_mb_25 = areal_por_mb.get(25, 0.0) if areal_por_mb else None
    areal_mb_21 = areal_por_mb.get(21, 0.0) if areal_por_mb else None
    areal_mb_lav = (sum(areal_por_mb.get(k, 0.0) for k in GRUPOS_MB[3][1]) if areal_por_mb
                    else tabela_mb.loc["Areal"].get("Lavoura", 0.0))

    arquivo_sema = proc / f"comparacao_sema_{ano}.csv"
    tem_sema = arquivo_sema.exists()
    if tem_sema:
        sema = pd.read_csv(arquivo_sema, index_col=0)
        dentro = "Dentro dos areais da SEMA"
        area_sema = sema[dentro].sum()
        areal_dentro = sema.loc["Areal", dentro]
        partes_sema_areal = [("Dentro dos areais da SEMA", areal_dentro, CORES_WEB[1]),
                             ("Fora dos areais da SEMA", sema.loc["Areal"].sum() - areal_dentro, "#F1B9A6")]
        partes_sema_classes = [(c, sema.loc[c, dentro], CORES_WEB[k])
                               for k, c in CLASSES_MAPA.items() if c in sema.index]

    # --- Figuras e logos ---------------------------------------------------------------------------------
    figura_local = Path(pasta_figuras) / "localizacao_bacia.png"
    if figura_local.exists():
        shutil.copy(figura_local, web / "localizacao_bacia.png")
    figura_matriz = Path(pasta_figuras) / "matriz_confusao.png"
    if figura_matriz.exists():
        shutil.copy(figura_matriz, web / "matriz_confusao.png")

    # --- Trechos de HTML ---------------------------------------------------------------------------------
    legenda = "".join(
        f'<li class="item-classe" tabindex="0" data-classe="{c}" data-cor="{CORES_WEB[c]}">'
        f'<span class="cor" style="background:{CORES_WEB[c]}"></span>{CLASSES_MAPA[c]}'
        f'<span class="km">{br(areas.get(c, 0.0))} km²</span></li>' for c in [1, 2, 3, 4, 5, 6])

    # Polígonos em arquivos separados, carregados pela página com fetch()
    (web / f"areais_{ano}.geojson").write_text(areais_geojson, encoding="utf-8")
    (web / "bacia.geojson").write_text(bacia_geojson, encoding="utf-8")
    logos_html = "".join(f'<img src="{a}" alt="{html.escape(alt)}">' for a, alt in logos)

    if areal_por_mb:
        achado_mb = (
            f"Dos {br(area_areal)} km² de Areal deste mapa, {br(areal_mb_23)} km² também são areal no MapBiomas. "
            f"Outros {br(areal_mb_lav)} km² estão em talhões que o MapBiomas classifica como lavoura, "
            f"{br(areal_mb_25)} km² em <i>outras áreas não vegetadas</i> e {br(areal_mb_21)} km² em "
            f"<i>mosaico de usos</i>, classes em que o MapBiomas não define o tipo de solo exposto.")
    else:
        achado_mb = (f"Dos {br(area_areal)} km² de Areal deste mapa, {br(areal_mb_23)} km² também são areal no "
                     f"MapBiomas e {br(areal_mb_lav)} km² estão em talhões que ele classifica como lavoura.")

    if tem_sema:
        bloco_sema = f"""
      <div class="cartao-texto">
        <h3>Areal deste mapa e areais da SEMA-RS</h3>
        {_empilhada(partes_sema_areal, "Areal deste mapa dentro e fora dos areais da SEMA")}
        <h3>Como este mapa classifica os {br(area_sema)} km² de areais da SEMA-RS</h3>
        {_empilhada(partes_sema_classes, "Classes deste mapa dentro dos areais da SEMA")}
        <p class="nota">Parte dos areais da SEMA aparece como Campo: são áreas revegetadas desde o mapeamento
        ou areais com cobertura rala. A conferência visual separa os dois casos.</p>
      </div>"""
    else:
        bloco_sema = ""

    qc_linhas = "".join(
        f'<tr><td>{"Núcleo de areal" if s == "nucleo" else "Duvidoso" if s == "duvidoso" else "Sem dado"}</td>'
        f'<td class="num">{int(r.n)}</td><td class="num">{br(r.ha, 1)}</td></tr>'
        for s, r in qc_resumo.iterrows())

    dados_js = json.dumps({"assinatura": assinatura, "metricas": metricas, "importancia": dados_importancia},
                          ensure_ascii=False)

    trocas = {
        "__ANO_MB__": str(ano_mapbiomas) if tem_mb else "",
        "__ANO__": str(ano), "__SUL__": f"{sul:.6f}", "__NORTE__": f"{norte:.6f}",
        "__OESTE__": f"{oeste:.6f}", "__LESTE__": f"{leste:.6f}",
        "__V_AREA__": f"{area_areal:.2f}", "__V_PCT__": f"{100 * area_areal / area_total:.1f}",
        "__V_F1__": f"{f1_areal:.2f}", "__V_ACURACIA__": f"{principal['acuracia']:.2f}",
        "__AREA__": br(area_areal), "__PCT__": br(100 * area_areal / area_total, 1), "__F1__": br(f1_areal),
        "__ACURACIA__": br(principal["acuracia"]), "__F1_MACRO__": br(principal["f1_macro"]),
        "__ORIGEM_METRICAS__": "do mapa do Earth Engine" if metricas["ee"] else "do modelo (scikit-learn)",
        "__N_TREINO__": br(n_treino, 0), "__N_TESTE__": br(n_teste, 0),
        "__ARVORES__": str(int(melhor["param_n_estimators"])), "__PROFUNDIDADE__": profundidade,
        "__VAR_DIVISAO__": str(melhor["param_max_features"]).replace("sqrt", "raiz quadrada do total"),
        "__F1_CV__": br(melhor["mean_test_score"], 3), "__F1_CV_DP__": br(melhor["std_test_score"], 3),
        "__AREA_TOTAL__": br(area_total, 0),
        "__BARRAS_AREA__": _barras_area(areas),
        "__EMPILHADA_MB__": _empilhada(partes_mb, "Areal deste mapa nas classes do MapBiomas"),
        "__ACHADO_MB__": achado_mb,
        "__MATRIZ_MB__": _matriz_mapbiomas(tabela_mb),
        "__CONCORDANCIA_MB__": br(100 * concordancia_mb, 1),
        "__BLOCO_SEMA__": bloco_sema,
        "__QC_LINHAS__": qc_linhas,
        "__LEGENDA__": legenda, "__COR_OUTRAS__": COR_OUTRAS_MB, "__LOGOS__": logos_html, "__VENTO__": _vento(),
        "__TEM_MB__": json.dumps(bool(tem_mb)), "__PERIODOS__": json.dumps(list(periodos_s2), ensure_ascii=False),
        "__OPCOES_FUNDO__": (f'<option value="s2">Sentinel-2 {ano}</option>' if periodos_s2 else "")
                            + '<option value="esri">Satélite de alta resolução (Esri)</option>'
                              '<option value="osm">OpenStreetMap</option>',
        "__OPCOES_COMPARAR__": '<option value="">Nada (mapa inteiro)</option>'
                               + ('<option value="mapbiomas">MapBiomas 10 m</option>' if tem_mb else "")
                               + '<option value="fundo">Só a imagem de fundo</option>',
        "__REPO__": repo_url, "__SITE__": site_url,
        "__SERIE__": f"série de {ano} inteira" + (f" ({n_cenas} cenas)" if n_cenas else ""),
        "__FIGURA_MATRIZ__": ('<figure class="figura-matriz"><img src="matriz_confusao.png" alt="Matriz de confusão nos pontos de teste, com '
                              'as classes de referência nas linhas e as classes previstas nas colunas"><figcaption>'
                              'Matriz de confusão do modelo (scikit-learn) nos pontos de teste, com as sete classes do '
                              'treino: linhas são a classe de referência e colunas, a classe prevista. A Lavoura exposta é '
                              'juntada à Lavoura no mapa final.</figcaption></figure>' if figura_matriz.exists() else ""),
        "__FIGURA_LOCAL__": ('<figure><img src="localizacao_bacia.png" alt="Mapa de localização da ottobacia '
                             'Miracatu-Taquari no Rio Grande do Sul"><figcaption>Localização da ottobacia '
                             'Miracatu-Taquari (código 682636).</figcaption></figure>'
                             if figura_local.exists() else ""),
        "__DADOS__": dados_js,
    }
    pagina = MODELO
    for chave, valor in trocas.items():
        pagina = pagina.replace(chave, valor)
    (web / "index.html").write_text(pagina, encoding="utf-8")
    return web / "index.html"


MODELO = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Areais da ottobacia Miracatu-Taquari – __ANO__</title>
<meta name="description" content="Mapeamento das áreas de arenização na ottobacia Miracatu-Taquari (Pampa, RS) com Sentinel-2 e Random Forest.">
<meta property="og:type" content="website">
<meta property="og:locale" content="pt_BR">
<meta property="og:title" content="Areais da ottobacia Miracatu-Taquari – __ANO__">
<meta property="og:description" content="__AREA__ km² de areal (__PCT__% da bacia) mapeados com Sentinel-2 e Random Forest no Pampa gaúcho.">
<meta property="og:url" content="__SITE__">
<meta property="og:image" content="__SITE__classes___ANO__.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="logo_ftl.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@600;700&display=swap">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  :root {
    --roxo: #4617DE; --limao: #DDFB0B;
    --fundo: #FAF6EF; --superficie: #EADFCB; --duna: #C9B48F;
    --texto: #1E1B2E; --texto-suave: #5C566E; --link: #4617DE; --numero: #1E1B2E;
    --calor: 70, 23, 222;
    --sombra: 0 2px 10px rgba(30, 27, 46, 0.08);
    --curva: cubic-bezier(0.2, 0.7, 0.2, 1);
    --titulo: "Space Grotesk", system-ui, sans-serif;
    --corpo: "Inter", system-ui, sans-serif;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --fundo: #15122B; --superficie: #221D40; --duna: #4A4270;
      --texto: #EDEAF5; --texto-suave: #B7B1CC; --link: #A48CFF; --numero: #DDFB0B;
      --calor: 164, 140, 255;
      --sombra: 0 2px 10px rgba(0, 0, 0, 0.35);
    }
  }
  * { box-sizing: border-box; }
  [hidden] { display: none !important; }
  html { scroll-behavior: smooth; scroll-padding-top: 64px; }
  body { margin: 0; background: var(--fundo); color: var(--texto); font: 400 16px/1.6 var(--corpo); }
  a { color: var(--link); }
  a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible {
    outline: 2px solid var(--roxo); outline-offset: 2px; }
  h1, h2, h3 { font-family: var(--titulo); margin: 0; }
  h2 { font-size: 28px; font-weight: 700; margin-bottom: 16px; }
  h3 { font-size: 20px; font-weight: 600; margin: 24px 0 8px; }
  .num, .valor, .cartao b, td { font-variant-numeric: tabular-nums; }

  .topo { display: flex; justify-content: space-between; align-items: center; gap: 24px; padding: 24px 32px 16px; }
  .sobre { margin: 0 0 4px; font-size: 13px; color: var(--texto-suave); }
  .topo h1 { font-size: 40px; line-height: 1.1; font-weight: 700; }
  .topo .sub { margin: 8px 0 0; color: var(--texto-suave); }
  .selo { display: inline-block; vertical-align: middle; margin-left: 8px; padding: 2px 12px; border-radius: 999px;
          background: var(--roxo); color: #fff; font: 600 16px var(--titulo); }
  @media (prefers-color-scheme: dark) { .selo { background: var(--limao); color: #15122B; } }
  .logos { display: flex; gap: 16px; align-items: center; }
  .logos img { height: 56px; max-width: 100%; object-fit: contain; }
  @media (prefers-color-scheme: dark) { .logos { background: #FAF6EF; padding: 8px 16px; border-radius: 14px; } }
  .vento { display: block; width: 100%; height: 24px; }
  .vento path { fill: none; stroke: var(--duna); stroke-width: 1.5; vector-effect: non-scaling-stroke; }

  .menu { position: sticky; top: 0; z-index: 2000; background: var(--fundo); border-bottom: 1px solid var(--duna); }
  .menu ul { display: flex; gap: 4px; list-style: none; margin: 0 auto; padding: 8px 32px; overflow-x: auto; }
  .menu a { display: block; padding: 4px 12px; border-radius: 999px; text-decoration: none; font-size: 14px;
            white-space: nowrap; transition: background 200ms var(--curva), color 200ms var(--curva); }
  .menu a.ativo { background: var(--roxo); color: #fff; }

  .numeros { display: flex; flex-wrap: wrap; gap: 16px; padding: 16px 32px; }
  .cartao { background: var(--superficie); border-radius: 14px; box-shadow: var(--sombra); padding: 16px 24px; min-width: 180px; }
  .cartao b { display: block; font: 700 40px/1.1 var(--titulo); color: var(--numero); }
  .cartao span { font-size: 13px; color: var(--texto-suave); }

  .area-mapa { position: relative; height: 72vh; min-height: 420px; margin: 0 32px; border-radius: 14px; overflow: hidden; box-shadow: var(--sombra); }
  #mapa { position: absolute; inset: 0; }
  .painel { position: absolute; z-index: 1000; background: var(--superficie); color: var(--texto); border-radius: 14px;
            box-shadow: var(--sombra); padding: 8px 16px; font-size: 13px; }
  .legenda { left: 16px; bottom: 24px; max-width: 280px; }
  .legenda summary { font: 600 16px var(--titulo); cursor: pointer; padding: 4px 0; }
  .legenda ul { list-style: none; margin: 4px 0 8px; padding: 0; }
  .legenda li { display: flex; align-items: center; gap: 8px; padding: 2px 4px; margin: 0 -4px; border-radius: 6px;
                transition: opacity 200ms var(--curva), background 200ms var(--curva); }
  .item-classe { cursor: pointer; }
  .item-classe:focus-visible { outline: 2px solid var(--roxo); outline-offset: 0; }
  .legenda ul.destacando .item-classe { opacity: 0.4; }
  .legenda ul.destacando .item-classe.ativo { opacity: 1; background: color-mix(in srgb, var(--roxo) 14%, transparent); }
  .imagem-s2 { transition: opacity 400ms var(--curva); }
  .cartao .explica { display: block; max-width: 220px; margin-top: 4px; font-size: 12px; line-height: 1.35; color: var(--texto-suave); }
  .quadro { font-size: 14px; min-width: 620px; }
  .quadro th[scope=row] { font-weight: 600; white-space: nowrap; position: sticky; left: 0; z-index: 1; background: var(--fundo); }
  .figura-matriz img { display: block; max-width: 620px; margin: 0 auto; background: #fff; }
  .quadro th.projeto { background: var(--roxo); color: #fff; border-radius: 8px 8px 0 0; }
  .quadro td.projeto { background: color-mix(in srgb, var(--roxo) 12%, transparent); font-weight: 500; }
  .trabalhos { display: grid; gap: 8px; margin-top: 16px; }
  .trabalhos summary { font: 600 16px var(--titulo); cursor: pointer; }
  .trabalhos p { margin: 8px 0 0; font-size: 15px; }
  .cita { text-decoration: underline dotted; text-underline-offset: 3px; cursor: help; }
  .balao { position: absolute; z-index: 3000; max-width: min(340px, calc(100vw - 16px)); background: var(--superficie);
           color: var(--texto); border-radius: 14px; box-shadow: 0 4px 18px rgba(30, 27, 46, 0.22); padding: 12px 16px;
           font-size: 13px; line-height: 1.45; opacity: 0; transform: translateY(4px);
           transition: opacity 150ms var(--curva), transform 150ms var(--curva); }
  .balao.visivel { opacity: 1; transform: none; }
  .balao .botao-doi { display: inline-block; margin-top: 8px; padding: 4px 12px; border-radius: 999px; background: var(--roxo);
                      color: #fff; text-decoration: none; font-weight: 500; }
  .linha-tempo { display: flex; flex-direction: column; gap: 4px; }
  .tempo { display: flex; align-items: center; gap: 8px; }
  .controles .tempo input[type=range] { flex: 1; width: auto; min-width: 0; }
  .botao-play { flex: none; display: grid; place-items: center; width: 32px; height: 32px; padding: 0; border: none;
                border-radius: 999px; background: var(--roxo); color: #fff; cursor: pointer;
                transition: transform 200ms var(--curva); }
  .botao-play:hover { transform: scale(1.06); }
  .botao-play svg { width: 14px; height: 14px; fill: currentColor; }
  .botao-play .icone-pausa, .botao-play[aria-pressed=true] .icone-play { display: none; }
  .botao-play[aria-pressed=true] .icone-pausa { display: inline; }
  @media (prefers-reduced-motion: reduce) {
    .imagem-s2, .legenda li, .botao-play, .barra, .bigode, .menu a, .botao, .balao { transition: none; }
    html { scroll-behavior: auto; }
  }
  .cor { display: inline-block; width: 14px; height: 14px; border-radius: 4px; flex: none; border: 1px solid rgba(0, 0, 0, 0.2); }
  .legenda .km { margin-left: auto; padding-left: 16px; color: var(--texto-suave); }
  .controles { left: 16px; top: 16px; }
  .controles summary { font: 600 14px var(--titulo); cursor: pointer; padding: 4px 0; }
  .conteudo-controles { display: flex; flex-direction: column; gap: 8px; padding: 4px 0 8px; }
  .controles label { display: flex; flex-direction: column; gap: 4px; }
  .controles input[type=range] { accent-color: var(--roxo); width: 220px; }
  .controles .seletor { width: 220px; font-size: 13px; }
  .dica { max-width: 980px; margin: 8px auto 0; padding: 0 32px; font-size: 13px; color: var(--texto-suave); }
  .botao { font: 500 13px var(--corpo); border-radius: 999px; padding: 6px 16px; cursor: pointer; border: 2px solid var(--roxo);
           background: transparent; color: var(--link); transition: background 200ms var(--curva), color 200ms var(--curva); }
  .botao[aria-pressed=true] { background: var(--roxo); color: #fff; }
  .divisor { position: absolute; z-index: 900; left: 0; top: 50%; width: 100%; height: 36px; margin: 0; transform: translateY(-50%);
             -webkit-appearance: none; appearance: none; background: transparent; pointer-events: none; }
  .divisor::-webkit-slider-runnable-track { background: transparent; }
  .divisor::-webkit-slider-thumb { -webkit-appearance: none; pointer-events: auto; width: 36px; height: 36px; border-radius: 999px;
                                   background: var(--roxo); border: 3px solid #fff; cursor: ew-resize; box-shadow: var(--sombra); }
  .divisor::-moz-range-thumb { pointer-events: auto; width: 30px; height: 30px; border-radius: 999px; background: var(--roxo);
                               border: 3px solid #fff; cursor: ew-resize; }
  .linha { position: absolute; z-index: 899; top: 0; bottom: 0; width: 3px; margin-left: -1.5px; background: #fff; pointer-events: none; }
  .lado { position: absolute; z-index: 899; top: 140px; padding: 2px 12px; border-radius: 999px; background: rgba(21, 18, 43, 0.75);
          color: #fff; font-size: 13px; pointer-events: none; }

  .secao { max-width: 980px; margin: 0 auto; padding: 32px 32px 0; }
  .secao > p, .secao li { max-width: 72ch; }
  .grade { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
  .cartao-texto { background: var(--superficie); border-radius: 14px; box-shadow: var(--sombra); padding: 16px 24px; }
  .cartao-texto h3:first-child { margin-top: 0; }
  .nota { font-size: 13px; color: var(--texto-suave); }
  figure { margin: 16px 0; }
  figure img { width: 100%; border-radius: 14px; }
  figcaption { font-size: 13px; color: var(--texto-suave); margin-top: 4px; }

  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--duna); vertical-align: top; }
  thead th { font-weight: 600; }
  td.num, th.num { text-align: right; }
  .rolagem { overflow-x: auto; }

  .passos { list-style: none; counter-reset: passo; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; }
  .passos li { counter-increment: passo; background: var(--superficie); border-radius: 14px; padding: 16px; box-shadow: var(--sombra); }
  .passos li::before { content: counter(passo); display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 999px;
                       background: var(--roxo); color: #fff; font: 600 14px var(--titulo); margin-bottom: 8px; }
  .passos b { display: block; font-family: var(--titulo); }
  .passos span { font-size: 14px; color: var(--texto-suave); }
  .formula { font-family: ui-monospace, monospace; font-size: 14px; }

  .barra-linha { display: grid; grid-template-columns: 150px 1fr 150px; align-items: center; gap: 8px; padding: 3px 0; font-size: 14px; }
  .trilho { position: relative; height: 14px; border-radius: 999px; background: color-mix(in srgb, var(--duna) 35%, transparent); }
  .barra { position: absolute; top: 0; bottom: 0; border-radius: 999px; transition: left 200ms var(--curva), width 200ms var(--curva); }
  .bigode { position: absolute; top: 6px; height: 2px; background: var(--texto); opacity: 0.55; transition: left 200ms var(--curva), width 200ms var(--curva); }
  .zero { position: absolute; top: -3px; bottom: -3px; width: 1px; background: var(--texto-suave); }
  .valor { text-align: right; color: var(--texto-suave); }
  .abas { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 16px; }
  .seletor { font: 500 14px var(--corpo); padding: 6px 12px; border-radius: 999px; border: 2px solid var(--roxo);
             background: var(--fundo); color: var(--texto); }

  .empilhada { display: flex; height: 28px; border-radius: 999px; overflow: hidden; margin: 8px 0; }
  .empilhada span { height: 100%; }
  .legenda-empilhada { list-style: none; padding: 0; margin: 0 0 8px; display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 13px; }
  .legenda-empilhada li { display: flex; align-items: center; gap: 6px; }
  .legenda-empilhada b { font-weight: 600; }

  .matriz { font-size: 13px; }
  .matriz th, .matriz td { text-align: center; border: none; padding: 6px; }
  .matriz tbody th { text-align: left; }
  .calor { background: rgba(var(--calor), calc(var(--a) * 0.9)); border-radius: 4px; }
  .calor.escura { color: #fff; }
  @media (prefers-color-scheme: dark) { .calor.escura { color: #15122B; } }

  .rodape { padding: 8px 32px 32px; font-size: 13px; color: var(--texto-suave); }
  .rodape p { margin: 4px 0; max-width: 980px; }

  @media (max-width: 700px) {
    .topo { flex-direction: column; align-items: flex-start; padding: 16px; }
    .topo h1 { font-size: 28px; }
    .logos img { height: auto; width: 100%; max-width: 360px; }
    .menu ul { padding: 8px 16px; }
    .numeros { padding: 16px; gap: 8px; }
    .cartao { flex: 1 1 140px; min-width: 0; padding: 8px 16px; }
    .cartao b { font-size: 28px; }
    .area-mapa { margin: 0; border-radius: 0; height: 75vh; }
    .legenda { left: 8px; right: 8px; bottom: 8px; max-width: none; }
    .controles { left: 8px; top: 8px; }
    .secao { padding: 24px 16px 0; }
    .barra-linha { grid-template-columns: 100px 1fr 96px; font-size: 13px; }
    .rodape { padding: 8px 16px 24px; }
  }
</style>
</head>
<body>
<header class="topo">
  <div>
    <p class="sobre">Future Tech Leaders Brasil · Space Tech Bootcamp 2026</p>
    <h1>Areais da ottobacia Miracatu-Taquari<span class="selo">__ANO__</span></h1>
    <p class="sub">Mapeamento de áreas de arenização com Sentinel-2 e Random Forest · Franqueline Monback Noschang</p>
  </div>
  <div class="logos">__LOGOS__</div>
</header>
__VENTO__
<nav class="menu" aria-label="Seções">
  <ul>
    <li><a href="#mapa-secao">Mapa</a></li>
    <li><a href="#contexto">Contexto</a></li>
    <li><a href="#dados">Dados</a></li>
    <li><a href="#metodo">Método</a></li>
    <li><a href="#resultados">Resultados</a></li>
    <li><a href="#validacao">Validação</a></li>
    <li><a href="#comparacao">Comparação</a></li>
    <li><a href="#limitacoes">Limitações</a></li>
    <li><a href="#referencias">Referências</a></li>
  </ul>
</nav>

<section id="mapa-secao" aria-label="Mapa e números principais">
  <div class="numeros">
    <div class="cartao"><b data-valor="__V_AREA__" data-casas="2">__AREA__</b><span>km² de areal</span></div>
    <div class="cartao"><b data-valor="__V_PCT__" data-casas="1" data-sufixo="%">__PCT__%</b><span>da bacia (__AREA_TOTAL__ km²)</span></div>
    <div class="cartao"><b data-valor="__V_F1__" data-casas="2">__F1__</b><span>F1 do Areal no teste</span>
      <small class="explica">F1: equilíbrio entre encontrar os areais e não marcar areal onde não existe (de 0 a 1).</small></div>
    <div class="cartao"><b data-valor="__V_ACURACIA__" data-casas="2">__ACURACIA__</b><span>acurácia global no teste</span></div>
  </div>
  <div class="area-mapa">
    <div id="mapa" aria-label="Mapa da classificação de cobertura da terra"></div>
    <details class="painel controles" id="controles" open>
      <summary>Camadas e linha do tempo</summary>
      <div class="conteudo-controles">
      <label>Fundo<select class="seletor" id="fundo">__OPCOES_FUNDO__</select></label>
      <div id="ctrl-periodo" class="linha-tempo" hidden>
        <span>Período: <b id="rotulo-periodo" aria-live="polite"></b></span>
        <div class="tempo">
          <button type="button" class="botao-play" id="play" aria-pressed="false" aria-label="Reproduzir a linha do tempo">
            <svg viewBox="0 0 16 16" aria-hidden="true"><path class="icone-play" d="M4 2.5v11l9-5.5z"/><path class="icone-pausa" d="M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z"/></svg>
          </button>
          <input type="range" id="periodo" min="0" max="0" value="0" aria-label="Período da imagem Sentinel-2">
        </div>
      </div>
      <label>Opacidade das classes<input type="range" id="opacidade" min="0" max="100" value="75"></label>
      <label>Comparar lado a lado com<select class="seletor" id="comparar-com">__OPCOES_COMPARAR__</select></label>
      </div>
    </details>
    <input type="range" class="divisor" id="divisor" min="0" max="100" value="50" aria-label="Divisão entre os mapas" hidden>
    <div class="linha" id="linha" hidden></div>
    <span class="lado" id="lado-esq" style="left: 16px" hidden>Este mapa</span>
    <span class="lado" id="lado-dir" style="right: 16px" hidden></span>
    <details class="painel legenda" id="legenda" open>
      <summary>Legenda</summary>
      <ul>__LEGENDA__<li id="leg-outras" hidden><span class="cor" style="background:__COR_OUTRAS__"></span>Outras classes do MapBiomas</li></ul>
    </details>
  </div>
  <p class="dica">Para conferir o resultado, use o fundo <b>Sentinel-2 __ANO__</b>, a mesma base da classificação, e
  compare lado a lado com o MapBiomas ou com a imagem sem classes. Mova o <b>período da imagem</b> pelos bimestres: o
  areal fica exposto o ano todo; a lavoura, só em parte dele. A partir do zoom 14, as manchas de areal ganham contorno
  e mostram a área ao clicar.</p>
</section>

<section class="secao" id="contexto">
  __VENTO__
  <h2>Contexto</h2>
  <p>A <b>arenização</b> é o principal processo de degradação do solo no Pampa gaúcho: em substratos arenosos frágeis,
  a perda da vegetação forma manchas de areia exposta, os <b>areais</b>. Os mapeamentos existentes usam imagens de 30 m
  ou classes genéricas de "área não vegetada", sem separar o areal de outros solos expostos, sobretudo da
  <b>lavoura em preparo de solo</b>, que tem resposta espectral parecida numa única data.</p>
  <p>Este projeto mapeia os areais existentes em __ANO__ na ottobacia <b>Miracatu-Taquari</b> (código 682636, nível 6 da ANA,
  __AREA_TOTAL__ km², entre Manoel Viana e São Francisco de Assis, sudoeste do RS) com imagens Sentinel-2 a 10 m e
  Random Forest. A diferença em relação aos mapeamentos anteriores é usar a <b>série do ano inteiro</b>: o areal fica
  exposto quase o ano todo; a lavoura, só em parte dele.</p>
  <div class="grade">
    <div class="cartao-texto">
      <h3>Objetivos de Desenvolvimento Sustentável</h3>
      <p><b>ODS 15 – Vida Terrestre</b>, meta 15.3: saber onde estão os areais é o primeiro passo para priorizar
      manejo e recuperação. <b>ODS 2</b>: a arenização reduz a área útil para pecuária e lavoura.
      <b>ODS 13</b>: o inventário é a linha de base para acompanhar o efeito de chuvas intensas e do vento.</p>
    </div>
    <div class="cartao-texto">
      <h3>Produtos</h3>
      <p>Mapa de classificação de __ANO__ (GeoTIFF, 10 m), polígonos de areais (shapefile), código aberto e
      reprodutível e este mapa web.</p>
    </div>
  </div>
  <p>O inventário será a base de validação de um mapa de suscetibilidade à arenização por Análise Hierárquica de
  Processos (AHP), em desenvolvimento no mestrado em Geografia da UFSM.</p>
  __FIGURA_LOCAL__

  <h3>Trabalhos relacionados</h3>
  <p><a class="cita" href="#ref-suertegaray1992">Suertegaray (1992)</a> propôs o termo <b>arenização</b> para os areais do
  sudoeste gaúcho: em clima úmido, a degradação não é desertificação, e sim o retrabalhamento de depósitos arenosos pouco
  consolidados, em que a areia em movimento dificulta a fixação da vegetação.
  <a class="cita" href="#ref-souza2017">Souza e Pires (2017)</a> mapearam os areais do Arroio Puitã entre 1984 e 2014 com
  imagens Landsat e Máxima Verossimilhança, uma imagem por data; a transição entre campo e areal, de vegetação rala, saiu
  como solo exposto, com resposta parecida com a de solo em cultivo inicial.
  <a class="cita" href="#ref-rayne2023">Rayne et al. (2023)</a> detectaram campos desertificados no Marrocos com
  Sentinel-2, Google Earth Engine e Random Forest, com acurácias de 74% a 76% na classe de desertificação. Este projeto
  une as duas linhas: aplica o método de Rayne et al. ao problema regional, com 10 m de resolução e a série do ano
  inteiro, para separar o areal da lavoura.</p>
  <div class="rolagem"><table class="quadro">
    <thead><tr><th scope="col">Critério</th><th scope="col">Souza e Pires (2017)</th><th scope="col">Rayne et al. (2023)</th>
      <th scope="col" class="projeto">Este projeto</th></tr></thead>
    <tbody>
      <tr><th scope="row">Local</th><td>Arroio Puitã, RS</td><td>Oásis do sul do Marrocos</td><td class="projeto">Ottobacia Miracatu-Taquari, RS</td></tr>
      <tr><th scope="row">Sensor e resolução</th><td>Landsat, 30 m</td><td>Sentinel-2 e Sentinel-1, 10 m</td><td class="projeto">Sentinel-2, 10 m</td></tr>
      <tr><th scope="row">Tempo</th><td>1 imagem por data (1984–2014)</td><td>mediana de jun–ago 2021</td><td class="projeto">__SERIE__</td></tr>
      <tr><th scope="row">Classificador</th><td>Máxima Verossimilhança</td><td>Random Forest (GEE)</td><td class="projeto">Random Forest (GEE)</td></tr>
      <tr><th scope="row">Acurácia do alvo</th><td>—</td><td>74–76%</td><td class="projeto">F1 do Areal de __F1__</td></tr>
      <tr><th scope="row">Limite</th><td>transição campo–areal confundida com cultivo</td><td>uma estação só</td><td class="projeto">sem verificação de campo</td></tr>
    </tbody>
  </table></div>
  <div class="trabalhos">
    <details class="cartao-texto">
      <summary>Suertegaray (1992)</summary>
      <p><b>O que fez:</b> definiu a arenização como um processo próprio do clima úmido do sudoeste gaúcho, distinto da
      desertificação: o retrabalhamento de depósitos arenosos pouco consolidados.</p>
      <p><b>O que aproveitamos:</b> o conceito, que define o alvo do mapa: areia exposta sobre depósitos arenosos, com
      dificuldade de fixação da vegetação.</p>
      <p><b>A lacuna:</b> o conceito precisa de um inventário atualizado e reprodutível dos areais, que é o que este
      projeto produz.</p>
    </details>
    <details class="cartao-texto">
      <summary>Souza e Pires (2017)</summary>
      <p><b>O que fizeram:</b> o mapeamento multitemporal dos areais do Arroio Puitã de 1984 a 2014, com Landsat e
      Máxima Verossimilhança, uma imagem por data.</p>
      <p><b>O que aproveitamos:</b> a referência regional da dinâmica dos areais e o alerta de que a transição
      campo–areal se parece com solo em cultivo inicial.</p>
      <p><b>A lacuna:</b> com uma data e 30 m, o areal não se separa do solo exposto agrícola.</p>
    </details>
    <details class="cartao-texto">
      <summary>Rayne et al. (2023)</summary>
      <p><b>O que fizeram:</b> detectaram campos desertificados em oásis do sul do Marrocos com Sentinel-2 e Sentinel-1,
      Google Earth Engine e Random Forest, sobre a mediana de jun–ago 2021.</p>
      <p><b>O que aproveitamos:</b> o fluxo Sentinel-2, Earth Engine e Random Forest e o parâmetro realista de acurácia
      (74–76% na classe-alvo).</p>
      <p><b>A lacuna:</b> uma estação só, em clima árido. Aqui a série do ano inteiro separa o areal, exposto o ano
      todo, da lavoura, exposta só em parte dele.</p>
    </details>
  </div>
</section>

<section class="secao" id="dados">
  __VENTO__
  <h2>Dados</h2>
  <div class="rolagem"><table>
    <thead><tr><th>Dado</th><th>Fonte</th><th>Uso</th></tr></thead>
    <tbody>
      <tr><td>Sentinel-2 L2A, reflectância de superfície, cenas de __ANO__</td><td>ESA/Copernicus, via Google Earth Engine</td><td>Índices espectrais e variáveis do modelo</td></tr>
      <tr><td>Cloud Score+</td><td>Google, via Earth Engine</td><td>Máscara de nuvens</td></tr>
      <tr><td>Limite da ottobacia 682636</td><td>ANA – Base Hidrográfica Ottocodificada</td><td>Recorte da área de estudo</td></tr>
      <tr><td>MapBiomas 10 m, Coleção 4</td><td>MapBiomas</td><td>Apoio à amostragem, controle de qualidade e comparação</td></tr>
      <tr><td>Mapeamento de areais do RS</td><td>SEMA-RS</td><td>Localização dos areais, controle de qualidade e comparação</td></tr>
      <tr><td>Amostras rotuladas (polígonos)</td><td>Interpretação visual neste projeto</td><td>Treino e teste</td></tr>
    </tbody>
  </table></div>
  <p class="nota">O MapBiomas e a SEMA-RS ajudaram a localizar os areais, mas nunca foram usados como rótulo direto:
  cada amostra foi conferida na imagem de alta resolução e nas seis medianas bimestrais do Sentinel-2.</p>
</section>

<section class="secao" id="metodo">
  __VENTO__
  <h2>Método</h2>
  <ol class="passos">
    <li><b>Imagens</b><span>Todas as cenas Sentinel-2 de __ANO__ sobre a bacia, com nuvens mascaradas pelo Cloud Score+.</span></li>
    <li><b>Índices por cena</b><span>NDVI, BSI, NDWI e uma marcação de solo exposto (NDVI &lt; 0,25, BSI &gt; 0 e NDWI &lt; 0).</span></li>
    <li><b>Variáveis anuais</b><span>Medianas das bandas, estatísticas do NDVI, BSI e NDWI medianos e a frequência de solo exposto no ano: 14 variáveis por pixel.</span></li>
    <li><b>Amostras</b><span>Polígonos desenhados em SIG e revisados; os areais passam por controle de qualidade.</span></li>
    <li><b>Treino e teste</b><span>Divisão espacial 70/30 por grupos de polígonos vizinhos; __N_TREINO__ pontos de treino e __N_TESTE__ de teste.</span></li>
    <li><b>Random Forest</b><span>Hiperparâmetros por validação cruzada espacial; classificação da bacia no Earth Engine e filtro entre Silvicultura e Vegetação Nativa.</span></li>
  </ol>

  <h3>Por que a série do ano inteiro separa areal e lavoura</h3>
  <p>Numa única data, areal e lavoura em preparo de solo são parecidos. No ano, não: o areal fica exposto em boa parte
  das cenas e tem NDVI baixo e estável; a lavoura alterna solo exposto e vegetação densa. Talhões expostos quase o ano
  todo (pousio, palhada) foram treinados como uma subclasse, <b>Lavoura exposta</b>, e juntados à Lavoura no mapa final.
  O gráfico mostra a mediana de cada classe nas amostras (barra) e o intervalo entre os quartis 25% e 75% (traço).</p>
  <div class="abas" id="abas-assinatura" role="tablist" aria-label="Variável"></div>
  <div id="grafico-assinatura"></div>

  <h3>Índices</h3>
  <div class="grade">
    <div class="cartao-texto formula">NDVI = (NIR − Vermelho) / (NIR + Vermelho)</div>
    <div class="cartao-texto formula">BSI = ((SWIR1 + Vermelho) − (NIR + Azul)) / ((SWIR1 + Vermelho) + (NIR + Azul))</div>
    <div class="cartao-texto formula">NDWI = (Verde − NIR) / (Verde + NIR)</div>
  </div>

  <h3>Controle de qualidade dos areais</h3>
  <p>Cada polígono de areal foi medido no próprio Sentinel-2: é <b>núcleo de areal</b> se ficou exposto em pelo menos
  metade das cenas e tem NDVI médio até 0,30; os demais são <b>duvidosos</b> e foram revisados um a um. O controle de
  qualidade nunca filtra o teste, para não deixar só os casos fáceis e inflar a acurácia.</p>
  <div class="rolagem"><table>
    <thead><tr><th>Polígonos de areal nas amostras</th><th class="num">Polígonos</th><th class="num">Área (ha)</th></tr></thead>
    <tbody>__QC_LINHAS__</tbody>
  </table></div>

  <h3>Modelo</h3>
  <p>Random Forest com __ARVORES__ árvores, profundidade máxima __PROFUNDIDADE__ e número de variáveis por divisão igual à
  __VAR_DIVISAO__, escolhidos por validação cruzada espacial de 5 dobras (F1 macro de __F1_CV__ ± __F1_CV_DP__).
  O Random Forest funciona bem com poucas centenas de polígonos e variáveis tabulares, é robusto a variáveis
  correlacionadas, indica a importância de cada variável e roda no próprio Earth Engine.</p>
  <p>Depois da classificação, um filtro espacial remove o salpicado de pixels soltos: manchas de Silvicultura e de
  Vegetação Nativa menores que 1 ha (as duas classes são espectralmente parecidas e trocavam pixels entre si) e
  manchas de Água menores que 0,2 ha passam para a classe predominante ao redor. Uma mata nativa pequena só vira
  silvicultura se estiver dentro de um talhão, para não apagar capões reais, e o limite da Água é baixo para manter
  os açudes. Areal, Campo e Lavoura não são filtrados, para manter os pequenos focos de areal.</p>
</section>

<section class="secao" id="resultados">
  __VENTO__
  <h2>Resultados</h2>
  <p>O mapa identificou <b>__AREA__ km² de areal</b>, __PCT__% da bacia. Campo e lavoura dominam a paisagem.</p>
  <div class="cartao-texto">__BARRAS_AREA__</div>
  <p class="nota">Área calculada pela contagem de pixels de 10 m na bacia.</p>

  <h3>Quais variáveis mais pesam em cada classe</h3>
  <p>Importância por permutação: quanto o acerto do modelo em cada classe cai quando os valores de uma variável são
  embaralhados. Variáveis correlacionadas dividem a importância entre si, por isso valores baixos não significam que a
  variável seja inútil.</p>
  <label class="nota">Classe <select class="seletor" id="seletor-importancia"></select></label>
  <div id="grafico-importancia" style="margin-top: 12px"></div>
</section>

<section class="secao" id="validacao">
  __VENTO__
  <h2>Validação</h2>
  <p>Acurácia global de <b>__ACURACIA__</b> e F1 macro de <b>__F1_MACRO__</b> nos pontos de teste (__ORIGEM_METRICAS__),
  que ficam em polígonos separados dos de treino. O F1 do Areal é <b>__F1__</b>; a classe mais difícil é o Campo, que se
  confunde com a lavoura e com areais revegetados.</p>
  <div class="abas" id="abas-metricas" role="tablist" aria-label="Conjunto de métricas"></div>
  <div class="rolagem"><table id="tabela-metricas"></table></div>
  <p class="nota">Os pontos de teste vêm de áreas típicas de cada classe e têm o mesmo número por classe. A acurácia do
  mapa inteiro, que inclui bordas e pixels mistos e classes de tamanhos muito diferentes, tende a ser menor.</p>
  __FIGURA_MATRIZ__
  <div class="cartao-texto">
    <h3>A lição do processo</h3>
    <p>A primeira versão do mapa tinha mais de 90% de acurácia no teste, mas marcava 19% da bacia como areal. A
    comparação com o MapBiomas revelou o excesso, e a revisão das amostras (areais duvidosos reclassificados e amostras
    de Lavoura exposta) reduziu o areal para __PCT__% da bacia. <b>Acurácia alta no teste não garante um bom mapa:</b>
    o teste mede o modelo em amostras típicas; a comparação com referências mede o mapa inteiro.</p>
  </div>
</section>

<section class="secao" id="comparacao">
  __VENTO__
  <h2>Comparação com o MapBiomas e a SEMA-RS</h2>
  <p>A concordância geral com o MapBiomas 10 m é de <b>__CONCORDANCIA_MB__%</b> da área da bacia. No Areal, a concordância
  é menor, e parte da diferença vem de como cada base classifica: o MapBiomas classifica o <b>uso</b> da terra (um talhão inteiro é lavoura,
  mesmo com uma mancha de areia dentro) e a SEMA-RS mapeou os areais consolidados, em escala mais grosseira. Este mapa
  classifica a <b>cobertura</b> pixel a pixel, a 10 m.</p>
  <div class="cartao-texto">
    <h3>Onde está o Areal deste mapa, segundo o MapBiomas</h3>
    __EMPILHADA_MB__
    <p>__ACHADO_MB__</p>
    <p>A conferência visual de 30 a 50 manchas em conflito com a lavoura do MapBiomas mostrou solo arenoso exposto na
    maior parte delas.</p>
    <p>Os solos do substrato arenoso da bacia são "muito frágeis e altamente suceptíveis [sic] à erosão hídrica"
    (<a class="cita" href="#ref-suertegaray2011">Suertegaray, 2011, p. 69</a>): quando a cobertura é removida, a "expansão lateral e remontante das ravinas e
    voçorocas, promove a formação do areal propriamente dito" (<a class="cita" href="#ref-suertegaray2011">idem</a>), e a "constante mobilidade dos sedimentos"
    dificulta a volta da vegetação (<a class="cita" href="#ref-suertegaray2011">Suertegaray, 2011, p. 62</a>). Por isso, as manchas de solo arenoso exposto
    encontradas dentro de lavouras são <b>áreas fragilizadas, com possíveis focos de arenização</b>; parte ainda pode
    ser manejo (pousio, preparo do solo), e a confirmação em campo é o próximo passo.</p>
    <p>A literatura sustenta essa leitura. A arenização é o "retrabalhamento de depósitos areníticos (pouco
    consolidados) ou arenosos (não consolidados)" (<a class="cita" href="#ref-suertegaray2011">Suertegaray, 2011, p. 62</a>), e "este processo poderá ser
    desencadeado por agentes naturais ou atividades humanas" (<a class="cita" href="#ref-suertegaray2011">Suertegaray, 2011, p. 69</a>). Numa área piloto entre
    São Francisco de Assis e Manoel Viana, a mesma região desta bacia, na frente de expansão da soja, a análise
    multitemporal registrou aumento de 47,52 ha de areais em 25 anos, resultados que "indicam o surgimento de novas
    manchas de areia (areais)" (Suertegaray; Guasselli; Franz, 1995 apud <a class="cita" href="#ref-suertegaray2011">Suertegaray, 2011, p. 69</a>). Ravinas e
    sulcos também podem resultar do "uso de maquinaria pesada na atividade agrícola"
    (<a class="cita" href="#ref-suertegaray2011">Suertegaray, 2011, p. 64</a>).</p>
  </div>
  __BLOCO_SEMA__
  <h3>Matriz de concordância</h3>
  <p class="nota">Cada linha é uma classe deste mapa; as colunas mostram como a mesma área aparece no MapBiomas (% da
  linha). Passe o mouse para ver a área em km².</p>
  <div class="rolagem">__MATRIZ_MB__</div>
</section>

<section class="secao" id="limitacoes">
  __VENTO__
  <h2>Limitações e próximos passos</h2>
  <ul>
    <li>A acurácia vem de amostras em áreas típicas de cada classe, sem verificação de campo. Uma amostra aleatória
    estratificada sobre o mapa permitiria estimar a acurácia sem esse viés e corrigir a área por classe
    (<a class="cita" href="#ref-olofsson2014">Olofsson et al., 2014</a>).</li>
    <li>A área é a contagem de pixels; ainda não tem intervalo de confiança.</li>
    <li>Talhões expostos quase o ano todo ainda podem se parecer com areal. Variáveis de textura ou classificação por
    objetos (segmentação) podem reduzir essa confusão.</li>
    <li>O Campo é a classe com menor acerto e se confunde com lavoura e com areais revegetados.</li>
    <li>A Água ainda ocupa mais área que no MapBiomas: quase toda a água real é encontrada, mas banhados, várzeas e
    sombras de mata ciliar também aparecem como água. Uma variável de frequência de água (fração das cenas com água)
    separaria os corpos d'água permanentes das áreas úmidas temporárias.</li>
    <li>A resolução de 10–20 m não captura areais muito pequenos ou estreitos, e areais sob silvicultura não aparecem.</li>
    <li>O mapa cobre um único ano. Aplicar o mesmo fluxo a anos anteriores permitiria medir a expansão dos areais.</li>
    <li>Próximo passo: usar o inventário para validar o mapa de suscetibilidade à arenização por AHP do mestrado em
    Geografia da UFSM.</li>
  </ul>
</section>

<section class="secao" id="referencias">
  __VENTO__
  <h2>Referências</h2>
  <ul class="nota">
    <li>MAPBIOMAS. Pampa – Appendix, ATBD Collection 11 e MapBiomas 10 m Collection 4. Disponível em: brasil.mapbiomas.org.</li>
    <li id="ref-olofsson2014" data-doi="10.1016/j.rse.2014.02.015">OLOFSSON, P. et al. Good practices for estimating area and assessing accuracy of land change. <i>Remote Sensing of Environment</i>, v. 148, p. 42–57, 2014. DOI: 10.1016/j.rse.2014.02.015.</li>
    <li id="ref-rayne2023" data-doi="10.1038/s41598-023-46319-1">RAYNE, L. et al. Detecting desertification in the ancient oases of southern Morocco. <i>Scientific Reports</i>, v. 13, 2023. DOI: 10.1038/s41598-023-46319-1.</li>
    <li>RIO GRANDE DO SUL. Secretaria do Meio Ambiente e Infraestrutura (SEMA). Mapeamento de areais do Rio Grande do Sul.</li>
    <li id="ref-souza2017" data-doi="10.20502/rbg.v18i1.1051">SOUZA, A. C.; PIRES, C. A. F. Dinâmica da arenização na bacia hidrográfica do Arroio Puitã, oeste do RS, através do mapeamento multitemporal no período de 1984 a 2014. <i>Revista Brasileira de Geomorfologia</i>, v. 18, n. 1, p. 185–196, 2017. DOI: 10.20502/rbg.v18i1.1051.</li>
    <li id="ref-suertegaray1992">SUERTEGARAY, D. M. A. <i>Deserto Grande do Sul: controvérsia</i>. Porto Alegre: Editora da UFRGS, 1992.</li>
    <li id="ref-suertegaray2011">SUERTEGARAY, D. M. A. Erosão nos campos sulinos: arenização no sudoeste do Rio Grande do Sul. <i>Revista Brasileira de Geomorfologia</i>, v. 12, n. 3, p. 61–74, 2011.</li>
  </ul>
  <h3>Créditos</h3>
  <p class="nota">Autora: Franqueline Monback Noschang. Professor ao longo do curso: Emanuel Goulart.
  Future Tech Leaders Brasil, Agência Espacial Brasileira (AEB), SDG AI Lab e UNDP/ICPSD.</p>
  <p class="nota">Agradecimentos ao Prof. Romário Trentin, orientador do mestrado, como referência e pela integração
  deste estudo à pesquisa sobre arenização, e a Marco Antônio da Rosa Soares, pelo apoio ao projeto.</p>
  <p class="nota">Parte do código e da revisão do texto teve apoio de IA (Claude, Anthropic); as decisões de método, a
  coleta e a conferência das amostras são da autora.</p>
</section>

__VENTO__
<footer class="rodape">
  <p>Fontes: imagens Sentinel-2 (ESA/Copernicus), Cloud Score+ (Google), MapBiomas 10 m, mapeamento de areais da SEMA-RS e
  ottobacias da ANA. Código sob licença MIT; dados produzidos no projeto sob CC BY 4.0.</p>
  <p><a href="__REPO__">Código, dados e metodologia completa no GitHub</a></p>
</footer>

<script>
const DADOS = __DADOS__;
const fmt = (v, c = 2) => v.toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c });

// ---------------------------------------------------------------- Mapa
const limites = [[__SUL__, __OESTE__], [__NORTE__, __LESTE__]];
// A posição vem antes de qualquer camada: sem ela, o Leaflet adia a montagem das camadas
const mapa = L.map("mapa", { zoomControl: false, scrollWheelZoom: false }).fitBounds(limites);
L.control.zoom({ position: "topright" }).addTo(mapa);
mapa.on("focus click", () => mapa.scrollWheelZoom.enable());
[["fundo", 250], ["mapbiomas", 410], ["classes", 420], ["areal", 430], ["limite", 440]].forEach(([nome, z]) => {
  mapa.createPane(nome).style.zIndex = z;
});

// Fundos: Sentinel-2 do mesmo ano (mediana usada na classificação), satélite de alta resolução ou OpenStreetMap
const satelite = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  { maxZoom: 18, attribution: "Imagem: Esri" });
const osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap" });
// Linha do tempo Sentinel-2: [arquivo, rótulo], a mediana do ano primeiro e depois os bimestres.
// Duas camadas se alternam para a sobreposição cruzada; cada WebP só é baixado quando é exibido.
const PERIODOS = __PERIODOS__;
const VAZIO = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";
const camadasS2 = PERIODOS.length ? [0, 1].map(() => L.imageOverlay(VAZIO, limites,
  { pane: "fundo", interactive: false, opacity: 0, className: "imagem-s2", attribution: "Sentinel-2: ESA/Copernicus" })) : [];
const periodo = document.getElementById("periodo");
const rotuloPeriodo = document.getElementById("rotulo-periodo");
const ctrlPeriodo = document.getElementById("ctrl-periodo");
const botaoPlay = document.getElementById("play");
periodo.max = Math.max(PERIODOS.length - 1, 0);
let visivel = 0, indicePeriodo = 0, pedidoPeriodo = 0, temporizador = null;

function mostrarPeriodo(i) {
  indicePeriodo = i;
  periodo.value = i;
  rotuloPeriodo.textContent = PERIODOS.length ? PERIODOS[i][1] : "";
  if (!camadasS2.length || !mapa.hasLayer(camadasS2[0])) return;
  const atual = camadasS2[visivel], proxima = camadasS2[1 - visivel];
  const url = new URL(PERIODOS[i][0], location.href).href;
  if (atual.getElement().src === url && atual.options.opacity > 0) return;
  const meu = ++pedidoPeriodo;
  const trocar = () => {
    if (meu !== pedidoPeriodo) return;   // outro período foi pedido enquanto esta imagem carregava
    proxima.setOpacity(1);
    atual.setOpacity(0);
    visivel = 1 - visivel;
  };
  if (proxima.getElement().src === url && proxima.getElement().complete) trocar();
  else { proxima.once("load", trocar); proxima.setUrl(PERIODOS[i][0]); }
}

const precarregadas = new Set();
function precarregar(i) {
  const url = PERIODOS[i][0];
  if (!precarregadas.has(url)) { precarregadas.add(url); new Image().src = url; }
}

function tocar(ligar) {
  clearInterval(temporizador);
  temporizador = null;
  botaoPlay.setAttribute("aria-pressed", ligar);
  botaoPlay.setAttribute("aria-label", ligar ? "Pausar a linha do tempo" : "Reproduzir a linha do tempo");
  if (!ligar) return;
  const proximo = () => (indicePeriodo + 1) % PERIODOS.length;
  precarregar(proximo());
  temporizador = setInterval(() => {
    mostrarPeriodo(proximo());
    precarregar(proximo());
  }, 1500);
}
botaoPlay.addEventListener("click", () => tocar(botaoPlay.getAttribute("aria-pressed") !== "true"));
periodo.addEventListener("input", () => { tocar(false); mostrarPeriodo(+periodo.value); });

const camadasFundo = { s2: [satelite, ...camadasS2], esri: [satelite], osm: [osm] };
function escolherFundo(chave) {
  tocar(false);
  [satelite, osm, ...camadasS2].forEach((c) => c.remove());
  camadasFundo[chave].forEach((c) => c.addTo(mapa));
  ctrlPeriodo.hidden = chave !== "s2" || PERIODOS.length < 2;
  if (chave === "s2") {
    camadasS2.forEach((c) => c.setOpacity(0));
    mostrarPeriodo(indicePeriodo);
  }
}
const seletorFundo = document.getElementById("fundo");
seletorFundo.addEventListener("change", () => escolherFundo(seletorFundo.value));
escolherFundo(seletorFundo.value);
const URL_CLASSES = "classes___ANO__.png";
const classes = L.imageOverlay(URL_CLASSES, limites, { pane: "classes", opacity: 0.75 }).addTo(mapa);
const areal = L.imageOverlay("areal___ANO__.png", limites, { pane: "areal", opacity: 1 }).addTo(mapa);
const mapbiomas = __TEM_MB__ ? L.imageOverlay("mapbiomas___ANO__.png", limites, { pane: "mapbiomas", opacity: 0.75 }) : null;

const contornos = L.geoJSON(null, {
  pane: "areal",
  style: { color: "#8A2A12", weight: 0.5, fillOpacity: 0 },
  onEachFeature: (f, camada) => camada.bindPopup("Areal: " + fmt(f.properties.area_ha) + " ha"),
});
const bacia = L.geoJSON(null, { pane: "limite", interactive: false, style: { color: "#fff", weight: 2, fill: false } }).addTo(mapa);
// Polígonos em arquivos separados (docs/), carregados depois do mapa
const lerGeoJSON = (arquivo, camada) => fetch(arquivo)
  .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
  .then((d) => camada.addData(d))
  .catch((e) => console.warn(`Não foi possível carregar ${arquivo} (${e}). Abra a página por um servidor (http), não pelo arquivo.`));
lerGeoJSON("bacia.geojson", bacia);
lerGeoJSON("areais___ANO__.geojson", contornos);

function atualizarContornos() {
  if (mapa.getZoom() >= 14) contornos.addTo(mapa); else contornos.remove();
}
mapa.on("zoomend", atualizarContornos);
atualizarContornos();

const opacidade = document.getElementById("opacidade");
opacidade.addEventListener("input", () => {
  if (!classeAtiva || classeAtiva.dataset.classe !== "1") classes.setOpacity(opacidade.value / 100);
  if (mapbiomas) mapbiomas.setOpacity(opacidade.value / 100);
});

// Destaque pela legenda: a classe escolhida fica como está e as outras esmaecem no mapa.
// O PNG de classes é recolorido num canvas (uma vez por classe); o Areal, que tem camada própria, esmaece junto.
const pngClasses = new Image();
pngClasses.src = URL_CLASSES;
const urlsDestaque = {};
function urlDestaque(cor) {
  if (urlsDestaque[cor]) return urlsDestaque[cor];
  if (!pngClasses.complete || !pngClasses.naturalWidth) return null;
  const tela = document.createElement("canvas");
  tela.width = pngClasses.naturalWidth;
  tela.height = pngClasses.naturalHeight;
  const ctx = tela.getContext("2d");
  ctx.drawImage(pngClasses, 0, 0);
  const dados = ctx.getImageData(0, 0, tela.width, tela.height);
  const p = dados.data;
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(cor.slice(i, i + 2), 16));
  for (let i = 0; i < p.length; i += 4) {
    if (p[i + 3] && (p[i] !== r || p[i + 1] !== g || p[i + 2] !== b)) p[i + 3] = 38;
  }
  ctx.putImageData(dados, 0, 0);
  return (urlsDestaque[cor] = tela.toDataURL());
}
const listaLegenda = document.querySelector("#legenda ul");
const itensClasse = [...document.querySelectorAll(".item-classe")];
let classeFixa = null, classeAtiva = null;
function destacar(item) {
  classeAtiva = item;
  itensClasse.forEach((li) => li.classList.toggle("ativo", li === item));
  listaLegenda.classList.toggle("destacando", !!item);
  const ehAreal = item && item.dataset.classe === "1";
  const url = item && !ehAreal ? urlDestaque(item.dataset.cor) : null;
  classes.setUrl(url || URL_CLASSES);
  classes.setOpacity(ehAreal ? opacidade.value / 400 : opacidade.value / 100);
  areal.setOpacity(item && !ehAreal ? 0.15 : 1);
}
const voltarDestaque = () => destacar(classeFixa);
itensClasse.forEach((li) => {
  li.addEventListener("pointerenter", (e) => { if (e.pointerType === "mouse") destacar(li); });
  li.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") voltarDestaque(); });
  li.addEventListener("focus", () => destacar(li));
  li.addEventListener("blur", voltarDestaque);
  li.addEventListener("click", () => { classeFixa = classeFixa === li ? null : li; voltarDestaque(); });
  li.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); li.click(); } });
});

const divisor = document.getElementById("divisor");
const linha = document.getElementById("linha");
const comparaCom = document.getElementById("comparar-com");
const RAIO = 18;
let modo = "";   // "" (sem comparação), "mapbiomas" ou "fundo"

function recortar() {
  const panes = ["classes", "areal"].map((p) => mapa.getPane(p));
  if (!modo) { panes.forEach((p) => (p.style.clip = "")); return; }
  const tamanho = mapa.getSize();
  const nw = mapa.containerPointToLayerPoint([0, 0]);
  const se = mapa.containerPointToLayerPoint(tamanho);
  const pos = RAIO + (tamanho.x - 2 * RAIO) * divisor.value / 100;
  const x = nw.x + pos;
  panes.forEach((p) => (p.style.clip = `rect(${nw.y}px, ${x}px, ${se.y}px, ${nw.x}px)`));
  mapa.getPane("mapbiomas").style.clip = `rect(${nw.y}px, ${se.x}px, ${se.y}px, ${x}px)`;
  linha.style.left = pos + "px";
}

comparaCom.addEventListener("change", () => {
  modo = comparaCom.value;
  ["divisor", "linha", "lado-esq", "lado-dir"].forEach((id) => (document.getElementById(id).hidden = !modo));
  document.getElementById("leg-outras").hidden = modo !== "mapbiomas";
  document.getElementById("lado-dir").textContent =
    modo === "mapbiomas" ? "MapBiomas 10 m (__ANO_MB__)" : "Imagem de fundo";
  if (mapbiomas) { if (modo === "mapbiomas") mapbiomas.addTo(mapa); else mapbiomas.remove(); }
  recortar();
});
divisor.addEventListener("input", recortar);
["mousedown", "touchstart"].forEach((ev) => divisor.addEventListener(ev, () => mapa.dragging.disable()));
["mouseup", "touchend"].forEach((ev) => divisor.addEventListener(ev, () => mapa.dragging.enable()));
mapa.on("move zoom resize", recortar);
if (window.matchMedia("(max-width: 700px)").matches) {
  document.getElementById("legenda").open = false;
  document.getElementById("controles").open = false;
}

// ---------------------------------------------------------------- Números dos cartões contam até o valor final
if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  document.querySelectorAll(".cartao b[data-valor]").forEach((el) => {
    const alvo = +el.dataset.valor, casas = +el.dataset.casas, sufixo = el.dataset.sufixo || "";
    const inicio = performance.now(), duracao = 800;
    const passo = (agora) => {
      const t = Math.min((agora - inicio) / duracao, 1);
      el.textContent = fmt(alvo * (1 - Math.pow(1 - t, 3)), casas) + sufixo;
      if (t < 1) requestAnimationFrame(passo);
    };
    requestAnimationFrame(passo);
  });
}

// ---------------------------------------------------------------- Citações: balão com a referência e o DOI
const balao = document.createElement("div");
balao.className = "balao";
balao.setAttribute("role", "dialog");
balao.hidden = true;
document.body.appendChild(balao);
let citaAberta = null, fecharDepois = null;
function abrirCitacao(link) {
  clearTimeout(fecharDepois);
  const ref = document.querySelector(link.getAttribute("href"));
  if (!ref) return;
  balao.innerHTML = ref.innerHTML + (ref.dataset.doi
    ? `<br><a class="botao-doi" href="https://doi.org/${ref.dataset.doi}" target="_blank" rel="noopener">DOI ↗</a>` : "");
  balao.hidden = false;
  const r = link.getBoundingClientRect();
  const largura = balao.offsetWidth;
  balao.style.left = Math.max(8, Math.min(r.left + scrollX, scrollX + document.documentElement.clientWidth - largura - 8)) + "px";
  balao.style.top = r.bottom + scrollY + 6 + "px";
  requestAnimationFrame(() => balao.classList.add("visivel"));
  if (citaAberta) citaAberta.setAttribute("aria-expanded", "false");
  citaAberta = link;
  link.setAttribute("aria-expanded", "true");
}
function fecharCitacao() {
  balao.classList.remove("visivel");
  balao.hidden = true;
  if (citaAberta) citaAberta.setAttribute("aria-expanded", "false");
  citaAberta = null;
}
document.querySelectorAll(".cita").forEach((link) => {
  link.setAttribute("aria-haspopup", "dialog");
  link.setAttribute("aria-expanded", "false");
  link.addEventListener("pointerenter", (e) => { if (e.pointerType === "mouse") abrirCitacao(link); });
  link.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") fecharDepois = setTimeout(fecharCitacao, 250); });
  link.addEventListener("click", (e) => {   // toque e teclado: abre e fecha o balão em vez de pular para a lista
    e.preventDefault();
    if (citaAberta === link && e.pointerType !== "mouse") fecharCitacao(); else abrirCitacao(link);
  });
});
balao.addEventListener("pointerenter", () => clearTimeout(fecharDepois));
balao.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") fecharDepois = setTimeout(fecharCitacao, 250); });
document.addEventListener("click", (e) => { if (citaAberta && !balao.contains(e.target) && !e.target.closest(".cita")) fecharCitacao(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && citaAberta) { const l = citaAberta; fecharCitacao(); l.focus(); } });

// ---------------------------------------------------------------- Abas reutilizáveis
function criarAbas(idContainer, opcoes, aoEscolher) {
  const caixa = document.getElementById(idContainer);
  const botoes = opcoes.map(([chave, rotulo], i) => {
    const b = document.createElement("button");
    b.className = "botao"; b.type = "button"; b.textContent = rotulo;
    b.setAttribute("role", "tab");
    b.addEventListener("click", () => {
      botoes.forEach((o) => o.setAttribute("aria-pressed", o === b));
      aoEscolher(chave);
    });
    caixa.appendChild(b);
    return b;
  });
  botoes[0].click();
}

// ---------------------------------------------------------------- Assinatura espectral
function desenharAssinatura(variavel) {
  const valores = DADOS.assinatura.valores[variavel];
  const minimo = Math.min(0, ...valores.map((q) => q[0]));
  const maximo = Math.max(0, ...valores.map((q) => q[2]));
  const escala = (v) => (100 * (v - minimo)) / (maximo - minimo || 1);
  const zero = escala(0);
  document.getElementById("grafico-assinatura").innerHTML = DADOS.assinatura.classes.map((c, i) => {
    const [q1, med, q3] = valores[i];
    const inicio = Math.min(zero, escala(med)), largura = Math.abs(escala(med) - zero);
    return `<div class="barra-linha"><span>${c.nome}</span><span class="trilho">
      <span class="barra" style="left:${inicio}%;width:${largura}%;background:${c.cor}"></span>
      <span class="bigode" style="left:${escala(q1)}%;width:${escala(q3) - escala(q1)}%"></span>
      ${minimo < 0 ? `<span class="zero" style="left:${zero}%"></span>` : ""}</span>
      <span class="valor">${fmt(med)} (${fmt(q1)} a ${fmt(q3)})</span></div>`;
  }).join("");
}
criarAbas("abas-assinatura", Object.entries(DADOS.assinatura.variaveis), desenharAssinatura);

// ---------------------------------------------------------------- Métricas
const rotulosMetricas = { ee: "Mapa publicado (Earth Engine)", mapa: "Modelo: classes do mapa", treino: "Modelo: classes do treino" };
function desenharMetricas(chave) {
  const m = DADOS.metricas[chave];
  const linhas = m.linhas.map((l) => `<tr><td>${l.classe}</td><td class="num">${fmt(l.precisao)}</td>
    <td class="num">${fmt(l.recall)}</td><td class="num"><b>${fmt(l.f1)}</b></td><td class="num">${l.n}</td></tr>`).join("");
  document.getElementById("tabela-metricas").innerHTML =
    `<thead><tr><th>Classe</th><th class="num">Precisão</th><th class="num">Recall</th><th class="num">F1</th><th class="num">Pontos</th></tr></thead>
     <tbody>${linhas}<tr><td><b>Acurácia global</b></td><td></td><td></td><td class="num"><b>${fmt(m.acuracia)}</b></td><td></td></tr></tbody>`;
}
criarAbas("abas-metricas", Object.keys(rotulosMetricas).filter((k) => DADOS.metricas[k]).map((k) => [k, rotulosMetricas[k]]), desenharMetricas);

// ---------------------------------------------------------------- Importância
const seletor = document.getElementById("seletor-importancia");
const imp = DADOS.importancia;
const coresClasse = Object.fromEntries(DADOS.assinatura.classes.map((c) => [c.nome, c.cor]));
["Areal", ...imp.classes.filter((c) => c !== "Areal")].forEach((c) => seletor.add(new Option(c, c)));
function desenharImportancia() {
  const classe = seletor.value;
  const pares = imp.variaveis.map((v, i) => [v, imp.valores[classe][i]]).sort((a, b) => b[1] - a[1]);
  const maximo = Math.max(...pares.map((p) => p[1]), 1e-9);
  const cor = coresClasse[classe] || "var(--roxo)";
  document.getElementById("grafico-importancia").innerHTML = pares.map(([v, val]) =>
    `<div class="barra-linha"><span>${v}</span><span class="trilho">
      <span class="barra" style="left:0;width:${(100 * Math.max(val, 0)) / maximo}%;background:${cor}"></span></span>
      <span class="valor">${fmt(val, 3)}</span></div>`).join("");
}
seletor.addEventListener("change", desenharImportancia);
desenharImportancia();

// ---------------------------------------------------------------- Menu: seção ativa
const linksMenu = [...document.querySelectorAll(".menu a")];
const observador = new IntersectionObserver((entradas) => {
  entradas.forEach((e) => {
    if (e.isIntersecting) linksMenu.forEach((a) => a.classList.toggle("ativo", a.getAttribute("href") === "#" + e.target.id));
  });
}, { rootMargin: "-40% 0px -55% 0px" });
linksMenu.forEach((a) => observador.observe(document.querySelector(a.getAttribute("href"))));
</script>
</body>
</html>
"""
