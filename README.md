# Powershell Maestro — Python Prototype

Versao em Python do Powershell Maestro. Canvas com janelas arrastaveis contendo terminais PowerShell/CMD, agente de chat e notas.

## Stack

- **PyQt6** — GUI nativa (mesmo toolkit do Qt Creator, KDE, etc.)
- **pywinpty** — wrapper do ConPTY, a API oficial de pseudo-console do Windows
- **QMdiArea** — janelas internas arrastaveis/redimensionaveis ja com barra de titulo

## Instalar

### 1. Python 3.10+
Se nao tiver, baixar em https://www.python.org/downloads/ e marcar **"Add Python to PATH"** na instalacao.

Verificar:
```powershell
python --version
```

### 2. Dependencias
```powershell
cd C:\Users\usuario\Documents\Vault\Powershell-Maestro\powershell-master-python
pip install -r requirements.txt
```

Isso instala PyQt6 (~60 MB) e pywinpty. Total ~80 MB.

### 3. Rodar
```powershell
python main.py
```

## Uso

- **Painel lateral esquerdo (Maestro):**
  - Adicionar PowerShell 5, PowerShell 7 (pwsh), CMD, Agente ou Nota
  - Digitar comando no campo grande e clicar "Executar" — envia para o terminal ativo
  - Botoes "Grade" / "Cascata" organizam os nodes
- **Cada janela:** arrastar pela barra de titulo, redimensionar pelas bordas, fechar no X
- **Terminal:** digitar no campo de input embaixo + Enter
- **Agente:** prefixar com `SEND: comando` para enviar ao terminal ativo

## Limitacoes do prototipo

- **Sem cores ANSI** — regex remove codigos de escape. Para cores, adicionar `pyte` (emulador VT100).
- **Sem zoom/pan infinito** — diferente da versao Rust. `QMdiArea` e mais simples mas nao tem canvas infinito. Se quiser, migrar para `QGraphicsView`.
- **Sem persistencia** — fechar o app perde o layout.
- **Agente e placeholder** — falta plugar CLI real (Claude/Gemini/etc.).

## Empacotar como .exe

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name "PowershellMaestro" main.py
```

Resultado em `dist\PowershellMaestro.exe` (~50 MB). Distribuir esse arquivo — o usuario final nao precisa de Python instalado.

## Proximos passos possiveis

1. Adicionar cores ANSI via `pyte`
2. Migrar canvas para `QGraphicsView` com zoom/pan
3. Persistir layout em JSON (QSettings)
4. Plugar CLI real no AgentWidget (subprocess + streaming de stdout)
5. Hotkeys globais (Ctrl+T = novo terminal, etc.)
