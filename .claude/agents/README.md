# Suíte de agentes de viagem

Quatro especialistas que se dividem por **domínio de custo**, não por etapa. Cada um
pesquisa, precifica e devolve um bloco pronto para o simulador de orçamento.

| Agente | Responde | Não responde |
|---|---|---|
| `passagens` | Quanto reservar de aéreo e quando comprar | Roteiro, hotel, restaurante |
| `hospedagem` | Onde dormir, que bairro, diária real | Voo, roteiro, restaurante |
| `passeios` | O que fazer, em que ordem, quanto custa | Voo, hotel, restaurante |
| `restaurantes` | Onde jantar e almoçar, por faixa | Voo, hotel, roteiro |

## Como rodar

A ordem importa, porque cada um depende do que o anterior fixou:

```
1. passagens     → fixa datas e duração viável
2. hospedagem    → fixa o bairro-base
3. passeios      → usa o bairro para sequenciar os dias  ┐ podem rodar
4. restaurantes  → usa os dias para casar os jantares    ┘ em paralelo
```

Os passos 3 e 4 são independentes entre si e podem rodar ao mesmo tempo. Peça direto pelo
nome quando quiser um só: *"pergunta pro agente de hospedagem se Recoleta compensa"*.

## Convenções compartilhadas

**Marcação de confiança em todo número.** `✓` conferido na fonte, com data · `~` faixa
estimada de fontes secundárias · `?` não confirmado. Um `?` nunca vira base de orçamento.

**Tudo em reais, para o casal.** A única exceção são itens naturalmente por pessoa —
passagem e seguro — e aí a linha diz "por pessoa". Câmbio de referência declarado em cada
relatório; agosto de 2026 usou R$ 1 ≈ 290 ARS e US$ 1 ≈ R$ 5,15.

**Bloco `PARA O SIMULADOR`** encerra todo relatório, com as chaves que a calculadora de
orçamento consome. É o que faz os quatro se somarem sem retrabalho.

**Relatório salvo** em `pesquisa/<agente>-<AAAA-MM-DD>.md`, além de devolvido.

## As regras de julgamento que os quatro herdam

Vieram de um planejamento real e são o que separa uma pesquisa de uma recomendação:

- **Orçamento único do casal.** Só a hospedagem divide entre dois — passagem, comida e
  passeios dobram. Por isso o custo por pessoa quase não cai ao viajar em dupla. O que
  divide de verdade: táxi, remis contratado e aluguel de carro.
- **A passagem decide se a viagem cabe.** É 20 a 35% do total e a despesa mais volátil.
  Resolva-a primeiro.
- **Nunca entregue um número que cabe raspando.** Folga abaixo de R$ 300 num teto de
  R$ 15.000 não sobrevive ao primeiro imprevisto. Se sua recomendação só cabe assim, diga
  e ofereça o corte que devolve margem.
- **Diga o que não cabe, com o número.** "Areco custa R$ 900 e não cabe junto com 12 dias"
  é mais útil que silêncio ou que uma recomendação impossível.
- **Separe o que é pago em reais do que é gasto em destino.** O primeiro está protegido do
  câmbio; o segundo não. Isso muda a leitura de risco de qualquer orçamento.
- **Faixas, não pontos.** Preço sem data de consulta é ficção. Preço sem faixa é falsa
  precisão.
