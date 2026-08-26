# Suíte de agentes de viagem

Quatro especialistas que se dividem por **domínio de custo**, não por etapa. Cada um
pesquisa, precifica e devolve um bloco pronto para o simulador de orçamento.

| Agente | Responde | Não responde |
|---|---|---|
| `passagens` | Quanto reservar de aéreo e quando comprar | Roteiro, hotel, restaurante |
| `hospedagem` | Onde dormir, que bairro, diária real | Voo, roteiro, restaurante |
| `passeios` | O que fazer, em que ordem, quanto custa | Voo, hotel, restaurante |
| `restaurantes` | Onde jantar e almoçar, por faixa | Voo, hotel, roteiro |

## Como rodar — a ordem não é sugestão

```
1. passagens     → fixa datas, duração viável e os horários de chegada e partida
2. hospedagem    → fixa o bairro-base
3. passeios      → usa o bairro para sequenciar os dias e emite o PLANO DE DIAS
4. restaurantes  → CONSOME o PLANO DE DIAS para casar os jantares
```

**Os passos 3 e 4 são sequenciais, não paralelos.** Rodar `restaurantes` antes de
`passeios` terminar obriga o primeiro a adivinhar a ordem dos dias — e ele vai adivinhar
errado de um jeito que parece certo. Se você rodar em paralelo por pressa, é você que vai
reconciliar duas ordens divergentes depois, e isso custa mais do que a espera economizou.

Peça direto pelo nome quando quiser um só: *"pergunta pro agente de hospedagem se Recoleta
compensa"*.

## O contrato entre passeios e restaurantes

`passeios` emite um bloco **`PLANO DE DIAS`**: uma linha por dia com título, peso
(leve/médio/pesado), bairro onde o dia termina e se tem jantar. Ele é a **fonte única da
verdade sobre a ordem dos dias**.

`restaurantes` recebe esse bloco e o usa literalmente. Se não receber, ele **não inventa a
ordem** — devolve a curadoria indexada por *tipo de dia* e avisa que falta o mapeamento.

Repare no campo `jantar: não`. Um roteiro de 10 dias raramente tem 10 jantares: o voo de
volta ao meio-dia mata a última noite. Sem esse campo, a curadoria vem com uma noite a mais
que não existe.

## Convenções compartilhadas

**Marcação de confiança em todo número.** `✓` conferido na fonte, com data · `~` faixa
estimada de fontes secundárias · `?` não confirmado. Um `?` nunca vira base de orçamento.

**Tudo em reais, para o casal.** A única exceção são itens naturalmente por pessoa —
passagem e seguro — e aí a linha diz "por pessoa". Câmbio de referência declarado em cada
relatório.

**Bloco `PARA O SIMULADOR`** encerra todo relatório, com as chaves que a calculadora de
orçamento consome. É o que faz os quatro se somarem sem retrabalho.

**Verificação final obrigatória.** Cada agente roda uma checklist contra a própria saída
antes de devolver, corrige o que falhou e reporta o placar numa última linha
(`Verificação: 7/7 · nada`). Existe porque agente enuncia regra e depois a viola: numa
rodada real, `restaurantes` escalou duas noites caras consecutivas violando a própria
regra de serrilhado.

**Relatório salvo cedo** em `pesquisa/<agente>-<destino>-<AAAA-MM-DD>.md`, não no fim. O slug
do destino é obrigatório: sem ele, duas viagens pesquisadas no mesmo dia se sobrescrevem — foi
o que aconteceu numa rodada real, e o relatório de Lisboa só sobreviveu porque já estava commitado. Se a escrita
falhar por política do ambiente, o agente registra `[relatório não persistido: <motivo>]` e
segue — o texto devolvido é o entregável, o arquivo é conveniência.

## O que sobra para quem orquestra

Os agentes não conversam entre si. Mesmo com o `PLANO DE DIAS`, quem coordena ainda precisa:

- **Deduplicar custos que aparecem em dois relatórios.** Fado entrou como experiência em
  `passeios` e como consumo em `restaurantes`; jantar de excursão entra nos dois. Some uma
  vez e diga qual removeu.
- **Conferir a aritmética consolidada.** Cada agente fecha a própria conta; ninguém fecha a
  soma. Rode a soma você.
- **Conferir se nada foi sobrescrito.** Agentes do mesmo tipo rodando em paralelo para viagens
  diferentes gravam em caminhos parecidos. Rode `git status` depois de cada rodada.
- **Reaplicar as regras de sequência depois de mesclar.** Reordenar dias na consolidação
  pode recriar exatamente o problema que a verificação do agente resolveu.

## As regras de julgamento que os quatro herdam

Vieram de planejamentos reais e são o que separa uma pesquisa de uma recomendação:

- **Orçamento único do casal.** Só a hospedagem divide entre dois — passagem, comida e
  passeios dobram. O que divide de verdade: táxi, remis contratado e aluguel de carro. A
  dois, transporte fechado quase sempre bate o bilhete por pessoa.
- **A passagem decide se a viagem cabe.** É 20 a 35% do total e a despesa mais volátil.
  Resolva-a primeiro. Em destino intercontinental ela reescreve a escala do problema inteiro.
- **Nunca entregue um número que cabe raspando.** Folga fina não sobrevive ao primeiro
  imprevisto. Se sua recomendação só cabe assim, diga e ofereça o corte que devolve margem.
- **Diga o que não cabe, com o número.** Vale para um passeio e vale para a viagem toda:
  "isto custa R$ 30.000 e o teto é R$ 15.000" é a resposta útil.
- **Separe o que é pago em reais do que é gasto em destino.** O primeiro está protegido do
  câmbio; o segundo não.
- **Faixas, não pontos.** Preço sem data de consulta é ficção. Preço sem faixa é falsa precisão.
- **Confirme que ainda existe.** Restaurante fecha, museu entra em obras, guia não avisa.
