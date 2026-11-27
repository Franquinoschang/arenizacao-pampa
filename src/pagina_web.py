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
    "NDWI_med": "NDWI mediano",
}


VARIAVEIS_TIPICAS = {"NDVI_medio": "NDVI médio", "NDWI_med": "NDWI mediano", "BSI_med": "BSI mediano",
                     "FREQ_EXPOSTO": "Frequência de solo exposto"}

# Cartões "Como ler os índices" (chave = índice da camada de fundo no mapa)
CARTOES_INDICES = [
    ("ndvi", "NDVI", "Índice de Vegetação por Diferença Normalizada",
     "Mede o vigor da vegetação pelo contraste entre o vermelho, que as plantas absorvem, e o infravermelho próximo, "
     "que elas refletem. Vai de −1 a 1. Abaixo de 0, água. Entre 0 e 0,25, solo exposto (o limiar usado neste "
     "projeto). Entre 0,25 e 0,5, vegetação rala ou campo seco. Acima de 0,6, vegetação densa. O NDVI médio do "
     "areal fica no limite porque mistura as cenas de areia exposta com as de vegetação rala. Na lavoura ele sobe no auge da safra e cai depois da colheita.",
     '<a class="cita" href="#ref-rouse1974">Rouse et al., 1974</a>',
     "NDVI = (NIR − Vermelho) / (NIR + Vermelho)"),
    ("ndwi", "NDWI", "Índice de Água por Diferença Normalizada",
     "Compara o verde e o infravermelho próximo. Fica negativo sobre vegetação e solo e positivo sobre água limpa "
     "e profunda. Nos açudes da bacia, rasos e turvos, ele fica perto de zero, mas ainda bem acima das outras "
     "classes. A condição do NDWI reduz, mas não elimina, a contagem da água como solo exposto, e isso explica "
     "parte da confusão da classe Água.",
     '<a class="cita" href="#ref-mcfeeters1996">McFeeters, 1996</a>',
     "NDWI = (Verde − NIR) / (Verde + NIR)"),
    ("bsi", "BSI", "Índice de Solo Exposto",
     "Compara o infravermelho de ondas curtas e o vermelho, que o solo reflete mais, com o infravermelho próximo e o "
     "azul, que a vegetação reflete ou absorve de outro jeito. Quanto maior, mais solo à mostra. A areia clara e seca "
     "tem BSI alto.",
     '<a class="cita" href="#ref-rikimaru2002">Rikimaru et al., 2002</a>',
     "BSI = ((SWIR1 + Vermelho) − (NIR + Azul)) / ((SWIR1 + Vermelho) + (NIR + Azul))"),
    ("freq", "Frequência de solo exposto", "",
     "Não é um índice da imagem, é uma contagem. Mostra em que fração das cenas de __ANO__ o pixel apareceu como solo "
     "exposto (NDVI abaixo de 0,25, BSI acima de 0 e NDWI abaixo de 0). Vai de 0, nunca exposto, a 1, exposto em "
     "todas as cenas. É a variável que melhor separa o areal da lavoura.",
     "",
     "Frequência = cenas com solo exposto / cenas sem nuvem do pixel no ano"),
]


def _cartoes_indices(indices, ano):
    cartoes = []
    for chave, sigla, nome, texto, cita, formula in CARTOES_INDICES:
        gradiente = (indices or {}).get(chave, {}).get("gradiente")
        barra = f'<div class="barra-cor" style="background:{gradiente}" aria-hidden="true"></div>' if gradiente else ""
        subtitulo = f'<span class="nome-indice">{nome}</span>' if nome else ""
        fonte = f" ({cita})" if cita else ""
        cartoes.append(
            f'<div class="cartao-texto cartao-indice" id="indice-{chave}"><h4>{sigla}</h4>{subtitulo}{barra}'
            f'<p>{texto.replace("__ANO__", str(ano))}{fonte}</p><details><summary>Ver fórmula</summary>'
            f'<p class="formula">{formula}</p></details></div>')
    return "".join(cartoes)


def br(valor, casas=2):
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _vento():
    caminho = "M0 12 Q120 3 240 12" + "".join(f" T{x} 12" for x in range(480, 1201, 240))   # 2,5 ondulações
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


def arredondar_geojson(texto, casas=6):
    """Arredonda as coordenadas de um GeoJSON (6 casas ≈ 10 cm), para a página carregar mais leve."""
    def arred(c):
        return [arred(v) for v in c] if isinstance(c, list) else round(c, casas)
    dados = json.loads(texto)
    for f in dados.get("features", []):
        if f.get("geometry"):
            f["geometry"]["coordinates"] = arred(f["geometry"]["coordinates"])
    return json.dumps(dados, ensure_ascii=False, separators=(",", ":"))


