# Atribuição — skill agent-browser

Esta skill acompanha e documenta o CLI **agent-browser**, um projeto de terceiros.

- **Projeto:** agent-browser
- **Autor/origem:** Vercel Labs — https://github.com/vercel-labs/agent-browser
- **Site:** https://agent-browser.dev
- **Licença:** MIT

## Como o CLI é obtido

O binário **não é redistribuído** neste repositório. Ele é instalado pelo gerenciador
de pacotes na máquina do usuário:

```bash
npm install -g agent-browser
```

O *postinstall* do próprio pacote baixa o binário nativo direto do release oficial do
projeto no GitHub e reaproveita o Chrome/Edge já instalado (não baixa Chromium).

## Sobre os arquivos desta pasta

Os arquivos `SKILL.md`, `references/` e `templates/` são material de instrução para
orientar um agente a usar o CLI. Eles derivam da skill oficial distribuída junto ao
projeto agent-browser (mesma licença MIT), com adaptações em português e notas de
plataforma (Windows/antivírus) específicas deste toolkit. O texto da licença MIT do
projeto original permanece com seus detentores de direitos; consulte o repositório
oficial para o `LICENSE` completo.
