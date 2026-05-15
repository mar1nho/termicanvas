# Widgets

TermiCanvas inclui widgets auxiliares para organizar contexto e rotear comandos.

## Nota

Um bloco de texto livre no canvas. Use para lembretes, plano de execucao ou contexto.

## Prompt Card

Campo multilinha que envia texto via `Ctrl+Enter` para um node conectado.

Fluxo comum:

1. Crie um Prompt Card.
2. Clique na porta de saida.
3. Clique em um terminal ou Agent Widget para conectar.
4. Escreva o prompt e envie com `Ctrl+Enter`.

## Agent Widget

Widget de chat one-shot que chama `claude -p`. Ele e util para perguntas rapidas, mas agentes interativos em terminal sao o fluxo principal.

## Preview

Node para visualizar arquivos Markdown ou HTML locais.

- Crie pela Tool Island em `Preview`.
- Shift-clique ou clique direito abre o dialogo para escolher arquivo e tipo.
- O tipo pode ser automatico, Markdown ou HTML.
- HTML usa QtWebEngine quando disponivel, entao CSS externo via paths relativos (`<link rel="stylesheet" href="style.css">`) renderiza como no navegador.
- O proprio node tambem tem botoes para trocar arquivo e recarregar.
- O botao de compactar no header reduz o preview para um card 2x2 do grid. Clique no card compacto para expandir de volta.
