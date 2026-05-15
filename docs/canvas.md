# Canvas

O canvas e a area principal do TermiCanvas. Ele usa uma cena ampla para organizar nodes como em um quadro visual.

## Como usar

- Arraste o fundo com o botao do meio do mouse para navegar.
- Segure `Espaco` e arraste com o botao esquerdo para pan alternativo.
- Use `Ctrl` + roda do mouse para zoom.
- Clique em um node para focar.
- Arraste o header de um node para mover.
- Arraste o canto inferior direito para redimensionar.

## Criacao de nodes

A Tool Island fica sobre o canvas.

- Clique simples em uma ferramenta: arma o modo de insercao.
- Depois clique ou arraste no canvas para criar o node.
- Duplo clique em uma ferramenta: cria o node no centro da tela.
- Shift-clique ou clique direito: abre o dialogo de criacao quando a ferramenta tiver opcoes.

O botao flutuante `+` fica separado da Tool Island. Ele abre o dialogo unificado para escolher PowerShell, CMD, Claude, Codex ou Gemini, configurar pasta, pasta padrao, shell do agente e orquestrador. Ao confirmar, o tipo escolhido fica armado para clicar ou arrastar no canvas.

## Snap

Movimento e resize usam grid de 40 px. Segure `Alt` durante drag ou resize para movimento livre.

## Atalhos

- `Ctrl+T`: novo terminal PowerShell.
- `Ctrl+W`: fecha o node focado.
- `Ctrl+Tab`: alterna foco entre nodes.
- `Ctrl+Shift+D`: abre ou foca o Debug Monitor.
