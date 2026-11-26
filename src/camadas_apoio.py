"""Camadas de apoio à coleta de amostras no projeto GIS.

Exporta para a pasta `arenizacao` do Google Drive, recortadas na ottobacia 682636
(SIRGAS 2000 / UTM 21S, 10 m):

- rgb_anual      mediana Sentinel-2 de 2025 em cor natural
- rgb_bimestral  6 medianas em cor natural (jan-fev ... nov-dez)
- pilha          NDVI, NDWI e BSI medianos de cada bimestre + FREQ_EXPOSTO (19 bandas,
                 inteiros x 10000) e o CSV com os nomes das bandas em data/processed/
- mapbiomas      MapBiomas 10 m, Coleção 4, classificação de 2025

Uso, na raiz do repositório:
    uv run python src/camadas_apoio.py                 # todas
    uv run python src/camadas_apoio.py pilha mapbiomas # só algumas
"""

import csv
import sys
from pathlib import Path

import ee
import geemap
import geopandas as gpd

PROJETO_GCP = "areanizacao-pampa"
ANO = 2025
CAMINHO_BACIA = Path("data/raw/area_de_estudo.shp")
PASTA_PROCESSADOS = Path("data/processed")
PASTA_DRIVE = "arenizacao"
CRS = "EPSG:31981"
ESCALA = 10
LIMIAR_NUVEM = 0.60
LIMIAR_NDVI_EXPOSTO = 0.25
ASSET_MAPBIOMAS_10M = "projects/mapbiomas-public/assets/brazil/lulc_10m/collection4/mapbiomas_10m_collection4_coverage_v1"

BANDAS = ["B2", "B3", "B4", "B8", "B11", "B12"]
RGB = ["B4", "B3", "B2"]
VIS_RGB = {"bands": RGB, "min": 0.02, "max": 0.18}
BIMESTRES = ["jan_fev", "mar_abr", "mai_jun", "jul_ago", "set_out", "nov_dez"]


def bacia():
    gdf = gpd.read_file(CAMINHO_BACIA).to_crs("EPSG:4326").dissolve()
    return geemap.gdf_to_ee(gdf).geometry()


def colecao(geom):
    # Cenas Sentinel-2 L2A do ano, sem nuvens (Cloud Score+), em reflectância 0–1,
    # com NDVI, NDWI, BSI e a marcação de solo exposto. Mantém a data de cada cena.
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
          .filterBounds(geom).filterDate(f"{ANO}-01-01", f"{ANO + 1}-01-01"))
    cs = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")

    def preparar(img):
        r = img.updateMask(img.select("cs_cdf").gte(LIMIAR_NUVEM)).select(BANDAS).multiply(0.0001)
        ndvi = r.normalizedDifference(["B8", "B4"]).rename("NDVI")
        ndwi = r.normalizedDifference(["B3", "B8"]).rename("NDWI")
        bsi = r.expression(
            "((S1 + R) - (N + B)) / ((S1 + R) + (N + B))",
            {"S1": r.select("B11"), "R": r.select("B4"), "N": r.select("B8"), "B": r.select("B2")},
        ).rename("BSI")
        exposto = ndvi.lt(LIMIAR_NDVI_EXPOSTO).And(bsi.gt(0)).And(ndwi.lt(0)).rename("EXPOSTO").toFloat()
        return r.addBands([ndvi, ndwi, bsi, exposto]).copyProperties(img, ["system:time_start"])

    return s2.linkCollection(cs, ["cs_cdf"]).map(preparar)


def do_bimestre(col, k):
    return col.filter(ee.Filter.calendarRange(2 * k + 1, 2 * k + 2, "month"))


def exportar(imagem, nome, geom, **opcoes):
    tarefa = ee.batch.Export.image.toDrive(
        image=imagem, description=nome, folder=PASTA_DRIVE, region=geom.buffer(200).bounds(),
        scale=ESCALA, crs=CRS, maxPixels=1e13, fileFormat="GeoTIFF", **opcoes,
    )
    tarefa.start()
    print(f"  exportação iniciada: {nome} ({tarefa.id})")


def rgb_anual(geom, col):
    exportar(col.median().visualize(**VIS_RGB).clip(geom), f"sentinel2_rgb_mediana_{ANO}", geom)


def rgb_bimestral(geom, col):
    for k, nome in enumerate(BIMESTRES):
        img = do_bimestre(col, k).median().visualize(**VIS_RGB).clip(geom)
        exportar(img, f"sentinel2_rgb_{ANO}_{k + 1:02d}_{nome.replace('_', '-')}", geom)


def pilha(geom, col):
    descricao = {"NDVI": "NDVI mediano (vegetacao)", "NDWI": "NDWI mediano (agua)", "BSI": "BSI mediano (solo exposto)"}
    camadas, linhas = [], []
    for k, nome in enumerate(BIMESTRES):
        sub = do_bimestre(col, k)
        print(f"  {nome}: {sub.size().getInfo()} cenas")
        med = sub.select(["NDVI", "NDWI", "BSI"]).median()
        for ind in ["NDVI", "NDWI", "BSI"]:
            banda = f"{ind}_{k + 1}_{nome}"
            camadas.append(med.select(ind).rename(banda))
            linhas.append([len(linhas) + 1, banda, f"{descricao[ind]}, {nome.replace('_', '-')} {ANO}", 10000])
    camadas.append(col.select("EXPOSTO").mean().rename("FREQ_EXPOSTO"))
    linhas.append([len(linhas) + 1, "FREQ_EXPOSTO", f"fracao das cenas de {ANO} com solo exposto (NDVI<0,25, BSI>0 e NDWI<0)", 10000])

    img = ee.Image.cat(camadas).multiply(10000).round().toInt16().clip(geom).unmask(-32768)
    exportar(img, f"pilha_indices_bimestrais_{ANO}", geom, formatOptions={"noData": -32768})

    PASTA_PROCESSADOS.mkdir(parents=True, exist_ok=True)
    with open(PASTA_PROCESSADOS / f"pilha_indices_bimestrais_{ANO}_bandas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["banda", "nome", "descricao", "fator_escala"])
        w.writerows(linhas)


def mapbiomas(geom, col):
    img = ee.Image(ASSET_MAPBIOMAS_10M).select(f"classification_{ANO}").clip(geom).toByte()
    exportar(img, "MapBiomas_ottobacia_682636", geom)


CAMADAS = {"rgb_anual": rgb_anual, "rgb_bimestral": rgb_bimestral, "pilha": pilha, "mapbiomas": mapbiomas}


if __name__ == "__main__":
    escolhidas = sys.argv[1:] or list(CAMADAS)
    invalidas = set(escolhidas) - set(CAMADAS)
    if invalidas:
        sys.exit(f"Camadas desconhecidas: {sorted(invalidas)}. Opções: {list(CAMADAS)}")
    ee.Initialize(project=PROJETO_GCP)
    geom = bacia()
    col = colecao(geom)
    print(f"Cenas Sentinel-2 em {ANO}: {col.size().getInfo()}")
    for nome in escolhidas:
        print(nome)
        CAMADAS[nome](geom, col)
    print(f"Acompanhe em https://code.earthengine.google.com/tasks e baixe da pasta '{PASTA_DRIVE}' do Drive.")
