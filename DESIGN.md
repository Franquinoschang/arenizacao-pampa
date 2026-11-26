---
name: Areais do Pampa – FTL
version: 1.0
description: >
  Identidade visual do mapa web e da página do projeto "Mapeamento de áreas de
  arenização com Sentinel-2 e Random Forest" (Future Tech Leaders Brasil – Space
  Tech Bootcamp 2026). Base nas cores do FTL, com a paisagem do Pampa arenizado
  como tema: areia, campo e vento.
tokens:
  color:
    # Base FTL
    ftl-roxo: "#4617DE"        # cor de marca; ações, links, foco
    ftl-vermelho: "#FE2E45"    # destaque pontual de interface; nunca no mapa
    ftl-limao: "#DDFB0B"       # realce sobre fundo escuro (selos, números)
    # Paisagem
    areia-clara: "#FAF6EF"     # fundo da página (modo claro)
    areia-media: "#EADFCB"     # superfícies, cartões, faixas
    duna: "#C9B48F"            # bordas, divisores, linhas de vento
    noite-pampa: "#15122B"     # fundo do modo escuro (céu noturno roxo)
    noite-superficie: "#221D40"
    tinta: "#1E1B2E"           # texto principal no modo claro
    tinta-suave: "#5C566E"     # texto secundário, legendas
    neblina: "#EDEAF5"         # texto principal no modo escuro
    # Classes do mapa (não usar em elementos de interface)
    classe-areal: "#E4572E"
    classe-campo: "#A8C66C"
    classe-lavoura: "#F2C14E"
    classe-silvicultura: "#7A5900"
    classe-agua: "#2E86C1"
    classe-vegetacao-nativa: "#2D6A4F"
  typography:
    titulo: "Space Grotesk, system-ui, sans-serif"   # 600–700
    corpo: "Inter, system-ui, sans-serif"            # 400–500
    numeros: "Inter, tabular-nums"                   # métricas e áreas
    escala: { h1: 40px, h2: 28px, h3: 20px, corpo: 16px, legenda: 13px }
  spacing: { base: 8px, escala: [4, 8, 16, 24, 32, 48, 64] }
  radius: { pequeno: 6px, cartao: 14px, pilula: 999px }
  shadow:
    cartao: "0 2px 10px rgba(30, 27, 46, 0.08)"
  motion:
    duracao: 200ms
    curva: "cubic-bezier(0.2, 0.7, 0.2, 1)"
---

# Areais do Pampa – sistema de design

## Ideia

O projeto fala de **areia exposta num campo verde, moldada pelo vento**. A página
usa a base do Future Tech Leaders (roxo, vermelho e limão) para a interface, e a
paisagem do Pampa para o resto: fundo cor de areia, divisores ondulados como
marcas de vento nas dunas, e o mapa como protagonista.

Regra central: **a interface é roxa, o mapa é a paisagem.** As cores da marca
nunca entram no mapa, e as cores das classes nunca viram botões ou títulos.

## Cores

- **Fundo:** `areia-clara` no modo claro e `noite-pampa` no modo escuro. Não usar
  branco puro nem preto puro.
- **Roxo FTL** é a única cor de ação: links, botões, foco, aba ativa.
- **Vermelho FTL** só em um elemento por tela (por exemplo, o selo "2025" ou um
  alerta). Ele é próximo do Areal, por isso nunca aparece perto do mapa.
- **Limão FTL** só sobre fundo escuro, para números de destaque e selos.
- Texto sempre em `tinta` (claro) ou `neblina` (escuro); contraste mínimo de 4,5:1.

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

## Tipografia

- **Space Grotesk** nos títulos: geométrica e técnica, conversa com o logo do FTL.
- **Inter** no texto e nos números, com algarismos tabulares (`font-variant-numeric:
  tabular-nums`) para que áreas e métricas se alinhem.
- Títulos sem ponto final. Texto alinhado à esquerda; centralizar só títulos curtos.

## Motivo visual: linhas de vento

O único elemento decorativo é uma **linha ondulada suave**, como as marcas que o
vento deixa na areia, em `duna` com 1,5 px de espessura.

- Usar como divisor entre seções e no rodapé do cabeçalho.
- No máximo uma por seção; nunca sobre o mapa.
- Nada de faixas coloridas laterais, gradientes ou ícones decorativos soltos.

## Componentes

- **Cabeçalho:** logo do FTL e dos parceiros à direita, título do projeto à
  esquerda, linha de vento embaixo.
- **Mapa:** ocupa a maior parte da tela (mínimo 70% da altura no desktop). Mapa base
  de satélite com a classificação por cima e um controle de opacidade.
- **Legenda:** cartão `areia-media`, canto inferior esquerdo, raio `cartao`.
- **Cartões de número:** número grande em Space Grotesk (40px) e rótulo pequeno
  embaixo. Ex.: "XX km² de areal", "XX% da bacia", "F1 do Areal 0,XX".
  No modo escuro, o número fica em limão.
- **Botões:** pílula, fundo roxo, texto branco; secundário com contorno roxo.
- **Comparação com o MapBiomas:** controle deslizante lado a lado (swipe) entre os
  dois mapas.

## Faça / evite

**Faça**
- Deixar o mapa falar: pouco texto ao redor, números grandes e poucos.
- Citar as fontes no rodapé: Sentinel-2 (ESA/Copernicus), MapBiomas, ANA.
- Testar no celular: a legenda vira uma gaveta recolhível.

**Evite**
- Vermelho FTL perto do mapa (confunde com o Areal).
- Mais de três cores de marca na mesma tela.
- Animações longas; transições de no máximo 200 ms.
- Rótulos de classe só em inglês: a página é em português.
