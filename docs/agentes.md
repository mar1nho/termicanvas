# Agentes

Agentes sao CLIs hospedadas dentro de terminais. O TermiCanvas suporta Claude, Codex e Gemini.

## Criar agente

Use os botoes `Claude`, `Codex` ou `Gemini` na Tool Island.

- Duplo clique cria com defaults.
- Shift-clique abre o dialogo completo.

No dialogo voce pode escolher:

- Nome do node.
- Icone curto.
- Shell base: PowerShell ou CMD.
- Diretorio de trabalho.
- Role gerenciado, quando nao existir manifesto no diretorio.
- Promocao a orquestrador.

## Manifestos

Cada agente usa o manifesto esperado pela CLI:

- Claude: `CLAUDE.md`
- Codex: `AGENTS.md`
- Gemini: `GEMINI.md`

Quando o modo gerenciado e usado, o TermiCanvas escreve um manifesto inicial com a role escolhida.

## Shell

Agentes podem iniciar em PowerShell ou CMD. O comando inicial e adaptado:

- PowerShell: `cls; <cli>`
- CMD: `cls && <cli>`

## Editor de role

O botao de edicao no header do agente abre o manifesto do diretorio atual em um editor inline.
