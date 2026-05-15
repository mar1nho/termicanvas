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
