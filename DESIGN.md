---
name: Areais do Pampa – FTL
version: 2.0
description: >
  Identidade visual do mapa web e da página do projeto "Mapeamento de áreas de
  arenização com Sentinel-2 e Random Forest" (Future Tech Leaders Brasil – Space
  Tech Bootcamp 2026). Tema de areia, com a paisagem do Pampa arenizado como
  base (areia, campo e vento) e o roxo do FTL apenas como acento.
tokens:
  color:
    claro:
      fundo: "#F6EFE3"          # fundo da página, com textura de areia
      painel: "#EDE2CE"         # cartões, painéis do mapa, balões
      borda: "#D9C6A5"          # bordas, linhas de tabela, linhas de vento
      texto: "#2B2420"          # texto principal e números dos cartões
      texto-secundario: "#6B5E52"
      acento: "#4617DE"         # roxo FTL: botões, links, controle ativo, foco
      sobre-acento: "#FFFFFF"   # texto sobre o acento
    escuro:
      fundo: "#1F1A15"
      painel: "#2A231C"
      borda: "#4A3E32"
      texto: "#F1E8DA"
      texto-secundario: "#BFAF98"
      acento: "#8F7CFF"
      sobre-acento: "#1F1A15"   # branco sobre #8F7CFF não chega a 4,5:1
    # Classes do mapa (não usar em elementos de interface)
    classe-areal: "#E4572E"
    classe-campo: "#A8C66C"
    classe-lavoura: "#F2C14E"
    classe-silvicultura: "#7A5900"
    classe-agua: "#2E86C1"
    classe-vegetacao-nativa: "#2D6A4F"
    outras-mapbiomas: "#B9B4C7"
  typography:
    titulo: "Space Grotesk, system-ui, sans-serif"   # 600–700
    corpo: "Inter, system-ui, sans-serif"            # 400–500
    numeros: "Inter, tabular-nums"                   # métricas e áreas
    escala: { h1: 34px, h2: 26px, h3: 19px, corpo: 16px, legenda: 13px }
  spacing: { base: 8px, escala: [4, 8, 16, 24, 32, 48, 64] }
  radius: { pequeno: 6px, cartao: 14px, pilula: 999px }
  shadow:
    cartao: "0 2px 10px rgba(43, 36, 32, 0.08)"
  motion:
    duracao: 200ms
    transicao-imagens: 400ms   # troca cruzada da linha do tempo Sentinel-2
    voo-do-mapa: 1200ms        # condução do mapa pelo texto (flyTo)
    curva: "cubic-bezier(0.2, 0.7, 0.2, 1)"
---

# Areais do Pampa – sistema de design

## Ideia

O projeto fala de **areia exposta num campo verde, moldada pelo vento**. A página
inteira é cor de areia, com textura leve de grão e linhas de vento como divisores;
o mapa é o protagonista. O roxo do Future Tech Leaders aparece só como acento.

Regra central: **a página é areia, o mapa é a paisagem, o roxo é a ação.** As
cores das classes nunca viram botões ou títulos, e o roxo nunca entra no mapa.

## Cores

- **Fundo e painéis:** fundo `#F6EFE3` e painéis `#EDE2CE` no modo claro; `#1F1A15`
  e `#2A231C` no escuro. Não usar branco puro nem preto puro.
- **Roxo só como acento:** botões, links, controle ativo (aba, item do menu) e foco.
  **Nenhum fundo roxo** em cabeçalho, cartões, painéis ou tabelas. Destaques de
  tabela usam texto e borda em roxo sobre fundo de areia.
- **Números dos cartões** na cor do texto (`#2B2420` / `#F1E8DA`), sem cor de marca.
- **Contraste mínimo de 4,5:1** para todo texto, nos dois modos. O texto secundário
  (`#6B5E52` / `#BFAF98`) passa sobre o fundo e sobre os painéis. No modo escuro, o
  texto sobre o acento é escuro (`#1F1A15`), porque branco sobre `#8F7CFF` dá 3,2:1.
- O vermelho e o limão do FTL não são usados: competiriam com o Areal no mapa.

### Classes do mapa

| Classe | Cor | Por quê |
|---|---|---|
| Areal | `#E4572E` | Terracota viva: a classe que importa, a mais saturada do mapa |
| Lavoura | `#F2C14E` | Amarelo-palha: tom diferente do Areal (amarelo × vermelho-alaranjado), para não confundir as duas |
| Campo | `#A8C66C` | Verde-pampa claro: a matriz da paisagem, discreta |
| Vegetação Nativa | `#2D6A4F` | Verde-mata escuro |
| Silvicultura | `#7A5900` | Oliva-castanho, próximo da convenção do MapBiomas |
| Água | `#2E86C1` | Azul convencional |

- O **Areal** fica sempre na camada de cima e com opacidade 100%; as outras
  classes podem ir a 70–80% para o Areal saltar.
- A legenda lista o **Areal primeiro** e mostra a área de cada classe em km².
- Não depender só da cor: a legenda tem os nomes escritos e o Areal tem contorno
  fino (`#8A2A12`, 0,5 px) quando o zoom permitir.

