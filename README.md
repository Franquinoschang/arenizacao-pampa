# Mapeamento de áreas de arenização com Sentinel-2 e Random Forest

> Projeto final do **Future Tech Leaders Brasil – Space Tech Bootcamp 2026**

**Autora:** Franqueline Monback Noschang – franqueline.noschang@gmail.com
**Mapa interativo:** https://franquinoschang.github.io/arenizacao-pampa/ _(publicado após a primeira execução completa do notebook)_

![Localização da ottobacia](figures/localizacao_bacia.png)

## 1. Ideia do projeto

Mapear as **áreas de arenização (areais) existentes em 2025** na ottobacia **Miracatu-Taquari** (código 682636, entre Manoel Viana e São Francisco de Assis, sudoeste do RS), com imagens **Sentinel-2** e **Random Forest**.

**Problema.** A arenização é o principal processo de degradação do solo no Pampa gaúcho: em substratos arenosos frágeis, a perda da vegetação forma manchas de areia exposta. Os mapeamentos existentes usam imagens de 30 m ou classes genéricas de "área não vegetada", sem separar o areal de outros solos expostos, sobretudo da lavoura em preparo de solo, que tem resposta espectral parecida numa única data.

**Objetivo e produto final.** Inventário atualizado e aberto dos areais da ottobacia, em 10 m e com acurácia avaliada:

- mapa de classificação de 2025 (GeoTIFF);
- polígonos de areais (shapefile);
- código aberto neste repositório;
- mapa web no GitHub Pages.

## 2. Relevância para os ODS e para o ecossistema espacial

- **ODS 15 – Vida Terrestre**, meta 15.3 (combater a degradação do solo): saber onde estão os areais é o primeiro passo para priorizar manejo e recuperação.
- **ODS 2 – Fome Zero e Agricultura Sustentável:** a arenização reduz a área útil para pecuária e lavoura; o mapa orienta o manejo do solo.
- **ODS 13 – Ação Climática:** os areais respondem a chuvas intensas e ao vento; o inventário é a linha de base para monitorar esses efeitos.

**Contribuição prática.** O inventário será a base de validação de um mapa de suscetibilidade à arenização por AHP, desenvolvido em dissertação de mestrado, e oferece ao ecossistema geoespacial um fluxo aberto e reprodutível para mapear areais com Sentinel-2.

## 3. Literatura de referência

- **Souza e Pires (2017)** mapearam os areais do Arroio Puitã (1984–2014) com Landsat e Máxima Verossimilhança, escolhida entre cinco classificadores, e relatam confusão entre areal com vegetação rala e solo de cultivo por usarem uma imagem por ano. É a referência regional e mostra a lacuna abordada: data única e 30 m.
- **Rayne et al. (2023)** detectaram campos desertificados em Marrocos com Sentinel-2, Google Earth Engine e Random Forest, com 74–76% de acurácia na classe de desertificação. É a referência metodológica e o parâmetro realista de acurácia.

## 4. Área de estudo

| Item | Valor |
|---|---|
| Ottobacia | Miracatu-Taquari (Arroio Miracatu e Arroio Taquari) |
| Código / nível (ANA) | 682636 / 6 |
| Área | 588 km² |
| Municípios | Manoel Viana e São Francisco de Assis – RS |
| Bioma | Pampa |
| Sistema de referência do limite | SIRGAS 2000 (EPSG:4674) |
| Sistema das saídas | SIRGAS 2000 / UTM 21S (EPSG:31981) |

## 5. Dados

Todos os dados são públicos, acessados pelo Google Earth Engine (GEE) ou por download direto.

| Dado | Fonte | Formato | Uso |
|---|---|---|---|
| Sentinel-2 L2A, reflectância de superfície (`COPERNICUS/S2_SR_HARMONIZED`) | ESA/Copernicus, via GEE | Raster, 10–60 m conforme a banda | Índices espectrais e variáveis do modelo |
| Cloud Score+ (`GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`) | Google, via GEE | Raster | Máscara de nuvens |
| Limite da ottobacia 682636 (`data/raw/area_de_estudo.shp`) | ANA – Base Hidrográfica Ottocodificada | Shapefile | Recorte da área de estudo |
| MapBiomas Pampa 10 m (Coleção 4) | MapBiomas | Raster | Apoio à amostragem e comparação |
| Amostras rotuladas (`data/samples/amostras_2025.geojson`) | Produzidas neste projeto | GeoJSON | Treino e validação |

