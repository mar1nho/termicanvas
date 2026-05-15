# TermiCanvas

TermiCanvas e um canvas visual para organizar multiplos terminais e agentes CLI lado a lado. Ele transforma PowerShell, CMD, Claude, Codex e Gemini em nodes moveis, redimensionaveis e conectaveis, com foco em orquestracao de trabalho local.

## O que oferece

- Canvas infinito com pan, zoom, drag-to-create e snap-to-grid.
- Terminais PowerShell/CMD com PTY real, scrollback e resize responsivo.
- Agentes Claude, Codex e Gemini rodando dentro de terminais.
- Bus local para agentes trocarem mensagens por CLI.
- Orquestracao com spawn de agentes filhos e chains visuais.
- Notas, Prompt Card, Agent one-shot e Debug Monitor.
- Preview de arquivos Markdown/HTML como nodes do canvas.
- Expurgo de workspaces gerenciados criados por agentes via spawn.
- Snapshots nomeados e persistencia automatica em `session.json`.

## Rodar

```powershell
pip install -r requirements.txt
python main.py
```

## Documentacao

O manual foi separado por feature em `docs/`:

- [Canvas](docs/canvas.md)
- [Terminais](docs/terminais.md)
- [Agentes](docs/agentes.md)
- [Bus e CLI](docs/bus-e-cli.md)
- [Orquestracao](docs/orquestracao.md)
- [Widgets](docs/widgets.md)
- [Snapshots](docs/snapshots.md)
- [Debug Monitor](docs/debug-monitor.md)

Versao HTML offline: [docs/manual.html](docs/manual.html)
