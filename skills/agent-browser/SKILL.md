---
name: agent-browser
description: "Browser automation CLI for AI agents. Use for website interaction, form automation, screenshots, scraping, and web app verification. Prefer snapshot refs (@e1, @e2) for deterministic actions."
allowed-tools: Read Write Bash Grep Glob
metadata:
  tags: browser-automation, headless-browser, ai-agent, web-testing, web-scraping, verification
  platforms: Claude, Gemini, Codex, ChatGPT
  version: 1.1.0
  source: vercel-labs/agent-browser
  license: MIT (ver ATTRIBUTION.md)
---


# agent-browser - Browser Automation for AI Agents

## Quando usar esta skill

- Abrir sites e automatizar ações de UI
- Preencher formulários, clicar em controles e verificar resultados
- Capturar screenshots/PDFs ou extrair conteúdo
- Rodar checagens web determinísticas usando refs de acessibilidade
- Executar tarefas de browser em paralelo com sessões isoladas

No **Video AI Toolkit** ela entra quando o print/captura exige **interação antes**
(fechar banner de cookies, logar, clicar numa aba, rolar até um gráfico, aguardar
conteúdo dinâmico) — casos que o `web-shot.js` de uma tacada não cobre. Para print
simples de uma URL, continue usando o `web-shot`.

## Instalação

O CLI `agent-browser` é um binário à parte, instalado via npm (não vem vendorizado):

```bash
npm install -g agent-browser
```

O npm 10+ pode bloquear o *postinstall* por segurança. Se `agent-browser --version`
falhar depois do install, rode o postinstall à mão (ele baixa o binário nativo do
release oficial e usa o Chrome/Edge já instalado — não baixa Chromium):

```bash
# a partir da pasta global do pacote
node scripts/postinstall.js
```

O `install.ps1`/`install.sh` do toolkit já fazem isso automaticamente.

## Fluxo principal

Sempre use o loop determinístico de refs:

1. `agent-browser open <url>`
2. `agent-browser snapshot -i`
3. interaja com refs (`@e1`, `@e2`, ...)
4. `agent-browser snapshot -i` de novo depois de mudanças de página/DOM

```bash
agent-browser open https://example.com/form
agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser fill @e1 "user@example.com"
agent-browser click @e2
agent-browser snapshot -i
```

## Padrões de comando

Use encadeamento `&&` quando a saída intermediária não é necessária.

```bash
# Bom encadeamento: open -> wait -> snapshot
agent-browser open https://example.com && agent-browser wait --load networkidle && agent-browser snapshot -i

# Chamadas separadas quando a saída é necessária antes
agent-browser snapshot -i
# parse dos refs
agent-browser click @e2
```

Comandos de alto valor:
- Navegação: `open`, `close`
- Snapshot: `snapshot -i`, `snapshot -i -C`, `snapshot -s "#selector"`
- Interação: `click`, `fill`, `type`, `select`, `check`, `press`
- Verificação: `diff snapshot`, `diff screenshot --baseline <file>`
- Captura: `screenshot`, `screenshot --annotate`, `pdf`
- Espera: `wait --load networkidle`, `wait <selector|@ref|ms>`

## Verificação

Use evidência explícita depois de cada ação.

```bash
# Baseline -> ação -> verifica estrutura
agent-browser snapshot -i
agent-browser click @e3
agent-browser diff snapshot

# Regressão visual
agent-browser screenshot baseline.png
agent-browser click @e5
agent-browser diff screenshot --baseline baseline.png
```

## Segurança e confiabilidade

- Refs ficam inválidos após navegação ou mudança grande de DOM; re-snapshot antes da próxima ação.
- Prefira `wait --load networkidle` ou espera por selector/ref a `sleep` fixo.
- Para JS multi-passo, use `eval --stdin` (ou base64) para evitar quebra de escape no shell.
- Para tarefas concorrentes, isole com `--session <name>`.
- Use os controles de saída em páginas longas para não inflar o contexto.
- Endurecimento opcional em fluxos sensíveis: allowlist de domínio e políticas de ação.

Exemplos de endurecimento:

```bash
# Envolve o conteúdo da página em fronteiras (reduz risco de prompt-injection)
export AGENT_BROWSER_CONTENT_BOUNDARIES=1

# Limita o volume de saída em páginas longas
export AGENT_BROWSER_MAX_OUTPUT=50000

# Restringe navegação e rede a domínios confiáveis
export AGENT_BROWSER_ALLOWED_DOMAINS="example.com,*.example.com"

# Restringe os tipos de ação permitidos
export AGENT_BROWSER_ACTION_POLICY=./policy.json
```

`policy.json` de exemplo:

```json
{"default":"deny","allow":["navigate","snapshot","click","fill","scroll","wait","get"],"deny":["eval","download","upload","network","state"]}
```

Equivalente por flag de CLI:

```bash
agent-browser --content-boundaries --max-output 50000 --allowed-domains "example.com,*.example.com" --action-policy ./policy.json open https://example.com
```

## Notas de plataforma (Windows / antivírus)

Duas pegadinhas conhecidas ao rodar num terminal automatizado no Windows:

- **`open` é um daemon.** `agent-browser open <url>` sobe o browser e **fica vivo de
  propósito** para os comandos seguintes reusarem a sessão — ele não "retorna". Num
  terminal automatizado (não-interativo), chamar `open` de forma síncrona parece
  travar, mas não travou: dispare o `open` destacado (em background), espere o
  processo do browser subir e rode `snapshot`/`click`/`close` como chamadas separadas
  curtas. Num terminal humano normal isso não é problema.
- **`read` x antivírus que intercepta HTTPS.** O comando `agent-browser read <url>`
  faz uma requisição HTTP **nativa** (fora do browser). Se um antivírus estiver
  interceptando HTTPS (Avast, Kaspersky etc.), ela falha com
  `invalid peer certificate: UnknownIssuer`. O modo browser (`open` + `snapshot`) usa
  o Chrome do sistema, que confia no certificado do antivírus, e **não** sofre disso —
  prefira esse caminho quando o `read` falhar.

## Troubleshooting

- `command not found`: instale com `npm install -g agent-browser` e rode o postinstall.
- Elemento errado clicado: rode `snapshot -i` de novo e use refs frescos.
- Conteúdo de SPA dinâmico faltando: espere com `--load networkidle` ou `wait` por selector.
- Colisão de sessão: use nomes `--session` únicos e feche cada sessão.
- Pressão de saída grande: estreite snapshots (`-i`, `-c`, `-d`, `-s`) e extraia só o necessário.

## Referências

Docs aprofundados nesta skill:
- [commands](./references/commands.md)
- [snapshot-refs](./references/snapshot-refs.md)
- [session-management](./references/session-management.md)
- [authentication](./references/authentication.md)

Recursos relacionados:
- https://github.com/vercel-labs/agent-browser
- https://agent-browser.dev

Templates prontos:
- `./templates/form-automation.sh`
- `./templates/capture-workflow.sh`

## Metadata

- Version: 1.1.0
- Scope: automação de browser determinística para fluxos de agente
- Origem: `vercel-labs/agent-browser` (MIT) — ver `ATTRIBUTION.md`