### Dataset de amostras

`data/samples/amostras_2025.geojson` contém polígonos rotulados por **interpretação visual no QGIS** sobre imagens de alta resolução, com apoio da mediana Sentinel-2 e do MapBiomas 10 m. Meta: **100 a 200 amostras por classe**.

| Campo | Tipo | Conteúdo |
|---|---|---|
| `classe` | inteiro | 1 Areal · 2 Campo · 3 Lavoura · 4 Silvicultura · 5 Água |
| `poligono` | inteiro | identificador único do polígono (usado para separar treino e teste) |

O notebook sorteia pontos dentro de cada polígono e lê neles o valor das variáveis. A tabela resultante fica em `data/processed/amostras_variaveis_2025.csv`.

## 6. Metodologia – Machine Learning (Random Forest)

**Ferramentas:** Python no VS Code, com `earthengine-api`, `geemap` e `scikit-learn`.

```
Limite da ottobacia ─► Sentinel-2 L2A 2025 (todas as cenas + máscara de nuvens)
                              │
                              ▼
                 Índices por cena: NDVI, BSI, NDWI
                              │
                              ▼
   Resumo anual por pixel: mediana das bandas, NDVI mínimo,
   NDVI médio e frequência de solo exposto
                              │
   Amostras (GeoJSON) ──► 70% treino ──► Random Forest + ajuste de
                     │                    hiperparâmetros (validação cruzada)
                     └──► 30% teste  ──► matriz de confusão, acurácia, precisão,
                                          recall, F1 e importância por classe
                              │
                              ▼
   Mapa de 2025 (GEE) ─► polígonos de areais ─► GeoTIFF, shapefile e mapa web
```

**Pré-processamento.** Filtrar as cenas Sentinel-2 de 2025, mascarar nuvens com o Cloud Score+ e calcular por cena:

- **NDVI** (vegetação) = (NIR − Vermelho) / (NIR + Vermelho)
- **BSI** (solo exposto) = ((SWIR1 + Vermelho) − (NIR + Azul)) / ((SWIR1 + Vermelho) + (NIR + Azul))
- **NDWI** (água) = (Verde − NIR) / (Verde + NIR)

**Variáveis do modelo** (resumo do ano por pixel):

| Variável | Descrição |
|---|---|
| `B2_med` … `B12_med` | mediana anual das bandas azul, verde, vermelho, NIR, SWIR1 e SWIR2 |
| `NDVI_min` | NDVI mínimo do ano |
| `NDVI_medio` | NDVI médio do ano |
| `FREQ_EXPOSTO` | fração das cenas com solo exposto (NDVI < 0,25 e BSI > 0) |

A **frequência de solo exposto** é a variável que separa areal de lavoura: o areal fica exposto o ano todo; a lavoura, só no preparo do solo.

**Classes:** 1 Areal · 2 Campo · 3 Lavoura · 4 Silvicultura · 5 Água

**Etapas:**

1. **Treino:** Random Forest em **70% das amostras**, com ajuste de hiperparâmetros (**nº de árvores**, **profundidade** e **variáveis por divisão**) por validação cruzada de 5 dobras.
2. **Avaliação:** nos **30% restantes**, com matriz de confusão, acurácia global, precisão, recall, F1 e importância das variáveis por classe (por permutação).
3. **Produtos:** classificação da ottobacia no GEE (`smileRandomForest`), área por classe, comparação com o MapBiomas 10 m, exportação do mapa e dos polígonos de areais e geração do mapa web.

Treino e teste são separados **por polígono** (`StratifiedGroupKFold`), mantendo a proporção das classes, para que pixels vizinhos de um mesmo polígono não fiquem dos dois lados e inflem a acurácia.

**Por que Random Forest.** É uma classificação de pixels com poucas amostras rotuladas (centenas) e variáveis tabulares: o Random Forest funciona bem nesse cenário, é robusto a variáveis correlacionadas, mostra quais variáveis importam e roda nativamente no GEE. Deep Learning exigiria um grande volume de imagens rotuladas, que não existe para areais, e seu ganho principal (forma e textura) pesa pouco, pois o areal se distingue mais pelo comportamento ao longo do ano do que pela forma.

