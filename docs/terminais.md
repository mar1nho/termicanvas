# Terminais

Terminais sao nodes que hospedam PowerShell ou CMD usando PTY real no Windows.

## Criar terminal

Use os botoes `PowerShell` ou `CMD` na Tool Island.

- Duplo clique cria com os defaults.
- Shift-clique abre o dialogo para escolher nome, icone e diretorio de trabalho.

## Interacao

- Digite diretamente dentro do terminal.
- `Ctrl+C` com selecao copia texto.
- `Ctrl+C` sem selecao envia interrupcao para o shell.
- `Ctrl+V` cola o conteudo do clipboard.
- Roda do mouse rola somente o terminal sob o cursor.
- `Shift` + roda navega pelo scrollback do terminal.

## Resize

Ao redimensionar o node, o TermiCanvas recalcula linhas/colunas e ajusta o PTY.

## Pasta padrao

A pasta padrao e salva em `session.json` como `canvas.default_cwd`. Na primeira execucao, ela parte do diretorio atual do processo.