## Textura e vento

- **Textura de areia:** ruído SVG (`feTurbulence`, `baseFrequency` 0,9, 2 oitavas)
  como data URI no fundo da página, com opacidade de 5–8%. Nunca sobre o mapa, as
  tabelas ou os painéis, que têm fundo sólido.
- **Linhas de vento:** uma linha ondulada suave, com 2–3 ondulações, em `#D9C6A5`
  (claro) / `#4A3E32` (escuro), 1,5 px. Usar no rodapé do cabeçalho e como divisor
  entre seções; no máximo uma por seção; nunca sobre o mapa.
- Nada de faixas coloridas laterais, gradientes ou ícones decorativos soltos.

## Índices espectrais no mapa

- Fonte: pilha das medianas bimestrais (camadas de apoio). Rotular sempre como
  **"medianas bimestrais"**, exceto a frequência de solo exposto, que é a própria
  variável do modelo.
- Escala fixa por índice em todos os bimestres: NDVI −0,2 a 0,9; NDWI e BSI −0,6 a
  0,6; frequência de solo exposto 0 a 1.
- Rampas: NDVI marrom → verde; NDWI branco → azul; BSI e frequência em *cividis*.
  **Nada de laranja ou terracota**, que se confundiriam com o Areal.
- Com um índice ligado, as classes ficam desligadas e as manchas de areal aparecem
  só em contorno (branco sobre NDVI; quase preto sobre NDWI, BSI e frequência).
- Legenda do índice: nome, período, barra de cores com a escala e o significado
  das cores.
- Minigráfico da mancha (ao clicar): mancha em `classe-areal` contínua; Lavoura
  (`#B08A2E`) e Campo (`#6E8F3A`) típicos tracejados. A faixa do eixo é fixa por
  índice, tirada dos dados, igual para todas as manchas.

## Tipografia

- **Space Grotesk** nos títulos: geométrica e técnica, conversa com o logo do FTL.
- **Inter** no texto e nos números, com algarismos tabulares (`font-variant-numeric:
  tabular-nums`) para que áreas e métricas se alinhem.
- Títulos sem ponto final. Texto alinhado à esquerda; centralizar só títulos curtos.

## Layout: story map

- **Desktop (≥ 900 px):** duas colunas. À esquerda, o mapa (~58%), fixo na tela
  (`position: sticky`, 100vh); à direita (~42%), a coluna de texto que rola, com o
  cabeçalho, o menu e os cartões de número no topo.
- **Celular (< 900 px):** uma coluna; o mapa fica fixo no topo com 45vh e o texto
  rola embaixo. Um botão "Expandir mapa" abre o mapa em tela cheia.
- **O texto conduz o mapa:** cada seção define uma cena (fundo, classes visíveis,
  comparação e enquadramento), aplicada com um voo de 1,2 s. Mexer no mapa pausa a
  condução até a próxima seção. Com `prefers-reduced-motion`, a troca é direta.

## Componentes

- **Painéis do mapa:** camadas e linha do tempo (canto superior esquerdo) e legenda
  (canto inferior esquerdo), recolhíveis, em `painel`, raio `cartao`. Nunca no
  centro do mapa. No celular, começam recolhidos.
- **Cartões de número:** número grande em Space Grotesk e rótulo pequeno embaixo,
  em grade 2 × 2. Ex.: "XX km² de areal", "XX% da bacia", "F1 do Areal 0,XX".
- **Botões:** pílula com fundo roxo (ação principal) ou contorno roxo (secundário).
- **Comparação com o MapBiomas:** controle deslizante lado a lado (swipe).
- **Citações:** link sublinhado pontilhado que abre um balão com a referência e o DOI.
- **Linha do tempo dos trabalhos:** marcos (ano, autor, papel, texto e "O que ficou em
  aberto →", que leva ao marco seguinte) ligados por uma linha de vento. Horizontal com
  rolagem no desktop e vertical no celular. O marco deste projeto tem contorno e ano em
  roxo, sem fundo roxo.
- **Cartões dos índices:** sigla, nome, barra com a mesma rampa do mapa, texto e a
  fórmula num `<details>` "Ver fórmula". O botão "?" da legenda do índice abre o cartão
  num balão.

## Faça / evite

**Faça**
- Deixar o mapa falar: pouco texto ao redor, números grandes e poucos.
- Citar as fontes no rodapé: Sentinel-2 (ESA/Copernicus), MapBiomas, SEMA-RS, ANA.
- Testar com 1.440 px, 1.024 px e 390 px, nos modos claro e escuro.

**Evite**
- Fundos roxos; o roxo é só acento.
- Animações longas: interface em até 200 ms; só a troca de imagens (400 ms) e o
  voo do mapa (1,2 s) passam disso.
- Rótulos de classe só em inglês: a página é em português.
- Ponto e vírgula no texto da página: usar frases separadas ou "e", "mas", "porque".
  Só as referências (ABNT) mantêm o ponto e vírgula entre autores.