def gerar_pagina(*, pasta_processados, pasta_web, pasta_figuras, ano, ano_mapbiomas, limites, areais_geojson,
                 bacia_geojson, tem_mb, periodos_s2=(), areal_por_mb=None, n_cenas=None, caso_lavoura=None,
                 indices=None, tipicas=None, logos=(), arquivos_amostras=(),
                 repo_url="",
                 site_url="https://franquinoschang.github.io/arenizacao-pampa/"):
    """Gera pasta_web/index.html.

    limites: (oeste, sul, leste, norte) em graus. periodos_s2: [(arquivo, rótulo)] das imagens Sentinel-2 de
    fundo em pasta_web, a mediana do ano primeiro. areal_por_mb: {código MapBiomas: km²} do Areal deste mapa,
    calculado dos GeoTIFFs (opcional; sem ele, usa a tabela de comparação, com "Outras" agrupadas).
    arquivos_amostras: arquivos de polígonos de amostra (GeoJSON ou shapefile, com a coluna Classvalue), contados
    por classe na tabela de Dados e ligados ao GitHub.
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

    # Valores típicos dos índices nas amostras (mediana por classe) e número de variáveis do modelo
    colunas_meta = {"areal_duvidoso", "classe", "conjunto", "grupo", "poligono"}
    n_variaveis = len([c for c in amostras.columns if c not in colunas_meta])
    linhas_tipicos = []
    for c in [1, 7, 3, 2, 6, 4, 5]:
        sub = amostras[amostras["classe"] == c]
        if not sub.empty:
            celulas = "".join(f'<td class="num">{br(sub[v].median())}</td>' for v in VARIAVEIS_TIPICAS)
            linhas_tipicos.append(f"<tr><td>{nomes_treino[c]}</td>{celulas}</tr>")
    cabecalho_tipicos = "".join(f'<th class="num">{r}</th>' for r in VARIAVEIS_TIPICAS.values())
    tabela_tipicos = (f'<table><thead><tr><th>Classe</th>{cabecalho_tipicos}</tr></thead>'
                      f'<tbody>{"".join(linhas_tipicos)}</tbody></table>')
    # Polígonos de amostra por classe, lidos dos arquivos de amostras, com link para cada arquivo no GitHub
    raiz_repo = proc.resolve().parents[1]
    poligonos_classe, links_amostras = {}, []
    for arquivo in arquivos_amostras:
        import geopandas as gpd

        arquivo = Path(arquivo).resolve()
        for c, n in gpd.read_file(arquivo)["Classvalue"].value_counts().items():
            poligonos_classe[int(c)] = poligonos_classe.get(int(c), 0) + int(n)
        relativo = arquivo.relative_to(raiz_repo).as_posix()
        if arquivo.suffix == ".shp":   # o shapefile são vários arquivos: o link vai para a pasta
            relativo = arquivo.parent.relative_to(raiz_repo).as_posix()
        alvo = f"{repo_url}/{'tree' if arquivo.suffix == '.shp' else 'blob'}/main/{relativo}"
        links_amostras.append(f'<a href="{alvo}">{html.escape(arquivo.name)}</a>')
    if poligonos_classe:
        por_classe = ", ".join(f"{nomes_treino[c]} {br(n, 0)}" for c, n in sorted(poligonos_classe.items()) if c in nomes_treino)
        amostras_dado = (f"Amostras rotuladas: {br(sum(poligonos_classe.values()), 0)} polígonos"
                         f'<span class="detalhe-dado">{por_classe}</span>')
        amostras_fonte = "Interpretação visual neste projeto, publicada no GitHub (" + " e ".join(links_amostras) + ")"
    else:
        amostras_dado, amostras_fonte = "Amostras rotuladas (polígonos)", "Interpretação visual neste projeto"

    # Frequência de solo exposto mediana por classe, citada no texto (sai do mesmo CSV da tabela de valores típicos)
    def pct_freq(c):
        return round(100 * amostras.loc[amostras["classe"] == c, "FREQ_EXPOSTO"].median())
    freq_areal = "metade das cenas" if pct_freq(1) == 50 else f"{pct_freq(1)}% das cenas"
    tipicas = {k: dict(v) for k, v in (tipicas or {}).items()}
    tipicas.setdefault("Lavoura", {})["freq"] = round(float(amostras.loc[amostras["classe"] == 3, "FREQ_EXPOSTO"].median()), 3)

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
    (web / f"areais_{ano}.geojson").write_text(arredondar_geojson(areais_geojson), encoding="utf-8")
    (web / "bacia.geojson").write_text(arredondar_geojson(bacia_geojson), encoding="utf-8")
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
        <p class="nota">Parte dos areais da SEMA (mapeamento de 2020) aparece como Campo em 2025: são áreas revegetadas desde o mapeamento
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
        "__N_TREINO__": br(n_treino, 0), "__FREQ_AREAL__": freq_areal,
        "__FREQ_LAVOURA__": f"{pct_freq(3)}%", "__FREQ_LAV_EXP__": f"{pct_freq(7)}%", "__N_TESTE__": br(n_teste, 0),
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
        "__CASO__": json.dumps(caso_lavoura["limites"]) if caso_lavoura else "null",
        "__INDICES__": json.dumps(indices or {}, ensure_ascii=False),
        "__TIPICAS__": json.dumps(tipicas or {}, ensure_ascii=False),
        "__OPCOES_INDICE__": '<option value="">Nenhum (classes do mapa)</option>' + "".join(
            f'<option value="{k}">{html.escape(v["rotulo"])}</option>' for k, v in (indices or {}).items()),
        "__SEM_INDICES__": "" if indices else "hidden",
        "__CASO_TEXTO__": (f" Nesta seção, o mapa mostra de perto a maior mancha de areal sobre lavoura do MapBiomas "
                           f"({br(caso_lavoura['ha'], 1)} ha), lado a lado com o MapBiomas." if caso_lavoura else ""),
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
        "__CARTOES_INDICES__": _cartoes_indices(indices, ano),
        "__TABELA_TIPICOS__": tabela_tipicos,
        "__N_VARIAVEIS__": str(n_variaveis),
        "__N_CENAS_PAR__": f" ({n_cenas})" if n_cenas else "",
        "__CENAS_S2__": f"{n_cenas} cenas de {ano}" if n_cenas else f"cenas de {ano}",
        "__AMOSTRAS_DADO__": amostras_dado, "__AMOSTRAS_FONTE__": amostras_fonte,
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
<meta property="og:image" content="__SITE__localizacao_bacia.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="logo_ftl.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@600;700&display=swap">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  /* Tema areia (DESIGN.md): o roxo FTL é só acento — botões, links, controle ativo e foco */
  :root {
    --roxo: #4617DE; --sobre-acento: #FFFFFF;
    --fundo: #F6EFE3; --superficie: #EDE2CE; --duna: #D9C6A5;
    --texto: #2B2420; --texto-suave: #6B5E52; --link: #4617DE; --numero: #2B2420;
    --calor: 139, 94, 52;
    --sombra: 0 2px 10px rgba(43, 36, 32, 0.08);
    --curva: cubic-bezier(0.2, 0.7, 0.2, 1);
    --titulo: "Space Grotesk", system-ui, sans-serif;
    --corpo: "Inter", system-ui, sans-serif;
    --altura-mapa-celular: 45vh;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --roxo: #8F7CFF; --sobre-acento: #1F1A15;
      --fundo: #1F1A15; --superficie: #2A231C; --duna: #4A3E32;
      --texto: #F1E8DA; --texto-suave: #BFAF98; --link: #8F7CFF; --numero: #F1E8DA;
      --calor: 217, 198, 165;
      --sombra: 0 2px 10px rgba(0, 0, 0, 0.35);
    }
  }
  * { box-sizing: border-box; }
  [hidden] { display: none !important; }
  html { scroll-behavior: smooth; scroll-padding-top: 56px; }
  /* Textura de areia: ruído SVG leve sobre o fundo (os painéis, tabelas e o mapa têm fundo próprio) */
  body { margin: 0; color: var(--texto); font: 400 16px/1.6 var(--corpo); background-color: var(--fundo);
         background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='220' height='220'%3E%3Cfilter id='r'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23r)' opacity='0.06'/%3E%3C/svg%3E"); }
  a { color: var(--link); }
  a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible, [tabindex]:focus-visible {
    outline: 2px solid var(--roxo); outline-offset: 2px; }
  h1, h2, h3 { font-family: var(--titulo); margin: 0; }
  h2 { font-size: 26px; font-weight: 700; margin-bottom: 16px; }
  h3 { font-size: 19px; font-weight: 600; margin: 24px 0 8px; }
  .num, .valor, .cartao b, td { font-variant-numeric: tabular-nums; }

  /* ------------------------------------------------ Story map: mapa fixo + coluna de texto */
  .coluna-mapa { position: sticky; top: 0; height: var(--altura-mapa-celular); z-index: 1500; }
  .coluna-mapa.tela-cheia { position: fixed; inset: 0; height: 100vh; height: 100dvh; z-index: 5000; }
  body.mapa-aberto { overflow: hidden; }
  .area-mapa { position: relative; height: 100%; overflow: hidden; background: var(--superficie); }
  #mapa { position: absolute; inset: 0; }
  .coluna-texto { min-width: 0; }
  @media (min-width: 900px) {
    .story { display: grid; grid-template-columns: minmax(0, 52fr) minmax(0, 48fr); align-items: start; }
    .coluna-mapa { height: 100vh; z-index: 1; }
    .botao-expandir { display: none; }
  }

  .topo { display: flex; flex-direction: column; align-items: flex-start; gap: 16px; padding: 24px 32px 8px; }
  .sobre { margin: 0 0 4px; font-size: 13px; color: var(--texto-suave); }
  .topo h1 { font-size: 34px; line-height: 1.12; font-weight: 700; }
  .topo .sub { margin: 8px 0 0; color: var(--texto-suave); }
  .selo { display: inline-block; vertical-align: middle; margin-left: 8px; padding: 1px 10px; border-radius: 999px;
          border: 1.5px solid var(--roxo); color: var(--roxo); font: 600 15px var(--titulo); }
  .logos { display: flex; gap: 16px; align-items: center; }
  .logos img { height: 48px; max-width: 100%; object-fit: contain; }
  @media (prefers-color-scheme: dark) { .logos { background: #F6EFE3; padding: 8px 16px; border-radius: 14px; } }
  .vento { display: block; width: 100%; height: 24px; }
  .vento path { fill: none; stroke: var(--duna); stroke-width: 1.5; vector-effect: non-scaling-stroke; }

  .menu { position: sticky; top: 0; z-index: 1400; background: var(--fundo); border-bottom: 1px solid var(--duna); }
  .menu ul { display: flex; gap: 4px; list-style: none; margin: 0; padding: 8px 24px; overflow-x: auto; }
  .menu a { display: block; padding: 4px 12px; border-radius: 999px; text-decoration: none; font-size: 14px;
            white-space: nowrap; transition: background 200ms var(--curva), color 200ms var(--curva); }
  .menu a.ativo { background: var(--roxo); color: var(--sobre-acento); }

  .numeros { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .cartao { background: var(--superficie); border-radius: 14px; box-shadow: var(--sombra); padding: 14px 18px; }
  .cartao b { display: block; font: 700 36px/1.1 var(--titulo); color: var(--numero); }
  .cartao span { font-size: 13px; color: var(--texto-suave); }
  .cartao .explica { display: block; margin-top: 4px; font-size: 12px; line-height: 1.35; color: var(--texto-suave); }

  /* ------------------------------------------------ Painéis sobre o mapa (nos cantos, recolhíveis) */
  .painel { position: absolute; z-index: 1000; background: var(--superficie); color: var(--texto); border-radius: 14px;
            box-shadow: var(--sombra); padding: 6px 14px; font-size: 13px; }
  .painel summary { font: 600 14px var(--titulo); cursor: pointer; padding: 4px 0; }
  .controles { left: 12px; top: 12px; }
  .conteudo-controles { display: flex; flex-direction: column; gap: 8px; padding: 4px 0 8px; }
  .conteudo-controles .check-ref { display: flex; flex-direction: row; align-items: center; gap: 6px; }
  .rotulo-municipio { background: rgba(31, 26, 21, 0.72); color: #FFF4D6; border: none; border-radius: 8px; box-shadow: none;
                      padding: 3px 8px; font: 600 12.5px var(--corpo); text-align: center; line-height: 1.25; }
  .rotulo-municipio span { display: block; font-weight: 400; font-size: 11.5px; opacity: 0.9; }
  .rotulo-municipio::before { display: none; }
  .controles label { display: flex; flex-direction: column; gap: 4px; }
  .controles input[type=range] { accent-color: var(--roxo); width: 210px; }
  .controles .seletor { width: 210px; font-size: 13px; }
  .legenda { left: 12px; bottom: 24px; max-width: 260px; }
  .legenda ul { list-style: none; margin: 4px 0 8px; padding: 0; }
  .legenda li { display: flex; align-items: center; gap: 8px; padding: 2px 4px; margin: 0 -4px; border-radius: 6px;
                transition: opacity 200ms var(--curva), background 200ms var(--curva); }
  .item-classe { cursor: pointer; }
  .legenda ul.destacando .item-classe { opacity: 0.45; }
  .legenda ul.destacando .item-classe.ativo { opacity: 1; background: color-mix(in srgb, var(--duna) 70%, transparent); }
  .legenda .km { margin-left: auto; padding-left: 16px; color: var(--texto-suave); }
  .cor { display: inline-block; width: 14px; height: 14px; border-radius: 4px; flex: none; border: 1px solid rgba(0, 0, 0, 0.2); }
  .botao-expandir { position: absolute; z-index: 1000; right: 10px; bottom: 26px; font: 600 13px var(--corpo);
                    padding: 6px 14px; border-radius: 999px; border: 2px solid var(--roxo); background: var(--superficie);
                    color: var(--link); cursor: pointer; box-shadow: var(--sombra); }
  .imagem-s2 { transition: opacity 400ms var(--curva); }
  .legenda-indice { left: 12px; bottom: 24px; width: 260px; }
  .legenda-indice b { display: block; font: 600 14px var(--titulo); }
  .li-periodo { font-size: 12px; color: var(--texto-suave); }
  .barra-cor { height: 12px; border-radius: 999px; margin: 8px 0 2px; border: 1px solid rgba(0, 0, 0, 0.15); }
  .escala { display: flex; justify-content: space-between; font-size: 12px; color: var(--texto-suave); font-variant-numeric: tabular-nums; }
  #li-significado { margin: 6px 0 0; font-size: 12px; line-height: 1.4; }
  .li-nota { margin: 4px 0 2px; font-size: 11px; color: var(--texto-suave); }
  .leaflet-popup-content-wrapper, .leaflet-popup-tip { background: var(--superficie); color: var(--texto); }
  .popup-areal { font: 13px/1.4 var(--corpo); }
  .popup-areal .titulo-mancha { display: block; font: 600 15px var(--titulo); margin-bottom: 4px; }
  .mini-numeros { margin: 0 0 6px; font-size: 13px; }
  .mini-numeros span { display: block; }
  .como-ler { margin: 4px 0 6px; font-size: 12.5px; line-height: 1.4; }
  .mini-abas { display: flex; gap: 4px; margin: 6px 0 4px; }
  .mini-aba { font: 600 12px var(--corpo); padding: 2px 10px; border-radius: 999px; border: 1.5px solid var(--roxo);
              background: transparent; color: var(--link); cursor: pointer; }
  .mini-aba[aria-pressed=true] { background: var(--roxo); color: var(--sobre-acento); }
  .minigrafico { display: block; width: 100%; height: auto; }
  .minigrafico text { font: 12px var(--corpo); fill: var(--texto-suave); }
  .minigrafico text.eixo-y { font-weight: 600; fill: var(--texto); }
  .minigrafico text.rotulo-linha { font-weight: 600; }
  .minigrafico line { stroke: var(--duna); stroke-width: 1; }
  .popup-areal small { display: block; color: var(--texto-suave); font-size: 12px; line-height: 1.35; }
  .aviso-zoom { position: absolute; z-index: 1000; top: 12px; right: 60px; width: max-content;
                max-width: 240px; display: flex; flex-direction: column; align-items: center; gap: 6px;
                padding: 8px 12px; border-radius: 14px; background: var(--superficie); color: var(--texto);
                box-shadow: var(--sombra); font-size: 12.5px; line-height: 1.35; text-align: center; }
  .aviso-zoom[hidden] { display: none; }
  .aviso-zoom button { font: 600 12.5px var(--corpo); padding: 4px 12px; border-radius: 999px; border: none;
                       background: var(--roxo); color: var(--sobre-acento); cursor: pointer; }
  .legenda .leg-cabecalho { font-size: 11.5px; color: var(--texto-suave); padding-bottom: 2px; }
  .legenda .leg-cabecalho .km { font-weight: 600; }
  .linha-tempo { display: flex; flex-direction: column; gap: 4px; }
  .tempo { display: flex; align-items: center; gap: 8px; }
  .controles .tempo input[type=range] { flex: 1; width: auto; min-width: 0; }
  .botao-play { flex: none; display: grid; place-items: center; width: 32px; height: 32px; padding: 0; border: none;
                border-radius: 999px; background: var(--roxo); color: var(--sobre-acento); cursor: pointer;
                transition: transform 200ms var(--curva); }
  .botao-play:hover { transform: scale(1.06); }
  .botao-play svg { width: 14px; height: 14px; fill: currentColor; }
  .botao-play .icone-pausa, .botao-play[aria-pressed=true] .icone-play { display: none; }
  .botao-play[aria-pressed=true] .icone-pausa { display: inline; }
  .divisor { position: absolute; z-index: 900; left: 0; top: 50%; width: 100%; height: 36px; margin: 0; transform: translateY(-50%);
             -webkit-appearance: none; appearance: none; background: transparent; pointer-events: none; }
  .divisor::-webkit-slider-runnable-track { background: transparent; }
  .divisor::-webkit-slider-thumb { -webkit-appearance: none; pointer-events: auto; width: 36px; height: 36px; border-radius: 999px;
                                   background: var(--roxo); border: 3px solid #fff; cursor: ew-resize; box-shadow: var(--sombra); }
  .divisor::-moz-range-thumb { pointer-events: auto; width: 30px; height: 30px; border-radius: 999px; background: var(--roxo);
                               border: 3px solid #fff; cursor: ew-resize; }
  .linha { position: absolute; z-index: 899; top: 0; bottom: 0; width: 3px; margin-left: -1.5px; background: #fff; pointer-events: none; }
  .lado { position: absolute; z-index: 899; bottom: 70px; padding: 2px 12px; border-radius: 999px; background: rgba(31, 26, 21, 0.78);
          color: #fff; font-size: 13px; pointer-events: none; }

  /* ------------------------------------------------ Texto */
  .secao { padding: 28px 32px 0; }
  .dica { font-size: 13px; color: var(--texto-suave); }
  .grade { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
  .cartao-texto { background: var(--superficie); border-radius: 14px; box-shadow: var(--sombra); padding: 16px 20px; }
  .cartao-texto h3:first-child { margin-top: 0; }
  .nota { font-size: 13px; color: var(--texto-suave); }
  .detalhe-dado { display: block; font-size: 12.5px; color: var(--texto-suave); }
  /* Celular: cada dado vira um bloco, com o nome da coluna antes de cada valor */
  @media (max-width: 600px) {
    .tabela-dados thead { display: none; }
    .tabela-dados tr { display: block; padding: 10px 0; border-bottom: 1px solid var(--duna); }
    .tabela-dados td { display: block; border: none; padding: 2px 0; }
    .tabela-dados td:first-child { font-weight: 600; }
    .tabela-dados td:nth-child(2)::before { content: "Fonte: "; font-weight: 600; }
    .tabela-dados td:nth-child(3)::before { content: "Formato e resolução: "; font-weight: 600; }
    .tabela-dados td:nth-child(4)::before { content: "Uso: "; font-weight: 600; }
  }
  .secao > p.dica, .secao > p.nota { max-width: none; font-size: 12.5px; font-style: italic; }
  .grade-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  @media (max-width: 560px) { .grade-2 { grid-template-columns: 1fr; } }
  .lista-ods { margin: 0; padding-left: 18px; }
  .lista-ods li { margin: 4px 0; }
  figure { margin: 16px 0; }
  figure img { width: 100%; border-radius: 14px; }
  figcaption { font-size: 13px; color: var(--texto-suave); margin: 6px auto 0; text-align: center; }
  .figura-matriz figcaption { max-width: 560px; }
  .figura-matriz img { display: block; max-width: 560px; margin: 0 auto; background: #fff; }

  table { border-collapse: collapse; width: 100%; font-size: 14px; background: var(--fundo); }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--duna); vertical-align: top; }
  thead th { font-weight: 600; }
  td.num, th.num { text-align: right; }
  .rolagem { overflow-x: auto; }
  .quadro { font-size: 14px; min-width: 600px; }
  .quadro th[scope=row] { font-weight: 600; white-space: nowrap; position: sticky; left: 0; z-index: 1; background: var(--fundo); }
  .quadro th.projeto { color: var(--roxo); border-bottom: 2px solid var(--roxo); }
  .quadro td.projeto { background: var(--superficie); font-weight: 600; }
  /* Linha do tempo dos trabalhos relacionados: horizontal com rolagem, vertical no celular */
  .linha-trabalhos { --onda: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='12'%3E%3Cpath d='M0 6 Q20 0 40 6 T80 6' fill='none' stroke='%23D9C6A5' stroke-width='1.5'/%3E%3C/svg%3E");
                 --onda-v: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='80'%3E%3Cpath d='M6 0 Q0 20 6 40 T6 80' fill='none' stroke='%23D9C6A5' stroke-width='1.5'/%3E%3C/svg%3E");
                 list-style: none; margin: 16px 0 8px; padding: 0 0 12px; display: grid; grid-auto-flow: column;
                 grid-auto-columns: minmax(260px, 46%); gap: 16px; overflow-x: auto; scroll-snap-type: x mandatory;
                 overscroll-behavior-x: contain; }
  @media (prefers-color-scheme: dark) {
    .linha-trabalhos { --onda: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='12'%3E%3Cpath d='M0 6 Q20 0 40 6 T80 6' fill='none' stroke='%234A3E32' stroke-width='1.5'/%3E%3C/svg%3E");
                   --onda-v: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='80'%3E%3Cpath d='M6 0 Q0 20 6 40 T6 80' fill='none' stroke='%234A3E32' stroke-width='1.5'/%3E%3C/svg%3E"); }
  }
  .marco { position: relative; padding-top: 30px; scroll-snap-align: start; display: flex; }
  .marco::before { content: ""; position: absolute; top: 6px; left: 0; width: calc(100% + 16px); height: 12px;
                   background: var(--onda) repeat-x; background-size: 80px 12px; }
  .marco:last-child::before { width: 100%; }
  .marco::after { content: ""; position: absolute; top: 3px; left: 18px; width: 12px; height: 12px; border-radius: 999px;
                  background: var(--fundo); border: 3px solid var(--duna); }
  .marco > .cartao-texto { flex: 1; display: flex; flex-direction: column; }
  .marco-ano { font: 700 26px var(--titulo); line-height: 1; }
  .marco-autor { font-size: 14px; color: var(--texto-suave); margin-top: 4px; }
  .marco-papel { font: 600 16px var(--titulo); margin-top: 10px; }
  .marco p { font-size: 15px; margin: 8px 0 12px; }
  .marco-aberto { margin-top: auto; border-top: 1px solid var(--duna); padding-top: 10px; font-size: 14px; }
  .marco-aberto a { font-weight: 600; }
  .marco-aberto p { margin: 4px 0 0; font-size: 14px; color: var(--texto-suave); }
  .marco.destaque > .cartao-texto { box-shadow: inset 0 0 0 2px var(--roxo), var(--sombra); }
  .marco.destaque::after { background: var(--roxo); border-color: var(--roxo); }
  .marco.destaque .marco-ano, .marco.destaque .marco-papel { color: var(--link); }
  /* Cartões dos índices e botão de ajuda da legenda */
  .cartao-indice h4 { margin: 0; font: 600 18px var(--titulo); }
  .nome-indice { display: block; font-size: 13px; color: var(--texto-suave); }
  .cartao-indice p { font-size: 15px; margin: 8px 0; }
  .cartao-indice summary { cursor: pointer; color: var(--link); font-size: 14px; font-weight: 500; }
  .balao .cartao-indice-balao h4 { margin: 0; font: 600 15px var(--titulo); }
  .balao .cartao-indice-balao p { margin: 6px 0; }
  .li-topo { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
  .botao-ajuda { flex: none; width: 24px; height: 24px; border-radius: 999px; border: 2px solid var(--roxo); background: var(--superficie);
                 color: var(--link); font: 700 13px var(--titulo); cursor: pointer; padding: 0; line-height: 1; }
  .cita { text-decoration: underline dotted; text-underline-offset: 3px; cursor: help; }
  .balao { position: absolute; z-index: 6000; max-width: min(340px, calc(100vw - 16px)); background: var(--superficie);
           color: var(--texto); border-radius: 14px; box-shadow: 0 4px 18px rgba(43, 36, 32, 0.22); padding: 12px 16px;
           font-size: 13px; line-height: 1.45; opacity: 0; transform: translateY(4px);
           transition: opacity 150ms var(--curva), transform 150ms var(--curva); }
  .balao.visivel { opacity: 1; transform: none; }
  .balao .botao-doi { display: inline-block; margin-top: 8px; padding: 4px 12px; border-radius: 999px; background: var(--roxo);
                      color: var(--sobre-acento); text-decoration: none; font-weight: 600; }

  .passos { list-style: none; counter-reset: passo; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
  @media (max-width: 640px) { .passos { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  @media (max-width: 420px) { .passos { grid-template-columns: 1fr; } }
  .passos li { counter-increment: passo; background: var(--superficie); border-radius: 14px; padding: 14px 16px; box-shadow: var(--sombra); }
  .passos li::before { content: counter(passo); display: inline-grid; place-items: center; width: 26px; height: 26px; border-radius: 999px;
                       border: 2px solid var(--roxo); color: var(--roxo); font: 600 13px var(--titulo); margin-bottom: 8px; }
  .passos b { display: block; font-family: var(--titulo); }
  .passos span { font-size: 14px; color: var(--texto-suave); }
  .formula { font-family: ui-monospace, monospace; font-size: 13px; }

  .barra-linha { display: grid; grid-template-columns: 130px 1fr 140px; align-items: center; gap: 8px; padding: 3px 0; font-size: 14px; }
  .trilho { position: relative; height: 14px; border-radius: 999px; background: color-mix(in srgb, var(--duna) 45%, transparent); }
  .barra { position: absolute; top: 0; bottom: 0; border-radius: 999px; transition: left 200ms var(--curva), width 200ms var(--curva); }
  .bigode { position: absolute; top: 6px; height: 2px; background: var(--texto); opacity: 0.55; transition: left 200ms var(--curva), width 200ms var(--curva); }
  .zero { position: absolute; top: -3px; bottom: -3px; width: 1px; background: var(--texto-suave); }
  .valor { text-align: right; color: var(--texto-suave); }
  .abas { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 16px; }
  .botao { font: 500 13px var(--corpo); border-radius: 999px; padding: 6px 16px; cursor: pointer; border: 2px solid var(--roxo);
           background: transparent; color: var(--link); transition: background 200ms var(--curva), color 200ms var(--curva); }
  .botao[aria-pressed=true] { background: var(--roxo); color: var(--sobre-acento); }
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
  @media (prefers-color-scheme: dark) { .calor.escura { color: #1F1A15; } }

  .rodape { padding: 8px 32px 40px; font-size: 13px; color: var(--texto-suave); }
  .rodape p { margin: 4px 0; }

  @media (prefers-reduced-motion: reduce) {
    .imagem-s2, .legenda li, .botao-play, .barra, .bigode, .menu a, .botao, .balao { transition: none; }
    html { scroll-behavior: auto; }
  }
  @media (max-width: 899px) {
    html { scroll-padding-top: calc(var(--altura-mapa-celular) + 52px); }
    .menu { top: var(--altura-mapa-celular); }
    .menu ul { padding: 8px 16px; }
    .topo { padding: 16px 16px 8px; }
    .topo h1 { font-size: 26px; }
    .logos img { height: auto; width: 100%; max-width: 340px; }
    .secao { padding: 24px 16px 0; }
    .numeros { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .cartao { padding: 10px 14px; }
    .cartao b { font-size: 26px; }
    .controles { left: 8px; top: 8px; }
    .legenda { left: 8px; bottom: 8px; max-width: calc(100% - 140px); }
    .aviso-zoom { top: auto; bottom: 64px; right: 8px; max-width: 170px; }
    .legenda-indice { left: 8px; bottom: 8px; width: auto; max-width: calc(100% - 140px); }
    .coluna-mapa.tela-cheia .legenda { max-width: 260px; }
    .barra-linha { grid-template-columns: 96px 1fr 96px; font-size: 13px; }
    .linha-trabalhos { grid-auto-flow: row; grid-auto-columns: auto; overflow: visible; scroll-snap-type: none; padding-left: 28px; }
    .marco { padding-top: 0; }
    .marco::before, .marco:last-child::before { top: 0; left: -24px; width: 12px; height: calc(100% + 16px);
                                                background: var(--onda-v) repeat-y; background-size: 12px 80px; }
    .marco:last-child::before { height: 100%; }
    .marco::after { top: 20px; left: -25px; }
    .rodape { padding: 8px 16px 32px; }
  }
</style>
</head>
<body>
<div class="story">
<div class="coluna-mapa" id="coluna-mapa">
  <div class="area-mapa">
    <div id="mapa" aria-label="Mapa da classificação de cobertura da terra, que acompanha o texto"></div>
    <details class="painel controles" id="controles" open>
      <summary>Camadas e linha do tempo</summary>
      <div class="conteudo-controles">
      <label>Fundo<select class="seletor" id="fundo">__OPCOES_FUNDO__</select></label>
      <label __SEM_INDICES__>Índice espectral<select class="seletor" id="indice">__OPCOES_INDICE__</select></label>
      <div id="ctrl-periodo" class="linha-tempo" hidden>
        <span>Período: <b id="rotulo-periodo" aria-live="polite"></b></span>
        <div class="tempo">
          <button type="button" class="botao-play" id="play" aria-pressed="false" aria-label="Reproduzir a linha do tempo">
            <svg viewBox="0 0 16 16" aria-hidden="true"><path class="icone-play" d="M4 2.5v11l9-5.5z"/><path class="icone-pausa" d="M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z"/></svg>
          </button>
          <input type="range" id="periodo" min="0" max="0" value="0" aria-label="Período da imagem Sentinel-2">
        </div>
      </div>
      <label class="check-ref"><input type="checkbox" id="ref-limites" checked> Limites do RS e dos estados (IBGE)</label>
      <label class="check-ref"><input type="checkbox" id="ref-municipios" checked> Municípios do RS (IBGE)</label>
      <label>Opacidade das classes<input type="range" id="opacidade" min="0" max="100" value="75"></label>
      <label>Comparar lado a lado com<select class="seletor" id="comparar-com">__OPCOES_COMPARAR__</select></label>
      </div>
    </details>
    <input type="range" class="divisor" id="divisor" min="0" max="100" value="50" aria-label="Divisão entre os mapas" hidden>
    <div class="linha" id="linha" hidden></div>
    <span class="lado" id="lado-esq" style="left: 12px" hidden>Este mapa</span>
    <span class="lado" id="lado-dir" style="right: 12px" hidden></span>
    <div class="aviso-zoom" id="aviso-zoom" hidden><span>Aproxime o mapa para clicar nas manchas de areal</span>
      <button type="button" id="ir-mancha">Ir até uma mancha</button></div>
    <details class="painel legenda" id="legenda" open>
      <summary>Legenda</summary>
      <ul><li class="leg-cabecalho"><span>Classe</span><span class="km">Área na bacia</span></li>__LEGENDA__<li id="leg-outras" hidden><span class="cor" style="background:__COR_OUTRAS__"></span>Outras classes do MapBiomas</li></ul>
    </details>
    <div class="painel legenda-indice" id="legenda-indice" hidden aria-live="polite">
      <div class="li-topo"><div><b id="li-nome"></b><span class="li-periodo" id="li-periodo"></span></div>
        <button type="button" class="botao-ajuda" id="li-ajuda" aria-haspopup="dialog" aria-expanded="false"
                aria-label="Como ler este índice">?</button></div>
      <div class="barra-cor" id="li-barra"></div>
      <div class="escala"><span id="li-min"></span><span id="li-max"></span></div>
      <p id="li-significado"></p>
      <p class="li-nota">Manchas de areal em contorno. Clique numa delas para ver as curvas.</p>
    </div>
    <button type="button" class="botao-expandir" id="expandir" aria-expanded="false" aria-controls="coluna-mapa">Expandir mapa</button>
  </div>
</div>

<main class="coluna-texto">
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
    <li><a href="#mapa-secao">Início</a></li>
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

<section class="secao" id="mapa-secao" aria-label="Números principais">
  <div class="numeros">
    <div class="cartao"><b data-valor="__V_AREA__" data-casas="2">__AREA__</b><span>km² de areal</span></div>
    <div class="cartao"><b data-valor="__V_PCT__" data-casas="1" data-sufixo="%">__PCT__%</b><span>da bacia (__AREA_TOTAL__ km²)</span></div>
    <div class="cartao"><b data-valor="__V_F1__" data-casas="2">__F1__</b><span>F1 do Areal no teste</span>
      <small class="explica">F1: equilíbrio entre encontrar os areais e não marcar areal onde não existe (de 0 a 1).</small></div>
    <div class="cartao"><b data-valor="__V_ACURACIA__" data-casas="2">__ACURACIA__</b><span>acurácia global no teste</span></div>
  </div>
  <p class="dica"><b>O mapa acompanha o texto:</b> ao rolar, ele muda de camada e de enquadramento a cada seção. Se você
  mexer no mapa, a condução automática pausa até a próxima seção. Para conferir o resultado, use o fundo
  <b>Sentinel-2 __ANO__</b>, mova o <b>período da imagem</b> pelos bimestres (o areal fica exposto em boa parte do ano, na mediana em __FREQ_AREAL__, contra
  __FREQ_LAVOURA__ na lavoura) e compare lado a lado com o MapBiomas. Ao aproximar o mapa, as manchas de areal ganham contorno e
  mostram os detalhes ao clicar.</p>
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
  exposto em boa parte do ano, na mediana em __FREQ_AREAL__, contra __FREQ_LAVOURA__ na lavoura.</p>
  <div class="grade">
    <div class="cartao-texto">
      <h3>Objetivos de Desenvolvimento Sustentável</h3>
      <ul class="lista-ods">
        <li><b>ODS 15 – Vida Terrestre</b>, meta 15.3: saber onde estão os areais é o primeiro passo para priorizar
        manejo e recuperação.</li>
        <li><b>ODS 2</b>: a arenização reduz a área útil para pecuária e lavoura.</li>
        <li><b>ODS 13</b>: o inventário é a linha de base para acompanhar o efeito de chuvas intensas e do vento.</li>
      </ul>
    </div>
    <div class="cartao-texto">
      <h3>Produtos</h3>
      <p>Mapa de classificação de __ANO__ (GeoTIFF, 10 m), polígonos de areais (shapefile), código aberto e
      reprodutível e este mapa web.</p>
    </div>
  </div>
  <p>Este inventário faz parte de um estudo mais amplo sobre os processos de arenização nesta bacia, desenvolvido no
  mestrado em Geografia da UFSM.</p>
  __FIGURA_LOCAL__

  <h3>Trabalhos relacionados</h3>
  <p>Três trabalhos orientam este projeto. Cada um resolve uma parte do problema e deixa outra em aberto, e é dessa
  sequência que vem o desenho do mapa.</p>
  <ol class="linha-trabalhos" aria-label="Linha do tempo dos trabalhos relacionados" tabindex="0">
    <li class="marco" id="marco-1992"><div class="cartao-texto">
      <span class="marco-ano">1992</span>
      <span class="marco-autor"><a class="cita" href="#ref-suertegaray1992">Suertegaray</a></span>
      <b class="marco-papel">O conceito</b>
      <p>Ao estudar os areais do sudoeste gaúcho, Suertegaray mostrou que eles não são um deserto. Em clima úmido, o
      que existe é a arenização, o retrabalhamento de depósitos arenosos pouco consolidados, em que a areia em
      movimento impede a vegetação de se fixar. O conceito define o que este mapa procura: areia exposta de forma
      persistente sobre esses depósitos.</p>
      <div class="marco-aberto"><a href="#marco-2017">O que ficou em aberto →</a>
        <p>Onde estão os areais hoje e como acompanhá-los ao longo do tempo.</p></div>
    </div></li>
    <li class="marco" id="marco-2017"><div class="cartao-texto">
      <span class="marco-ano">2017</span>
      <span class="marco-autor"><a class="cita" href="#ref-souza2017">Souza e Pires</a></span>
      <b class="marco-papel">O mapeamento regional</b>
      <p>No Arroio Puitã, Souza e Pires acompanharam os areais de 1984 a 2014 com imagens Landsat e classificação por
      Máxima Verossimilhança, uma imagem por data. O trabalho mostra a dinâmica regional e traz um alerta: a transição
      entre campo e areal, de vegetação rala, aparece como solo exposto e se parece com solo em cultivo inicial.</p>
      <div class="marco-aberto"><a href="#marco-2023">O que ficou em aberto →</a>
        <p>Com uma única data e 30 m de resolução, o areal se confunde com a lavoura em preparo de solo.</p></div>
    </div></li>
    <li class="marco" id="marco-2023"><div class="cartao-texto">
      <span class="marco-ano">2023</span>
      <span class="marco-autor"><a class="cita" href="#ref-rayne2023">Rayne et al.</a></span>
      <b class="marco-papel">O método</b>
      <p>No sul do Marrocos, Rayne et al. detectaram campos degradados por desertificação com Sentinel-2, Google Earth
      Engine e Random Forest, com 74 a 76% de acerto na classe de interesse. Daí vêm o fluxo de trabalho deste projeto
      e uma referência realista do que esperar de acurácia.</p>
      <div class="marco-aberto"><a href="#marco-2025">O que ficou em aberto →</a>
        <p>Uma única estação do ano, em clima árido, sem a confusão com a lavoura.</p></div>
    </div></li>
    <li class="marco destaque" id="marco-2025"><div class="cartao-texto">
      <span class="marco-ano">__ANO__</span>
      <span class="marco-autor">Este projeto</span>
      <b class="marco-papel">A síntese</b>
      <p>Este projeto aplica o método de Rayne et al. ao problema descrito por Suertegaray e por Souza e Pires, com
      Sentinel-2 a 10 m e a série do ano inteiro. O areal fica exposto em boa parte do ano, na mediana em __FREQ_AREAL__, contra
      __FREQ_LAVOURA__ na lavoura, e é essa diferença que separa as duas classes.</p>
    </div></li>
  </ol>
  <h3>Comparação rápida</h3>
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
</section>

<section class="secao" id="dados">
  __VENTO__
  <h2>Dados</h2>
  <div class="rolagem"><table class="tabela-dados">
    <thead><tr><th>Dado</th><th>Fonte</th><th>Formato e resolução</th><th>Uso</th></tr></thead>
    <tbody>
      <tr><td>Sentinel-2 L2A, reflectância de superfície, __CENAS_S2__</td><td><a href="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED">ESA/Copernicus, via Google Earth Engine</a></td><td>Imagem multiespectral, 10 m (visível e infravermelho próximo) e 20 m (infravermelho de ondas curtas)</td><td>Índices espectrais e variáveis do modelo</td></tr>
      <tr><td>Cloud Score+</td><td><a href="https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_CLOUD_SCORE_PLUS_V1_S2_HARMONIZED">Google, via Earth Engine</a></td><td>Imagem de qualidade por pixel, 10 m</td><td>Máscara de nuvens</td></tr>
      <tr><td>Imagens de alta resolução</td><td><a href="https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9">Esri World Imagery</a> / <a href="https://earth.google.com/">Google Earth</a></td><td>Imagem, menos de 1 m</td><td>Interpretação visual das amostras</td></tr>
      <tr><td>Limite da ottobacia 682636</td><td><a href="https://metadados.snirh.gov.br/geonetwork/srv/por/catalog.search">ANA – Base Hidrográfica Ottocodificada</a></td><td>Vetor (polígono)</td><td>Recorte da área de estudo</td></tr>
      <tr><td>MapBiomas 10 m, Coleção 4</td><td><a href="https://brasil.mapbiomas.org/">MapBiomas</a></td><td>Mapa de cobertura e uso, 10 m</td><td>Apoio à amostragem, controle de qualidade e comparação</td></tr>
      <tr><td>Mapeamento de areais do RS (2020)</td><td><a href="https://www.sema.rs.gov.br/">SEMA-RS</a></td><td>Vetor (polígonos)</td><td>Localização dos areais, controle de qualidade e comparação</td></tr>
      <tr><td>Malhas territoriais do Brasil, do RS e dos municípios</td><td><a href="https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais.html">IBGE</a></td><td>Vetor (polígonos)</td><td>Referência no mapa</td></tr>
      <tr><td>__AMOSTRAS_DADO__</td><td>__AMOSTRAS_FONTE__</td><td>Vetor (polígonos), GeoJSON e shapefile</td><td>Treino e teste</td></tr>
    </tbody>
  </table></div>
  <p class="nota">Todos os dados de entrada são públicos. As amostras rotuladas estão publicadas no GitHub sob licença
  CC BY 4.0.</p>
  <p class="nota">O MapBiomas e a SEMA-RS ajudaram a localizar os areais, mas nunca foram usados como rótulo direto:
  cada amostra foi conferida na imagem de alta resolução e nas seis medianas bimestrais do Sentinel-2.</p>
</section>

<section class="secao" id="metodo">
  __VENTO__
  <h2>Método</h2>
  <ol class="passos">
    <li><b>Imagens</b><span>Todas as cenas Sentinel-2 de __ANO__ sobre a bacia__N_CENAS_PAR__, com as nuvens removidas pelo Cloud Score+.</span></li>
    <li><b>Índices por cena</b><span>NDVI, BSI e NDWI, mais uma marcação de solo exposto quando o NDVI fica abaixo de 0,25, o BSI acima de 0 e o NDWI abaixo de 0.</span></li>
    <li><b>Variáveis anuais</b><span>São __N_VARIAVEIS__ por pixel: as medianas das bandas, as estatísticas do NDVI (mínimo, médio, máximo, amplitude e desvio), o BSI e o NDWI medianos e a frequência de solo exposto no ano.</span></li>
    <li><b>Amostras</b><span>Polígonos desenhados em SIG e revisados um a um. Os areais passam por um controle de qualidade próprio.</span></li>
    <li><b>Treino e teste</b><span>As amostras foram divididas em 70% para treino e 30% para teste, sempre por grupos de polígonos vizinhos, para que áreas quase idênticas não fiquem dos dois lados. Foram __N_TREINO__ pontos de treino e __N_TESTE__ de teste.</span></li>
    <li><b>Random Forest</b><span>Os hiperparâmetros foram escolhidos por validação cruzada espacial. A bacia foi classificada no Earth Engine, e um filtro final corrige a troca de pixels entre Silvicultura e Vegetação Nativa.</span></li>
  </ol>

  <h3>Como ler os índices</h3>
  <div class="grade grade-2">__CARTOES_INDICES__</div>
  <h4>Valores típicos nas amostras</h4>
  <div class="rolagem">__TABELA_TIPICOS__</div>
  <p class="nota">Mediana de cada classe nos pontos de amostra de __ANO__. A Lavoura exposta é uma subclasse do treino,
  juntada à Lavoura no mapa final.</p>

  <h3>Por que a série do ano inteiro separa areal e lavoura</h3>
  <p>Numa única data, areal e lavoura em preparo de solo são parecidos. No ano, não: o areal fica exposto em boa parte
  do ano, na mediana em __FREQ_AREAL__, contra __FREQ_LAVOURA__ na lavoura, que alterna solo exposto e vegetação densa. Talhões expostos
  por mais tempo (pousio, palhada, na mediana em __FREQ_LAV_EXP__ das cenas) foram treinados como uma subclasse, <b>Lavoura exposta</b>, e juntados à Lavoura no mapa final.
  O gráfico mostra a mediana de cada classe nas amostras (barra) e o intervalo entre os quartis 25% e 75% (traço).</p>
  <div class="abas" id="abas-assinatura" role="tablist" aria-label="Variável"></div>
  <div id="grafico-assinatura"></div>
  <p class="nota">Clique numa aba para ver o índice correspondente no mapa, como medianas bimestrais de __ANO__ (a
  frequência de solo exposto é a mesma variável do modelo). No mapa, clique numa mancha de areal para comparar as
  suas curvas com as de Lavoura e Campo.</p>

  <h3>Controle de qualidade dos areais</h3>
  <p>Cada polígono de areal foi medido no próprio Sentinel-2: é <b>núcleo de areal</b> se ficou exposto em pelo menos
  metade das cenas e tem NDVI médio até 0,30. Os demais são <b>duvidosos</b> e foram revisados um a um. O controle de
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
  <p>Deep Learning foi descartado porque exige milhares de imagens rotuladas de areais, que não existem para a região.
  Como limitação, o Random Forest classifica cada pixel isoladamente e não usa forma nem textura, o que contribui para
  a confusão com talhões expostos.</p>
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
  que ficam em polígonos separados dos de treino. O F1 do Areal é <b>__F1__</b>. A classe mais difícil é o Campo, que se
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
    o teste mede o modelo em amostras típicas, e a comparação com referências mede o mapa inteiro.</p>
  </div>
</section>

<section class="secao" id="comparacao">
  __VENTO__
  <h2>Comparação com o MapBiomas e a SEMA-RS</h2>
  <p>A concordância geral com o MapBiomas 10 m é de <b>__CONCORDANCIA_MB__%</b> da área da bacia. No Areal, a concordância
  é menor, e parte da diferença vem de como cada base classifica: o MapBiomas classifica o <b>uso</b> da terra (um talhão inteiro é lavoura,
  mesmo com uma mancha de areia dentro) e a SEMA-RS mapeou os areais consolidados, em escala mais grosseira. Este mapa
  classifica a <b>cobertura</b> pixel a pixel, a 10 m.__CASO_TEXTO__</p>
  <div class="cartao-texto">
    <h3>Onde está o Areal deste mapa, segundo o MapBiomas</h3>
    __EMPILHADA_MB__
    <p>__ACHADO_MB__</p>
    <p>A conferência visual de 30 a 50 manchas em conflito com a lavoura do MapBiomas mostrou solo arenoso exposto na
    maior parte delas.</p>
    <p>A literatura sustenta essa leitura. O processo de arenização "poderá ser desencadeado por agentes naturais ou
    atividades humanas" (<a class="cita" href="#ref-suertegaray2011">Suertegaray, 2011, p. 69</a>). Numa área piloto entre
    São Francisco de Assis e Manoel Viana, a mesma região desta bacia, na frente de expansão da soja, a análise
    multitemporal registrou aumento de 47,52 ha de areais em 25 anos, resultados que "indicam o surgimento de novas
    manchas de areia (areais)" (Suertegaray, Guasselli e Franz, 1995 apud <a class="cita" href="#ref-suertegaray2011">Suertegaray, 2011, p. 69</a>). Ravinas e
    sulcos também podem resultar do "uso de maquinaria pesada na atividade agrícola"
    (<a class="cita" href="#ref-suertegaray2011">Suertegaray, 2011, p. 64</a>).</p>
    <p>Os solos do substrato arenoso da bacia são "muito frágeis e altamente suceptíveis [sic] à erosão hídrica"
    (<a class="cita" href="#ref-suertegaray2011">Suertegaray, 2011, p. 69</a>): quando a cobertura é removida, a "expansão lateral e remontante das ravinas e
    voçorocas, promove a formação do areal propriamente dito" (<a class="cita" href="#ref-suertegaray2011">idem</a>), e a "constante mobilidade dos sedimentos"
    dificulta a volta da vegetação (<a class="cita" href="#ref-suertegaray2011">Suertegaray, 2011, p. 62</a>).</p>
    <p>Por isso, as manchas de solo arenoso exposto
    encontradas dentro de lavouras são <b>áreas fragilizadas, com possíveis focos de arenização</b>. Parte ainda pode
    ser manejo (pousio, preparo do solo), e a confirmação em campo é o próximo passo.</p>
  </div>
  __BLOCO_SEMA__
  <h3>Matriz de concordância</h3>
  <p class="nota">Cada linha é uma classe deste mapa, e as colunas mostram como a mesma área aparece no MapBiomas (% da
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
    <li>A área é a contagem de pixels e ainda não tem intervalo de confiança.</li>
    <li>Talhões expostos por mais tempo que a lavoura comum ainda podem se parecer com areal. Variáveis de textura ou classificação por
    objetos (segmentação) podem reduzir essa confusão.</li>
    <li>O Campo é a classe com menor acerto e se confunde com lavoura e com areais revegetados.</li>
    <li>A Água ainda ocupa mais área que no MapBiomas: quase toda a água real é encontrada, mas banhados, várzeas e
    sombras de mata ciliar também aparecem como água. Uma variável de frequência de água (fração das cenas com água)
    separaria os corpos d'água permanentes das áreas úmidas temporárias.</li>
    <li>A resolução de 10–20 m não captura areais muito pequenos ou estreitos, e areais sob silvicultura não aparecem.</li>
    <li>O mapa cobre um único ano. Aplicar o mesmo fluxo a anos anteriores permitiria medir a expansão dos areais.</li>
    <li>Integrar o inventário ao estudo dos processos de arenização da bacia, em desenvolvimento no mestrado em
    Geografia da UFSM.</li>
  </ul>
</section>

<section class="secao" id="referencias">
  __VENTO__
  <h2>Referências</h2>
  <ul class="nota">
    <li>MAPBIOMAS. Pampa – Appendix, ATBD Collection 11 e MapBiomas 10 m Collection 4. Disponível em: brasil.mapbiomas.org.</li>
    <li id="ref-mcfeeters1996" data-doi="10.1080/01431169608948714">McFEETERS, S. K. The use of the Normalized Difference Water Index (NDWI) in the delineation of open water features. <i>International Journal of Remote Sensing</i>, v. 17, n. 7, p. 1425–1432, 1996.</li>
    <li id="ref-olofsson2014" data-doi="10.1016/j.rse.2014.02.015">OLOFSSON, P. et al. Good practices for estimating area and assessing accuracy of land change. <i>Remote Sensing of Environment</i>, v. 148, p. 42–57, 2014. DOI: 10.1016/j.rse.2014.02.015.</li>
    <li id="ref-rayne2023" data-doi="10.1038/s41598-023-46319-1">RAYNE, L. et al. Detecting desertification in the ancient oases of southern Morocco. <i>Scientific Reports</i>, v. 13, 2023. DOI: 10.1038/s41598-023-46319-1.</li>
    <li id="ref-rikimaru2002">RIKIMARU, A.; ROY, P. S.; MIYATAKE, S. Tropical forest cover density mapping. <i>Tropical Ecology</i>, v. 43, n. 1, p. 39–47, 2002.</li>
    <li>RIO GRANDE DO SUL. Secretaria do Meio Ambiente e Infraestrutura (SEMA). Mapeamento de areais do Rio Grande do Sul. 2020. Disponível em: https://sema.rs.gov.br/areais.</li>
    <li id="ref-rouse1974">ROUSE, J. W. et al. Monitoring vegetation systems in the Great Plains with ERTS. In: <i>Third ERTS Symposium</i>, NASA SP-351, p. 309–317, 1974.</li>
    <li id="ref-souza2017" data-doi="10.20502/rbg.v18i1.1051">SOUZA, A. C.; PIRES, C. A. F. Dinâmica da arenização na bacia hidrográfica do Arroio Puitã, oeste do RS, através do mapeamento multitemporal no período de 1984 a 2014. <i>Revista Brasileira de Geomorfologia</i>, v. 18, n. 1, p. 185–196, 2017. DOI: 10.20502/rbg.v18i1.1051.</li>
    <li id="ref-suertegaray1992">SUERTEGARAY, D. M. A. <i>Deserto Grande do Sul: controvérsia</i>. Porto Alegre: Editora da UFRGS, 1992.</li>
    <li id="ref-suertegaray2011">SUERTEGARAY, D. M. A. Erosão nos campos sulinos: arenização no sudoeste do Rio Grande do Sul. <i>Revista Brasileira de Geomorfologia</i>, v. 12, n. 3, p. 61–74, 2011.</li>
  </ul>
  <h3>Créditos</h3>
  <p class="nota">Autora: Franqueline Monback Noschang. Professor ao longo do curso: Emanuel Goulart.
  Future Tech Leaders Brasil, Agência Espacial Brasileira (AEB), SDG AI Lab e UNDP/ICPSD.</p>
  <p class="nota">Agradecimentos ao Prof. Romário Trentin, orientador do mestrado, como referência e pela integração
  deste estudo à pesquisa sobre arenização, e a Marco Antônio da Rosa Soares, pelo apoio ao projeto.</p>
  <p class="nota">Parte do código e da revisão do texto teve apoio de IA (Claude, Anthropic), mas as decisões de método, a
  coleta e a conferência das amostras são da autora.</p>
</section>

__VENTO__
<footer class="rodape">
  <p>Fontes: imagens Sentinel-2 (ESA/Copernicus), Cloud Score+ (Google), MapBiomas 10 m, mapeamento de areais da SEMA-RS e
  ottobacias da ANA. Código sob licença MIT e dados produzidos no projeto sob CC BY 4.0.</p>
  <p><a href="__REPO__">Código, dados e metodologia completa no GitHub</a></p>
</footer>
</main>
</div>

<script>
const DADOS = __DADOS__;
const fmt = (v, c = 2) => v.toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c });

// ---------------------------------------------------------------- Mapa
const limites = [[__SUL__, __OESTE__], [__NORTE__, __LESTE__]];
// A posição vem antes de qualquer camada: sem ela, o Leaflet adia a montagem das camadas
const mapa = L.map("mapa", { zoomControl: false, scrollWheelZoom: false }).fitBounds(limites);
L.control.zoom({ position: "topright" }).addTo(mapa);
mapa.on("focus click", () => mapa.scrollWheelZoom.enable());
[["fundo", 250], ["mapbiomas", 410], ["classes", 420], ["areal", 430], ["referencia", 435], ["limite", 440]].forEach(([nome, z]) => {
  mapa.createPane(nome).style.zIndex = z;
});

// Fundos: Sentinel-2 do mesmo ano (mediana usada na classificação), satélite de alta resolução ou OpenStreetMap
const satelite = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  { maxZoom: 18, attribution: "Imagem: Esri" });
const osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap" });
// Linha do tempo Sentinel-2: [arquivo, rótulo], a mediana do ano primeiro e depois os bimestres.
// Duas camadas se alternam para a sobreposição cruzada; cada WebP só é baixado quando é exibido.
const PERIODOS = __PERIODOS__;
// Índices espectrais da pilha bimestral: arquivos por período (posição 0 = ano; vazia nos índices bimestrais)
const INDICES = __INDICES__;
const TIPICAS = __TIPICAS__;   // curvas medianas de Lavoura e Campo nas amostras
let indiceAtual = "";
function urlPeriodo(i) {
  const ind = INDICES[indiceAtual];
  if (ind) return ind.anual ? ind.arquivos[0] : ind.arquivos[i];
  return PERIODOS[i][0];
}
function rotuloDoPeriodo(i) {
  const ind = INDICES[indiceAtual];
  if (ind && ind.anual) return "ano __ANO__";
  return PERIODOS.length ? PERIODOS[i][1] : "";
}
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
  rotuloPeriodo.textContent = rotuloDoPeriodo(i);
  document.getElementById("li-periodo").textContent = rotuloDoPeriodo(i);
  if (!camadasS2.length || !mapa.hasLayer(camadasS2[0])) return;
  const atual = camadasS2[visivel], proxima = camadasS2[1 - visivel];
  const arquivo = urlPeriodo(i);
  const url = new URL(arquivo, location.href).href;
  if (atual.getElement().src === url && atual.options.opacity > 0) return;
  const meu = ++pedidoPeriodo;
  const trocar = () => {
    if (meu !== pedidoPeriodo) return;   // outro período foi pedido enquanto esta imagem carregava
    proxima.setOpacity(1);
    atual.setOpacity(0);
    visivel = 1 - visivel;
  };
  if (proxima.getElement().src === url && proxima.getElement().complete) trocar();
  else { proxima.once("load", trocar); proxima.setUrl(arquivo); }
}

const precarregadas = new Set();
function precarregar(i) {
  const url = urlPeriodo(i);
  if (!precarregadas.has(url)) { precarregadas.add(url); new Image().src = url; }
}

function tocar(ligar) {
  clearInterval(temporizador);
  temporizador = null;
  botaoPlay.setAttribute("aria-pressed", ligar);
  botaoPlay.setAttribute("aria-label", ligar ? "Pausar a linha do tempo" : "Reproduzir a linha do tempo");
  if (!ligar) return;
  // Nos índices bimestrais o play percorre só os bimestres (posições 1 a 6)
  const proximo = () => (INDICES[indiceAtual] ? (indicePeriodo % (PERIODOS.length - 1)) + 1 : (indicePeriodo + 1) % PERIODOS.length);
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
  ctrlPeriodo.hidden = chave !== "s2" || PERIODOS.length < 2 || !!(INDICES[indiceAtual] && INDICES[indiceAtual].anual);
  if (chave === "s2") {
    camadasS2.forEach((c) => c.setOpacity(0));
    mostrarPeriodo(indicePeriodo);
  }
}
const seletorFundo = document.getElementById("fundo");
seletorFundo.addEventListener("change", () => {
  if (seletorFundo.value !== "s2" && indiceAtual) definirIndice("");
  escolherFundo(seletorFundo.value);
});
escolherFundo(seletorFundo.value);
const URL_CLASSES = "classes___ANO__.png";
const classes = L.imageOverlay(URL_CLASSES, limites, { pane: "classes", opacity: 0.75 }).addTo(mapa);
const areal = L.imageOverlay("areal___ANO__.png", limites, { pane: "areal", opacity: 1 }).addTo(mapa);
const mapbiomas = __TEM_MB__ ? L.imageOverlay("mapbiomas___ANO__.png", limites, { pane: "mapbiomas", opacity: 0.75 }) : null;

// Com o balão aberto, os painéis do mapa ficam recolhidos para não cobri-lo e voltam ao estado anterior ao fechar
const paineisMapa = ["controles", "legenda"].map((id) => document.getElementById(id));
let estadoPaineis = null;
function recolherPaineis() {
  if (!estadoPaineis) estadoPaineis = paineisMapa.map((p) => p.open);
  paineisMapa.forEach((p) => { p.open = false; });
}
mapa.on("popupclose", () => {
  // espera um instante: ao trocar de mancha, o balão novo abre logo depois de o anterior fechar
  setTimeout(() => {
    if (estadoPaineis && !document.querySelector(".leaflet-popup")) {
      paineisMapa.forEach((p, i) => { p.open = estadoPaineis[i]; });
      estadoPaineis = null;
    }
  }, 50);
});
// Contorno das manchas: vermelho-escuro sobre as classes e o satélite, branco sobre os índices
const estiloContorno = () => ({ color: INDICES[indiceAtual] ? "#FFFFFF" : "#8A2A12", weight: 1.5, opacity: 1,
                                fillColor: INDICES[indiceAtual] ? "#FFFFFF" : "#8A2A12", fillOpacity: 0 });
const contornos = L.geoJSON(null, {
  pane: "areal",
  style: estiloContorno,
  onEachFeature: (f, camada) => {
    // No celular o mapa ocupa só 45% da tela: o balão ganha rolagem para caber nele
    const alturaMax = window.matchMedia("(max-width: 899px)").matches ? Math.round(window.innerHeight * 0.45 - 120) : null;
    camada.bindPopup(() => conteudoPopup(f.properties), { maxWidth: Math.min(320, window.innerWidth - 90), minWidth: 260, maxHeight: alturaMax,
                                                          autoPanPaddingTopLeft: [10, 56], autoPanPaddingBottomRight: [10, 56] });
    camada.on("mouseover", () => camada.setStyle({ weight: 2.5, fillOpacity: 0.22 }));
    camada.on("mouseout", () => camada.setStyle(estiloContorno()));
    camada.on("popupopen", (e) => {
      recolherPaineis();
      // Abas NDVI / NDWI / BSI dentro do balão: troca só o gráfico, sem recriar o balão (o Leaflet fecharia o
      // balão ao ver um clique num botão que saiu da página)
      e.popup.getElement().onclick = (ev) => {
        const b = ev.target.closest(".mini-aba");
        if (!b) return;
        L.DomEvent.stopPropagation(ev);
        const caixa = b.closest(".popup-areal");
        caixa.querySelectorAll(".mini-aba").forEach((o) => o.setAttribute("aria-pressed", o === b));
        const serie = typeof f.properties.s === "string" ? JSON.parse(f.properties.s) : f.properties.s;
        caixa.querySelector(".minigrafico").outerHTML = miniGrafico(serie, b.dataset.ind);
        caixa.querySelector(".como-ler").innerHTML = COMO_LER[b.dataset.ind];
      };
    });
  },
});
const bacia = L.geoJSON(null, { pane: "limite", interactive: false, style: { color: "#fff", weight: 2, fill: false } }).addTo(mapa);
// Polígonos em arquivos separados (docs/), carregados depois do mapa
const lerGeoJSON = (arquivo, camada) => fetch(arquivo)
  .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
  .then((d) => camada.addData(d))
  .catch((e) => console.warn(`Não foi possível carregar ${arquivo} (${e}). Abra a página por um servidor (http), não pelo arquivo.`));
lerGeoJSON("bacia.geojson", bacia);
// Referência regional: limites estaduais do Brasil e o contorno do RS (malhas do IBGE, arquivos fixos em docs/)
const limitesRef = L.layerGroup([
  L.geoJSON(null, { pane: "referencia", interactive: false, attribution: "Limites: IBGE",
    style: { color: "#F2F2F2", weight: 1, opacity: 0.75, dashArray: "4 3", fill: false } }),
  L.geoJSON(null, { pane: "referencia", interactive: false, style: { color: "#FFD166", weight: 2.5, opacity: 0.95, fill: false } }),
]).addTo(mapa);
const [ufsBrasil, contornoRS] = limitesRef.getLayers();
lerGeoJSON("ufs_brasil.geojson", ufsBrasil);
lerGeoJSON("rs.geojson", contornoRS);
document.getElementById("ref-limites").addEventListener("change", (e) => {
  if (e.target.checked) limitesRef.addTo(mapa); else limitesRef.remove();
});
// Municípios do RS (malha do IBGE): limites finos e destaque, com o nome, para os municípios em que a bacia está
const municipios = L.layerGroup().addTo(mapa);
const malhaMunicipios = L.geoJSON(null, {
  pane: "referencia", interactive: false,
  style: (f) => (f.properties.km2
    ? { color: "#FFD166", weight: 2, opacity: 1, fillColor: "#FFD166", fillOpacity: 0.08 }
    : { color: "#F2F2F2", weight: 0.6, opacity: 0.55, fill: false }),
  onEachFeature: (f) => {
    if (!f.properties.rotulo) return;
    L.tooltip({ permanent: true, direction: "center", className: "rotulo-municipio", interactive: false })
      .setLatLng(f.properties.rotulo)
      .setContent(`${f.properties.nome}<span>${fmt(f.properties.km2, 0)} km² na bacia</span>`)
      .addTo(municipios);
  },
}).addTo(municipios);
lerGeoJSON("municipios_rs.geojson", malhaMunicipios);
document.getElementById("ref-municipios").addEventListener("change", (e) => {
  if (e.target.checked) municipios.addTo(mapa); else municipios.remove();
});
lerGeoJSON("areais___ANO__.geojson", contornos).then(() => atualizarContornos());

const avisoZoom = document.getElementById("aviso-zoom");
function atualizarContornos() {
  const ind = INDICES[indiceAtual];
  contornos.setStyle(estiloContorno());
  // Sombra escura sob o contorno branco, para ele aparecer também nos tons claros dos índices
  mapa.getPane("areal").style.filter = ind ? "drop-shadow(0 0 1px rgba(0, 0, 0, 0.85))" : "";
  const visiveis = !!ind || mapa.getZoom() >= 14;
  if (visiveis) contornos.addTo(mapa); else contornos.remove();
  avisoZoom.hidden = visiveis || !contornos.getLayers().length;
}
// "Ir até uma mancha": voa até a maior mancha de areal e abre o balão dela
document.getElementById("ir-mancha").addEventListener("click", () => {
  const maior = contornos.getLayers().reduce((a, b) => (b.feature.properties.area_ha > a.feature.properties.area_ha ? b : a));
  mapa.once("moveend", () => maior.openPopup());
  mapa.flyToBounds(maior.getBounds(), { maxZoom: 16, padding: [40, 40] });
});

// Minigráfico das medianas bimestrais de uma mancha de areal, com as curvas típicas de Lavoura e Campo
const NOMES_INDICE = { ndvi: "NDVI", ndwi: "NDWI", bsi: "BSI" };
const ABAS_BALAO = ["ndvi", "bsi"];   // o NDWI não entra no balão: nas manchas de areal ele quase não varia
const EIXO_Y = { ndvi: "NDVI ↑ mais vegetação", ndwi: "NDWI ↑ mais água", bsi: "BSI ↑ mais solo exposto" };
const BIMESTRES_CURTOS = ["jan–fev", "mar–abr", "mai–jun", "jul–ago", "set–out", "nov–dez"];
const COMO_LER = {
  ndvi: "<b>Como ler:</b> no areal, a linha laranja fica baixa e quase plana o ano todo. Na lavoura, ela sobe na safra e cai depois da colheita.",
  ndwi: "<b>Como ler:</b> valores abaixo de zero indicam ausência de água. Linhas próximas mostram que a mancha não é corpo d'água.",
  bsi: "<b>Como ler:</b> quanto mais alto, mais solo à mostra. O areal fica acima da lavoura e do campo na maior parte do ano.",
};
function miniGrafico(serie, nome) {
  // Faixa do minigráfico: a mesma para todas as manchas, ajustada aos valores das manchas e das curvas típicas
  const [gmin, gmax] = (INDICES[nome] && INDICES[nome].grafico) || [-1, 1];
  const ind = { min: gmin, max: gmax };
  const L = 300, A = 202, m = { e: 34, d: 96, t: 24, b: 44 };
  const x = (i) => m.e + (i * (L - m.e - m.d)) / 5;
  const y = (v) => m.t + (1 - (Math.min(Math.max(v, ind.min), ind.max) - ind.min) / (ind.max - ind.min)) * (A - m.t - m.b);
  const completa = (vals) => vals && vals.length === 6 && vals.every((v) => v !== null);
  const linhas = [
    { vals: TIPICAS.Campo && TIPICAS.Campo[nome], cor: "#6E8F3A", tracejada: true, rotulo: "Campo típico" },
    { vals: TIPICAS.Lavoura && TIPICAS.Lavoura[nome], cor: "#B08A2E", tracejada: true, rotulo: "Lavoura típica" },
    { vals: serie && serie[nome], cor: "#E4572E", tracejada: false, rotulo: "esta mancha" },
  ].filter((l) => completa(l.vals));
  const desenho = linhas.map((l) => `<polyline fill="none" stroke="${l.cor}" stroke-width="${l.tracejada ? 1.8 : 2.8}" stroke-linejoin="round"${l.tracejada ? ' stroke-dasharray="4 3"' : ""} points="${l.vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ")}"/>`).join("");
  // Rótulo na ponta de cada linha, afastando os que ficariam sobrepostos (no mínimo 14 px entre eles)
  const pontas = linhas.map((l) => ({ ...l, yr: y(l.vals[5]) })).sort((a, b) => a.yr - b.yr);
  pontas.forEach((p, i) => { if (i && p.yr - pontas[i - 1].yr < 14) p.yr = pontas[i - 1].yr + 14; });
  const excesso = pontas.length ? pontas[pontas.length - 1].yr - (A - m.b) : 0;
  if (excesso > 0) pontas.forEach((p) => { p.yr -= excesso; });
  const rotulos = pontas.map((p) => `<text class="rotulo-linha" x="${x(5) + 6}" y="${(p.yr + 4).toFixed(1)}" style="fill:${p.cor}">${p.rotulo}</text>`).join("");
  const marcas = [ind.min, (ind.min + ind.max) / 2, ind.max].map((v) =>
    `<line x1="${m.e}" x2="${x(5)}" y1="${y(v)}" y2="${y(v)}"/><text x="${m.e - 4}" y="${y(v) + 4}" text-anchor="end">${fmt(v, 1)}</text>`).join("");
  // Bimestres em duas alturas alternadas, para caberem por extenso sem se sobrepor
  const meses = BIMESTRES_CURTOS.map((r, i) => `<text x="${x(i)}" y="${A - m.b + 21 + (i % 2) * 15}" text-anchor="middle">${r}</text>`).join("");
  return `<svg class="minigrafico" viewBox="0 0 ${L} ${A}" role="img" aria-label="${NOMES_INDICE[nome]} por bimestre: esta mancha, Lavoura típica e Campo típico">`
    + `<text class="eixo-y" x="0" y="13">${EIXO_Y[nome]}</text>`
    + marcas + meses + desenho + rotulos + "</svg>";
}
const pct = (v) => `${Math.round(100 * v)}%`;
function conteudoPopup(props, nome) {
  nome = nome || (ABAS_BALAO.includes(indiceAtual) ? indiceAtual : "ndvi");
  let corpo = `<b class="titulo-mancha">Mancha de areal · ${fmt(props.area_ha)} ha</b>`;
  const numeros = [];
  if (props.f !== undefined && props.f !== null) {
    const tipica = TIPICAS.Lavoura && TIPICAS.Lavoura.freq;
    numeros.push(`Exposta em ${pct(props.f)} das cenas de __ANO__` + (tipica !== undefined ? ` (lavoura típica: ${pct(tipica)})` : ""));
  }
  const mb = typeof props.mb === "string" ? JSON.parse(props.mb) : props.mb;
  if (mb && mb.length) numeros.push(`No MapBiomas: ${mb.map(([classe, p]) => `${p}% ${classe}`).join(" · ")}`);
  if (numeros.length) corpo += `<p class="mini-numeros">${numeros.map((n) => `<span>${n}</span>`).join("")}</p>`;
  const serie = typeof props.s === "string" ? JSON.parse(props.s) : props.s;
  if (serie) {
    corpo += `<div class="mini-abas">${ABAS_BALAO.map((k) =>
      `<button type="button" class="mini-aba" data-ind="${k}" aria-pressed="${k === nome}">${NOMES_INDICE[k]}</button>`).join("")}</div>`
      + miniGrafico(serie, nome)
      + `<p class="como-ler">${COMO_LER[nome]}</p>`
      + `<small>Medianas bimestrais de __ANO__. Lavoura e Campo típicos são a mediana dos polígonos de amostra.</small>`;
  }
  return `<div class="popup-areal">${corpo}</div>`;
}

// Liga e desliga um índice espectral: fundo Sentinel-2, classes desligadas e manchas de areal só em contorno
const seletorIndice = document.getElementById("indice");
const legendaClasses = document.getElementById("legenda");
const legendaIndice = document.getElementById("legenda-indice");
function definirIndice(nome, restaurarClasses = true) {
  if (!INDICES[nome]) nome = "";
  indiceAtual = nome;
  seletorIndice.value = nome;
  const ind = INDICES[nome];
  periodo.min = ind && !ind.anual ? 1 : 0;
  if (ind && !ind.anual && indicePeriodo === 0) indicePeriodo = 1;
  legendaIndice.hidden = !ind;
  legendaClasses.hidden = !!ind;
  if (ind) {
    document.getElementById("li-nome").textContent = ind.rotulo;
    document.getElementById("li-barra").style.background = ind.gradiente;
    document.getElementById("li-min").textContent = fmt(ind.min, 1);
    document.getElementById("li-max").textContent = fmt(ind.max, 1);
    document.getElementById("li-significado").textContent = ind.significado;
    classes.setOpacity(0);
    areal.setOpacity(0);
    if (seletorFundo.value !== "s2") { seletorFundo.value = "s2"; escolherFundo("s2"); }
    else mostrarPeriodo(indicePeriodo);
  } else {
    if (restaurarClasses) destacar(classeFixa);
    if (seletorFundo.value === "s2") mostrarPeriodo(indicePeriodo);
  }
  ctrlPeriodo.hidden = seletorFundo.value !== "s2" || PERIODOS.length < 2 || !!(ind && ind.anual);
  atualizarContornos();
}
seletorIndice.addEventListener("change", () => definirIndice(seletorIndice.value));
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

function definirComparacao(novo) {
  comparaCom.value = novo;
  modo = novo;
  ["divisor", "linha", "lado-esq", "lado-dir"].forEach((id) => (document.getElementById(id).hidden = !modo));
  document.getElementById("leg-outras").hidden = modo !== "mapbiomas";
  document.getElementById("lado-dir").textContent =
    modo === "mapbiomas" ? "MapBiomas 10 m (__ANO_MB__)" : "Imagem de fundo";
  if (mapbiomas) { if (modo === "mapbiomas") mapbiomas.addTo(mapa); else mapbiomas.remove(); }
  recortar();
}
comparaCom.addEventListener("change", () => definirComparacao(comparaCom.value));
divisor.addEventListener("input", recortar);
["mousedown", "touchstart"].forEach((ev) => divisor.addEventListener(ev, () => mapa.dragging.disable()));
["mouseup", "touchend"].forEach((ev) => divisor.addEventListener(ev, () => mapa.dragging.enable()));
mapa.on("move zoom resize", recortar);
if (window.matchMedia("(max-width: 899px)").matches) {
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
function mostrarBalao(link, conteudo) {
  clearTimeout(fecharDepois);
  balao.innerHTML = conteudo;
  balao.hidden = false;
  const r = link.getBoundingClientRect();
  const largura = balao.offsetWidth, altura = balao.offsetHeight;
  balao.style.left = Math.max(8, Math.min(r.left + scrollX, scrollX + document.documentElement.clientWidth - largura - 8)) + "px";
  const cabeEmbaixo = r.bottom + 6 + altura <= document.documentElement.clientHeight || r.top < altura + 12;
  balao.style.top = (cabeEmbaixo ? r.bottom + 6 : r.top - altura - 6) + scrollY + "px";
  requestAnimationFrame(() => balao.classList.add("visivel"));
}
function abrirCitacao(link) {
  const ref = document.querySelector(link.getAttribute("href"));
  if (!ref) return;
  mostrarBalao(link, ref.innerHTML + (ref.dataset.doi
    ? `<br><a class="botao-doi" href="https://doi.org/${ref.dataset.doi}" target="_blank" rel="noopener">DOI ↗</a>` : ""));
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
document.addEventListener("click", (e) => { if (citaAberta && !balao.contains(e.target) && !e.target.closest(".cita, .botao-ajuda")) fecharCitacao(); });

// Botão "?" da legenda do índice: abre o cartão "Como ler os índices" do índice ligado
const botaoAjuda = document.getElementById("li-ajuda");
botaoAjuda.addEventListener("click", () => {
  if (citaAberta === botaoAjuda) { fecharCitacao(); return; }
  const cartao = document.getElementById("indice-" + indiceAtual);
  if (!cartao) return;
  mostrarBalao(botaoAjuda, `<div class="cartao-indice-balao">${cartao.innerHTML}</div>`);
  balao.querySelectorAll("details").forEach((d) => (d.open = true));
  if (citaAberta) citaAberta.setAttribute("aria-expanded", "false");
  citaAberta = botaoAjuda;
  botaoAjuda.setAttribute("aria-expanded", "true");
});

// Linha do tempo: "O que ficou em aberto →" leva ao marco seguinte
document.querySelectorAll(".marco-aberto a").forEach((a) => a.addEventListener("click", (e) => {
  e.preventDefault();
  document.querySelector(a.getAttribute("href")).scrollIntoView({
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    block: "nearest", inline: "start" });
}));
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && citaAberta) { const l = citaAberta; fecharCitacao(); l.focus(); } });

// ---------------------------------------------------------------- Abas reutilizáveis
function criarAbas(idContainer, opcoes, aoEscolher) {
  const caixa = document.getElementById(idContainer);
  const botoes = opcoes.map(([chave, rotulo], i) => {
    const b = document.createElement("button");
    b.className = "botao"; b.type = "button"; b.textContent = rotulo; b.dataset.chave = chave;
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
// Clicar numa aba mostra no mapa o índice correspondente (só cliques de verdade, não a aba inicial)
const VARIAVEL_INDICE = { FREQ_EXPOSTO: "freq", NDVI_medio: "ndvi", NDVI_amp: "ndvi", NDVI_min: "ndvi", BSI_med: "bsi", NDWI_med: "ndwi" };
document.getElementById("abas-assinatura").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  const nome = b && VARIAVEL_INDICE[b.dataset.chave];
  if (e.isTrusted && nome && INDICES[nome]) definirIndice(nome);
});

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

// ---------------------------------------------------------------- Mapa em tela cheia (celular) e redimensionamento
const colunaMapa = document.getElementById("coluna-mapa");
const botaoExpandir = document.getElementById("expandir");
let mapaAberto = false;
const ajustarMapa = () => requestAnimationFrame(() => { mapa.invalidateSize(); recortar(); });
botaoExpandir.addEventListener("click", () => {
  mapaAberto = !mapaAberto;
  colunaMapa.classList.toggle("tela-cheia", mapaAberto);
  document.body.classList.toggle("mapa-aberto", mapaAberto);
  botaoExpandir.textContent = mapaAberto ? "Fechar" : "Expandir mapa";
  botaoExpandir.setAttribute("aria-expanded", mapaAberto);
  ajustarMapa();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && mapaAberto) botaoExpandir.click(); });
window.addEventListener("resize", ajustarMapa);

// ---------------------------------------------------------------- Story map: o texto conduz o mapa
const CASO = __CASO__;   // limites da maior mancha de areal sobre lavoura do MapBiomas (ou null)
const semAnimacao = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const itemAreal = document.querySelector('.item-classe[data-classe="1"]');
const CENAS = {
  "mapa-secao": { fundo: "s2", classes: "todas" },
  contexto: { fundo: "esri", classes: "nenhuma" },
  dados: { fundo: "esri", classes: "nenhuma" },
  metodo: { fundo: "s2", classes: "nenhuma", indice: "ndvi", play: true },
  resultados: { fundo: "s2", classes: "todas" },
  validacao: { fundo: "s2", classes: "areal" },
  comparacao: { fundo: "s2", classes: "todas", comparar: "mapbiomas", vista: "caso" },
  limitacoes: { fundo: "s2", classes: "nenhuma", indice: "ndwi" },
  referencias: { fundo: "s2", classes: "todas" },
};
let movimentoAuto = false, secaoAtual = null, pausadaEm = null;

function voar(alvo, zoomMaximo = 15) {
  movimentoAuto = true;
  if (semAnimacao) {
    mapa.fitBounds(alvo, { animate: false, maxZoom: zoomMaximo });
    movimentoAuto = false;
    return;
  }
  mapa.once("moveend", () => (movimentoAuto = false));
  mapa.flyToBounds(alvo, { duration: 1.2, maxZoom: zoomMaximo, padding: [24, 24] });
}
function mostrarClasses(estado) {
  classeFixa = null;
  if (estado === "areal" && itemAreal) { destacar(itemAreal); return; }
  destacar(null);
  if (estado === "nenhuma") { classes.setOpacity(0); areal.setOpacity(0); }
}
function aplicarCena(id) {
  const cena = CENAS[id];
  if (!cena) return;
  const fundo = cena.fundo === "s2" && !PERIODOS.length ? "esri" : cena.fundo;
  if (seletorFundo.value !== fundo) { seletorFundo.value = fundo; escolherFundo(fundo); }
  definirComparacao(cena.comparar && mapbiomas ? cena.comparar : "");
  definirIndice(cena.indice || "", false);
  mostrarClasses(cena.classes);
  tocar(!!cena.play && fundo === "s2" && PERIODOS.length > 1);
  if (cena.vista === "caso" && CASO) voar(CASO, 14); else voar(limites);
}

// Interação manual pausa a condução até a próxima seção
function pausarConducao() {
  pausadaEm = secaoAtual;
  if (movimentoAuto) { mapa.stop(); movimentoAuto = false; }
}
mapa.on("dragstart", pausarConducao);
mapa.on("zoomstart", () => { if (!movimentoAuto) pausarConducao(); });
const areaMapa = document.querySelector(".area-mapa");
areaMapa.addEventListener("pointerdown", (e) => { if (e.target.closest(".controles, .legenda, .divisor")) pausarConducao(); });
["input", "change"].forEach((ev) => areaMapa.addEventListener(ev, (e) => { if (e.isTrusted) pausarConducao(); }));

const linksMenu = [...document.querySelectorAll(".menu a")];
const ehCelular = window.matchMedia("(max-width: 899px)").matches;
const observador = new IntersectionObserver((entradas) => {
  entradas.forEach((e) => {
    if (!e.isIntersecting) return;
    const id = e.target.id;
    linksMenu.forEach((a) => a.classList.toggle("ativo", a.getAttribute("href") === "#" + id));
    if (id === secaoAtual) return;
    secaoAtual = id;
    if (pausadaEm && pausadaEm !== id) pausadaEm = null;
    if (!pausadaEm && !mapaAberto) aplicarCena(id);
  });
}, { rootMargin: ehCelular ? "-55% 0px -40% 0px" : "-35% 0px -60% 0px" });
linksMenu.forEach((a) => observador.observe(document.querySelector(a.getAttribute("href"))));
</script>
</body>
</html>
"""
