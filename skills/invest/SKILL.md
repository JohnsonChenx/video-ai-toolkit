---
name: invest
description: Estilo de edição "Invest" — notícia/economia dinâmica em vídeo vertical. Use quando o usuário pedir edição "estilo invest", "estilo notícia dinâmica", "edição de jornalismo econômico" ou similar. Define a estética completa (legendas bloco-caps, cartões de dados, manchetes como prova, flash de ênfase, ritmo denso) e a receita para aplicá-la com as ferramentas do agente editor desta suíte.
---

# Estilo Invest — edição dinâmica de notícia/economia

Estética extraída da análise frame a frame de vídeos verticais de jornalismo
econômico brasileiro (formatos curto e longo). Objetivo: aplicar as TÉCNICAS ao
vídeo do usuário — nunca clonar marca, vinheta ou identidade de nenhum canal.

## Os dois modos

| | NEWS RÁPIDO (30s–3min) | ANÁLISE LONGA (8min+) |
|---|---|---|
| Densidade visual | 40–65 eventos/min (algo muda a cada ~1-1,5s) | ~7 eventos/min |
| Cenário | estúdio virtual: fundo em cor sólida vibrante | ambiente real neutro |
| Uso | manchete única, dado do dia | tema com múltiplos capítulos |

Escolha o modo pela duração-alvo do vídeo final. Em dúvida: rápido.

## As 10 assinaturas visuais

1. **Apresentador central, peito pra cima**, olhando pra câmera. Punch-in/out de
   zoom entre frases (dois enquadramentos alternados).
2. **Legendas em BLOCO CAPS** — TODAS MAIÚSCULAS, brancas com contorno escuro
   fino, blocos curtos (2–6 palavras), posição central na **altura do peito**
   (não no rodapé). Trocam rápido acompanhando a fala. NÃO é karaokê — é bloco
   seco que corta de uma vez.
3. **Fundo troca de cor como transição** (modo rápido): cores sólidas vibrantes
   (roxo → azul-violeta) com formas geométricas brancas em diagonal que mudam
   entre planos. A própria troca É a transição.
4. **Logos como personagens**: empresa citada = logo "pop" ao lado da cabeça
   (um por vez, empilhando). Em b-roll, o logo entra GRANDE sobreposto.
5. **Cartão de dados ("tira de etiqueta")**: chip de título curto ("Prejuízo:")
   + tiras brancas empilhadas com texto preto, um dado por tira. **Persistem na
   tela** enquanto o assunto continua — inclusive sobre b-roll. Número vira imagem.
6. **Manchete real como prova**: screenshot da matéria de veículo conhecido
   ocupando a tela, logo do veículo visível, foto levemente dessaturada.
7. **Flash duotônico de ênfase**: na frase de virada, UM plano com o apresentador
   em monocromo saturado (laranja/rosa). Dura a frase, volta ao normal. 1–2x por vídeo.
8. **B-roll temático curto** nos exemplos concretos, frequentemente dessaturado,
   com whip-pan (borrão) na entrada/saída.
9. **Nuvem de logos por categoria** (modo longo): a tela enche de logos do
   segmento citado ao redor do apresentador (fundo dessaturado), título da
   categoria em lettering grande.
10. **Elemento nacional**: bandeira do país ao fundo quando o assunto é nacional.

## Estrutura narrativa

- **0–3s: gancho** — pergunta direta ou dado-choque.
- **Desenvolvimento em LISTA de exemplos concretos** — cada item ganha seu
  evento visual (logo/card/b-roll).
- **Fechamento com punchline informal.**
- Tom: coloquial-informado + números sempre exatos.

## Receita de aplicação (ferramentas da suíte)

Ordem de montagem sobre o vídeo já cortado (3 passadas do agente editor):

1. **Legendas bloco-CAPS**: `apps/editor/gen_bloco_caps.py`
   ```bash
   python apps/editor/gen_bloco_caps.py <transcricao.json> caps.ass [560] [66]
   ```
   ⚠️ Ao conferir com frame: `-ss` DEPOIS do `-i` (antes zera timestamps e o
   filtro ass não renderiza).
2. **Punch-in**: alternar crop 100% ↔ ~112% entre frases longas.
3. **Cartões de dados**: para CADA número citado, montar a tira (Remotion com
   fundo branco/texto preto, ou PNG via HTML→screenshot). Manter até o assunto mudar.
4. **Manchetes**: `apps/editor/web-shot/` na matéria citada; tela cheia 2–3s
   com leve dessaturação (`eq=saturation=0.5`).
5. **Flash duotônico**: no trecho de ênfase, monocromo quente pela duração da
   frase. Ex.: `-vf "colorchannelmixer=.9:.5:.2:0:.4:.3:.1:0:.2:.2:.1"`.
6. **Logos**: capturar do site oficial via web-shot (`--sel "header img"` /
   `".logo img"`; fallback: print do topo + crop medido no frame). Não inventar
   nem desenhar logos.
7. **Whip-pan nas trocas de bloco**: ~0,25s com blur de movimento (fallback
   aceitável: corte seco).
8. **Fundo colorido — decisão automática**: olhe 1 frame do bruto. Parede lisa
   de cor única/chroma → `colorkey` + fundo vibrante com formas diagonais,
   alternando cor entre blocos (teste o key num frame antes; vazamento no
   cabelo → pular). Fundo real complexo → PULAR sem perguntar — as assinaturas
   2, 5, 6 e 7 já entregam a estética.

## Limites honestos

- Fundo real complexo → sem troca de fundo colorido (decisão automática acima).
- Logos de terceiros: capturar do site oficial; não inventar.
- B-roll de banco de imagens não é automático — sem acervo, manchetes e cartões
  fazem a cobertura visual.
- A estética é aplicada com a identidade DO USUÁRIO — nunca reproduzir marca,
  vinheta ou lettering de canais existentes no vídeo final.

## Gatilhos

"edita no estilo invest" · "estilo notícia dinâmica" · "edição de jornalismo
econômico" · comando de voz: "pato preto, estilo invest".
O agente editor carrega esta skill e segue a receita na FASE B.