## 7. Estrutura do repositório

```
arenizacao-pampa/
├── data/
│   ├── raw/          # limite da ottobacia (shapefile, ANA)
│   ├── samples/      # amostras rotuladas (GeoJSON)
│   └── processed/    # tabelas geradas pelo notebook
├── notebooks/
│   └── 01_pipeline_arenizacao.ipynb
├── figures/          # mapas e gráficos
├── docs/             # mapa web (GitHub Pages)
├── src/              # funções reutilizáveis
├── pyproject.toml    # ambiente uv
├── requirements.txt  # alternativa ao uv
└── README.md
```

## 8. Instalação

Requisitos: Git, [uv](https://docs.astral.sh/uv/), VS Code com as extensões Python e Jupyter, e uma conta no [Google Earth Engine](https://earthengine.google.com/) vinculada a um projeto do Google Cloud (uso não comercial gratuito).

```bash
git clone https://github.com/Franquinoschang/arenizacao-pampa.git
cd arenizacao-pampa
uv sync
```

Sem uv: `python -m venv .venv`, ative o ambiente e rode `pip install -r requirements.txt`.

### Autenticação no Earth Engine

```bash
uv run earthengine authenticate
```

Depois, no notebook, troque `SEU-PROJETO-GCP` pelo ID do seu projeto do Google Cloud.

## 9. Como executar

1. Abra a pasta no VS Code e selecione o kernel do `.venv`.
2. Abra `notebooks/01_pipeline_arenizacao.ipynb`.
3. As etapas 1 a 4 rodam sem amostras e mostram o mapa da frequência de solo exposto.
4. As etapas 5 a 10 precisam de `data/samples/amostras_2025.geojson`.
5. Para comparar com o MapBiomas 10 m, preencha `ASSET_MAPBIOMAS_10M` na célula de parâmetros com o ID do asset publicado pelo MapBiomas.
6. A etapa 10 gera `docs/index.html`; depois do `git push`, o mapa aparece no GitHub Pages.

Todas as etapas aleatórias usam `SEMENTE = 42`.

## 10. Resultados

_A preencher após a execução: mapa de classificação, matriz de confusão, acurácia global, precisão, recall e F1 por classe, importância das variáveis por classe, área de areal na ottobacia e comparação com o MapBiomas 10 m._

## 11. Limitações e trabalhos futuros

- A resolução de 10–20 m não captura areais muito pequenos ou estreitos.
- Areais sob plantios de silvicultura não aparecem na imagem.
- As amostras vêm de interpretação visual, sem verificação de campo.
- O NDVI mínimo é sensível a nuvens residuais não removidas pela máscara.
- O mapa cobre um único ano (2025). Aplicar o modelo a anos anteriores, para medir a expansão dos areais, fica como extensão futura.

## 12. Referências

- MAPBIOMAS. Pampa – Appendix, ATBD Collection 11 e MapBiomas 10 m Collection 4. Código: github.com/mapbiomas/brazil-pampa. Disponível em: brasil.mapbiomas.org.
- RAYNE, L.; BRANDOLINI, F.; MAKOVICS, J. L. et al. Detecting desertification in the ancient oases of southern Morocco. *Scientific Reports*, v. 13, 2023. DOI: 10.1038/s41598-023-46319-1.
- SOUZA, A. C.; PIRES, C. A. F. Dinâmica da arenização na bacia hidrográfica do Arroio Puitã, oeste do RS, através do mapeamento multitemporal no período de 1984 a 2014. *Revista Brasileira de Geomorfologia*, v. 18, n. 1, p. 185–196, 2017. DOI: 10.20502/rbg.v18i1.1051.

## 13. Licença

Código sob licença **MIT**. Dados produzidos neste projeto sob **CC BY 4.0**. Dados de terceiros seguem as licenças das respectivas fontes.

## 14. Agradecimentos

Future Tech Leaders Brasil, Agência Espacial Brasileira (AEB), SDG AI Lab, UNDP / ICPSD.
Emanuel, professor ao longo do curso.
Marco Antônio da Rosa Soares, amigo e apoiador do projeto.
Professor orientador Romário Trentin.
