# Debug Monitor

O Debug Monitor e um node de diagnostico ao vivo.

## Abrir

Use o botao `Debug` ou o atalho:

```text
Ctrl+Shift+D
```

Se ja existir um Debug Monitor no canvas, o TermiCanvas foca o node existente.

## Abas

- Overview: RAM, CPU, nodes, terminais, timers, fila do bus e render times.
- Per-Terminal: metricas por terminal.
- Errors: ultimos erros capturados.
- Threads: stacks das threads atuais.

## Exportar

O header do Debug Monitor permite:

- Copiar snapshot JSON para o clipboard.
- Salvar JSON em disco.

## Uso pratico

Use o monitor para investigar travamentos, crescimento de memoria, terminais com output excessivo e filas do bus que nao esvaziam.
