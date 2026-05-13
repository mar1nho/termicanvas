# TermiCanvas

![TermiCanvas](img1.png)

Canvas infinito para orquestrar múltiplos terminais PowerShell/CMD em paralelo, no estilo Figma/n8n. Pensado para rodar várias CLIs (incluindo agentes de IA) lado a lado, com pan, zoom e nodes arrastáveis com snap-to-grid.

---

## O que é

Um workspace visual em que cada terminal vira um node independente no canvas. Você cria, posiciona, redimensiona e organiza terminais como se fossem caixas em um quadro infinito — útil para acompanhar várias execuções, builds, agentes de IA ou sessões SSH sem precisar de múltiplas janelas.

Originalmente era o `Powershell-Maestro` (versão Rust, Linux-only). Foi reescrito em Python para rodar nativamente no Windows com setup mais leve.

---

## Features

### Canvas

- Canvas infinito via `QGraphicsView` + `QGraphicsScene` (50 000 × 50 000)
- **Pan:** botão do meio do mouse, ou `Espaço` + clique esquerdo (funciona mesmo por cima de terminais)
- **Zoom:** `Ctrl` + roda do mouse (0.15× até 4×)
- **Snap-to-grid de 40 px** no movimento e redimensionamento dos nodes — alinhamento automático estilo n8n
  - Segure `Alt` durante drag/resize para movimento livre (sub-grid)
- Grid quadriculado com linhas reforçadas a cada 5 quadrados
- Visual minimalista: fundo preto puro, paleta de cinzas progressivos, accent color global ajustável

### Nodes

- Cantos retos (radius 0)
- Arrastáveis pelo header — drag continua mesmo se o cursor sair do widget
- Redimensionáveis pelo grip do canto inferior direito
- Fechar pelo X no header (com cleanup completo de timers, threads PTY e refs do bus — sem leaks)
- Borda colorida quando o usuário escolhe cor custom — persiste mesmo desfocado
- **Rename inline:** duplo-clique no título abre input para renomear
- **Ícone editável:** duplo-clique no slot de ícone, aceita emoji ou texto curto
- **Cor da borda:** botão swatch no header abre `QColorDialog` (cor persiste no `session.json`)

### Terminais

- Digitação direta no widget (sem input box separado)
- Emulação VT100 completa com cores ANSI via `pyte`
- **Scrollback:** 3 000 linhas via `pyte.HistoryScreen`
  - Roda do mouse → rola scrollbar local
  - `Shift` + roda → navega páginas do histórico
- **Wheel isolado:** rola apenas o terminal sob o cursor, sem interferir no canvas
- **Copy/paste inteligente:**
  - `Ctrl+C` com seleção → copia para o clipboard
  - `Ctrl+C` sem seleção → envia SIGINT (0x03) para o shell
  - `Ctrl+V` → cola normalizando `\r\n`
- Suporte a setas, Home/End, PageUp/PageDown, Tab, `Ctrl+letra`
- Detecta prompt no fim do buffer e marca o terminal como "idle"
- Resize do widget reconfigura ConPTY + recria `pyte.Screen` automaticamente
- Fonte ajustável por terminal (`A−` / `A+` no header)

### Diálogo de novo terminal

Disparado por **shift-clique** (ou clique-direito) em um botão da Tool Island. Abre um modal com:

- **Nome do terminal** (opcional, default: `<Tipo> N`)
- **Diretório de trabalho** (default: `Vault/dattos-ia`) com botões "Pasta padrão" e "Escolher outra…"
- **Para agentes:**
  - Seleção de Responsibility (role)
  - Opção de "criar manifesto gerenciado" se o cwd ainda não tem `CLAUDE.md`/`GEMINI.md`
  - Checkbox **"Promover a orquestrador"** — apende o system prompt de orquestração no manifesto (idempotente: substitui in-place se já existe entre os markers `<!-- TermiCanvas orchestrator -->`)

### Topbar

- **Toggle do bus** — bolinha verde no canto esquerdo. Clique pra desligar o servidor de mensagens entre agentes; isso fecha todos os terminais e widgets do canvas e bota o app em modo enxuto. A bolinha fica vermelha pulsante quando desligado. Estado persiste entre sessões; o primeiro toggle pede confirmação com checkbox "não perguntar de novo"
- Brand `TERMICANVAS`
- Toggle da sidebar
- Toggle de tema (dark/light)
- Botão `Debug` (abre/foca o Debug Monitor)
- Swatch global de accent color (afeta todos os nodes que ainda não têm cor custom)

### Tool Island

Toolbar **flutuante e arrastável** com os botões de criação de nodes. Vive sobre o canvas com fundo translúcido em gradiente, divisor entre os grupos (terminais vs. widgets) e adapta paleta ao tema (dark/light).

Botões: `PowerShell`, `CMD`, `Claude`, `Gemini` · `Nota`, `Prompt`, `Agent`, `Debug Monitor`.

Modos de criação:

- **Clique simples** → arma o modo de inserção: o próximo drag no canvas desenha o retângulo onde o node vai nascer (drag-to-create). Clique sem drag cria no tamanho default.
- **Shift+clique** ou **clique-direito** → arma o modo *com dialog* (abre o `TerminalLaunchDialog` antes da criação).
- **Duplo-clique** → cria imediatamente no centro da viewport com defaults.

A máquina de estados fica em `InsertController` (`IDLE → ARMED → DRAGGING → commit`); o `NodeFactory` centraliza o dispatch `kind → widget` e o singleton handling do Debug Monitor.

### Sidebar (terminais abertos)

- Lista vertical com cada terminal aberto
- Nome + dot colorido (verde `idle` / accent `executando`)
- Linha de atividade (comando atual ou `idle`)
- Clique → canvas centraliza e foca o terminal
- Botão `«` recolhe; `»` flutuante reabre

### Widgets auxiliares

- **Notas** — `QTextEdit` livre com fundo claro
- **Prompt Card** — input multilinha que envia o conteúdo via `Ctrl+Enter` para outro node conectado por uma edge
- **Agente (chat one-shot)** — chat lateral que dispara `claude -p` por mensagem; mantido para perguntas rápidas

### Agentes interativos (CLI hospedada em terminal)

Cada terminal pode hospedar uma **CLI de agente** rodando interativamente — diferente do widget de chat one-shot. Suportados:

- **Claude Code** (`claude`) — usa manifesto `CLAUDE.md` + skills em `.claude/skills/`
- **Gemini CLI** (`gemini`) — usa manifesto `AGENTS.md` (ou `GEMINI.md`) + extensão em `.gemini/extensions/`

Ao criar um terminal-agente, o app:

1. Sobe o shell no diretório escolhido com `TERMICANVAS_BUS_URL` e `TERMICANVAS_NODE_ID` injetados no env
2. Em modo gerenciado, escreve a Responsibility selecionada como manifesto + instalação da skill `termicanvas-send`
3. Se a opção "Promover a orquestrador" foi marcada, apende o system prompt de orquestração no manifesto antes de subir a CLI
4. Envia `cls` + comando da CLI (`claude` ou `gemini`) ao prompt assim que detecta silêncio (~900 ms)

Botão 📝 no header do agente abre o `CLAUDE.md`/`GEMINI.md` do `cwd` em editor inline (disponível para qualquer agente com `cwd` configurado).

A skill `termicanvas-send` é distribuída em duas formas:

- `skills/claude-code-skill.md` — formato Claude Code (`.claude/skills/termicanvas-send/SKILL.md`)
- `skills/gemini-extension.md` — formato Gemini CLI (`.gemini/extensions/termicanvas-send/`)

No modo gerenciado a skill é instalada automaticamente; em projetos com manifesto próprio (modo `existing`), copiar manualmente.

### Responsibilities (roles)

Roles de fábrica em `~/.termicanvas/roles/`:

- **Líder** — coordena, divide trabalho, valida resultados
- **Desenvolvedor** — foca em implementação, escreve código pronto pra rodar
- **Revisor** — crítica de código, aponta riscos
- **Testador** — escreve e roda testes

Roles novos podem ser adicionados como markdown na mesma pasta. O nome do arquivo (sem extensão) vira o nome do role.

### Bus local (agente↔agente)

Servidor HTTP em `127.0.0.1:<porta-livre>` exposto via env var `TERMICANVAS_BUS_URL` para os agentes. Cada terminal recebe um `TERMICANVAS_NODE_ID` único.

Endpoints:

| Método | Rota | Payload / Query | Função |
|---|---|---|---|
| POST | `/send` | `{from, to, message}` | enfileira mensagem direta |
| POST | `/broadcast` | `{from, message, exclude?}` | manda pra todos os agentes (exceto remetente + opcionais) |
| POST | `/spawn` | `{kind, name, role_md, parent_cwd?}` | cria um novo node-agente no canvas |
| GET | `/list` | — | lista terminais (id, nome, agent_kind) |
| GET | `/inbox` | `?node_id=X` | mensagens pendentes pra X |
| GET | `/status` | `?msg_id=X` | `pending` \| `delivered` \| `expired` |
| GET | `/health` | — | ping |

Regra de entrega (estilo Maestri): a mensagem só é injetada no PTY do destinatário quando ele está **idle** **e desselecionado**. Se estiver focado, fica na fila até perder o foco. Isso evita pisar em digitação manual. TTL de 5 min — mensagens não entregues nesse período viram `expired`.

### CLI `termicanvas` (agente↔agente)

Cada agente recebe automaticamente acesso à CLI Python expondo o bus. Comandos:

```
python -m termicanvas.cli list                       # lista todos os agentes ativos
python -m termicanvas.cli whoami                     # seu próprio node_id
python -m termicanvas.cli send <node_id> "mensagem"  # mensagem direta
python -m termicanvas.cli broadcast "mensagem"       # mensagem pra todos os agentes
python -m termicanvas.cli inbox                      # mensagens pendentes pra você
python -m termicanvas.cli status <msg_id>            # checa se mensagem foi entregue
python -m termicanvas.cli spawn <kind> "<nome>"      # cria um novo agente no canvas
```

`spawn` aceita `--role-file role.md` (recomendado, evita o limite de ~965 B do parser de comandos do Claude Code) ou role via **stdin** pra payloads curtos. Kinds suportados: `claude`, `gemini`, `powershell`, `cmd` (apenas claude/gemini consomem `role_md`).

### Orquestração

Qualquer agente pode ser **promovido a orquestrador** na criação (checkbox no dialog) ou via `promote_to_orchestrator(cwd, agent_kind)` no código. A promoção é idempotente: apende um bloco demarcado pelos markers `<!-- TermiCanvas orchestrator -->` / `<!-- /TermiCanvas orchestrator -->` no `CLAUDE.md`/`GEMINI.md`, ou substitui in-place se já existir. Funciona tanto em manifestos gerenciados quanto em manifestos pré-existentes do projeto.

O system prompt injetado ensina o agente a:

1. Listar agentes ativos via `list`
2. Dividir trabalho em sub-tarefas atômicas
3. Delegar via `send <node_id> "..."` com critério de sucesso explícito
4. Monitorar respostas via `inbox` (entrega assíncrona, idle-aware)
5. Agregar retornos e responder ao humano

Quando o orquestrador chama `spawn`, o TermiCanvas:

1. Cria uma pasta isolada em `<parent_cwd>/.termicanvas/<slug>/`
2. Escreve o manifesto com o `role_md` fornecido + **bloco automático "Como responder mensagens"** (instruindo o agente a responder via `cli send` em vez de escrever no PTY — comunicação máquina-a-máquina)
3. Spawna o terminal correspondente posicionado abaixo do orquestrador
4. Desenha uma **chain visual** (catenária) ligando os dois no canvas

Permissões pré-aprovadas: agentes promovidos a orquestrador (e seus spawnados) recebem `.claude/settings.local.json` autorizando qualquer comando `python -m termicanvas.cli ...` sem prompts.

### Auto-responder

Toggle no header de cada terminal-agente. Quando ativo, ao receber uma mensagem do bus o agente captura a resposta gerada e a devolve automaticamente ao emissor após o próximo silêncio do prompt. **Agentes nascem com auto-reply ON por default** — pra que o fluxo orquestrador→spawn funcione sem o user precisar clicar em cada cabeçalho.

### Chain visual

Quando um orquestrador spawna um agente filho, o canvas desenha uma corrente (catenária) ligando o header do pai ao do filho. A linha é fina, tracejada e adapta a cor ao tema. Também é possível criar chains manuais entre agentes pelo botão dedicado no header.

### Debug Monitor

Node especial para diagnóstico ao vivo, abrível pelo botão `Debug` da topbar ou pelo atalho `Ctrl+Shift+D` (foca o existente em vez de criar duplicata).

Quatro abas:

- **Overview** — RAM, CPU, n° de nodes, terminais, timers, fila do bus, p50/p95/p99 dos tempos de render. Cada métrica acompanha sparkline de 5 min e há um histograma dos render times.
- **Per-Terminal** — tabela com `name / raw_buf (KB) / chars/s / activity / alive`. Linhas com `chars/s > 5000` por 3 ticks consecutivos são marcadas como sustained-alert.
- **Errors** — buffer dos últimos 200 erros (timestamp, source, exc_type, message, stack completo). Captura `sys.excepthook`, `threading.excepthook` e 8 blocos `except: pass` antes silenciados em `terminal.py`/`bus.py`.
- **Threads** — `sys._current_frames()` sob demanda (botão `Atualizar agora`); útil para diagnosticar travamentos.

Ações no header do node:

- 📋 **Copy snapshot** — copia o estado atual como JSON para o clipboard
- 💾 **Save JSON** — salva snapshot + 5 min de history + erros como `debug-snapshot-YYYYMMDD-HHMMSS.json`

Requisitos:

- `psutil>=5.9` (já no `requirements.txt`)
- O monitor usa `weakref.WeakSet` para observar terminais — fechar o monitor libera todas as refs e timers (validado por unit tests + gate manual de não-leak).

### Persistência (`session.json`)

Tudo que está no canvas é salvo no `session.json` ao fechar:

- Posição, tamanho, ícone, cor (custom ou herdada do accent global)
- Por tipo: `terminal` (shell, cwd, agent_kind, role_name, manifest_mode, font_size, auto_reply), `note` (conteúdo), `prompt` (conteúdo), `agent`, `debug_monitor` (apenas geometria — history sempre começa vazia)
- Estado do canvas (zoom, scroll, accent color)
- Conexões entre nodes (Prompt → Agent/Terminal, Agent → Agent/Terminal)

---

## Stack

| Camada | Lib | Função |
|---|---|---|
| GUI | PyQt6 | toolkit nativo, canvas via `QGraphicsView` |
| PTY | pywinpty | wrapper do ConPTY (API oficial do Windows 10 1903+) |
| Emulador | pyte | VT100 + `HistoryScreen` para scrollback |
| Métricas | psutil | RSS / CPU para o Debug Monitor |
| Testes | pytest | regression tests (`tests/`) |

---

## Instalação

### 1. Python 3.10+

Baixar em <https://www.python.org/downloads/> e marcar **"Add Python to PATH"** durante a instalação.

```powershell
python --version
```

### 2. Dependências

```powershell
git clone https://github.com/mar1nho/termicanvas.git
cd termicanvas
pip install -r requirements.txt
```

Instala PyQt6, pywinpty, pyte, psutil e pytest (~120 MB no total).

### 3. Rodar

```powershell
python main.py
```

### 4. (Opcional) Rodar os testes

```powershell
python -m pytest tests/ -v
```

---

## Atalhos

| Atalho | Ação |
|---|---|
| Botão do meio (drag) | Pan no canvas |
| Espaço + clique esquerdo | Pan no canvas (mesmo sobre terminais) |
| Ctrl + roda | Zoom in/out |
| Roda sobre terminal | Scroll local do terminal |
| Shift + roda sobre terminal | Navega páginas do scrollback |
| Drag de node | Move com snap-to-grid (40 px) |
| Drag de node + Alt | Move sem snap (movimento livre) |
| Resize de node | Mesmo comportamento (snap, com Alt para livre) |
| Duplo-clique no header | Renomear node |
| Ctrl+C com seleção | Copiar |
| Ctrl+C sem seleção | Enviar SIGINT |
| Ctrl+V | Colar |
| Ctrl+T | Novo terminal |
| Ctrl+W | Fecha terminal focado |
| Ctrl+Tab | Próximo terminal |
| Ctrl+Shift+D | Abre / foca o Debug Monitor |
| Alt + 1..9 | Foca o N-ésimo terminal aberto |

---

## Empacotar como .exe

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name "TermiCanvas" main.py
```

Resultado em `dist\TermiCanvas.exe` (~50 MB). O usuário final não precisa de Python instalado.

---

## Changelog técnico recente

### Orquestração de agentes (2026-05)

- **Promoção a orquestrador** (`termicanvas/agents.py`): novo `promote_to_orchestrator(cwd, agent_kind)` apende um system prompt completo de orquestração no `CLAUDE.md`/`GEMINI.md`, demarcado por markers idempotentes. Disponível como checkbox no `TerminalLaunchDialog` e aplicado *antes* de spawnar o terminal — funciona mesmo em manifestos do projeto não-gerenciados.
- **Spawn dinâmico** (`/spawn` no bus + `cli.py spawn`): orquestradores criam novos agentes em pastas isoladas (`<cwd>/.termicanvas/<slug>/`). Manifesto é montado por `build_spawned_manifest()` → marker + role customizado + bloco fixo "Como responder mensagens" (garante que o agente fale via `cli send`, não no PTY).
- **CLI completa**: `list`, `whoami`, `send`, `broadcast`, `inbox`, `status`, `spawn`. Endpoints REST espelhados em `bus.py` (`/send`, `/broadcast`, `/spawn`, `/list`, `/inbox`, `/status`, `/health`).
- **Auto-reply ON por default** em agentes-terminal — fluxo orquestrador→spawn funciona sem clicar em cada header.
- **Permissões pré-aprovadas**: agentes orquestradores e spawnados recebem `.claude/settings.local.json` autorizando `python -m termicanvas.cli ...` sem prompt.
- **Skill `termicanvas-send`** publicada em `skills/claude-code-skill.md` + `skills/gemini-extension.md` — instalável em qualquer agente fora do contexto gerenciado.

### Tool Island + drag-to-create (2026-05)

- **`termicanvas/island.py`** — toolbar flutuante (gradient translúcido, arrastável, adaptativa ao tema) substitui os botões de criação que viviam na Topbar. Dois grupos visuais: terminais (PS/CMD/Claude/Gemini) e widgets (Nota/Prompt/Agent/Debug).
- **`termicanvas/insert_controller.py`** — `QObject` state machine (`IDLE → ARMED → DRAGGING`). Sem GUI; `ToolIsland` arma, `CanvasView` dispara `start/update/finish_drag`, e o controller emite `commit_requested(kind, geometry, with_dialog)`.
- **`termicanvas/node_factory.py`** — centraliza criação de qualquer node a partir de um `kind` semântico. Substitui os 6 métodos `_add_*` antes espalhados em `main.py`. Cuida de: tamanhos default por kind, posição (se `geometry` veio do drag), dispatch `kind → widget class`, abertura opcional do `TerminalLaunchDialog`, singleton handling do Debug Monitor.
- UX: clique simples = drag-to-create, shift/right-click = drag-to-create *com dialog*, duplo-clique = cria no centro com defaults.
- Tests novos em `tests/test_insert_controller.py`, `tests/test_island.py`, `tests/test_node_factory.py`.

### Memory leak fix (2026-04-27)

- `Bus._RegisteredNode` retinha `TerminalWidget` + `NodeFrame` indefinidamente porque `canvas._close()` não chamava `bus.unregister(node_id)`. Cada terminal fechado deixava ~1-3 MB de heap (HistoryScreen + raw_buf + QTextDocument) e 3 QTimers a 12.5 Hz cada rodando como zumbis até o app fechar.
- Confirmação empírica via instrumentação: `nodes` crescia monotonicamente (1 → 11 sem nunca cair) durante uso normal.
- Fix em três frentes:
  - `TerminalWidget.shutdown` agora para `_render_timer`, `_idle_timer` e `_resize_timer` e chama `deleteLater()`
  - `CanvasView._close` chama `bus.unregister(node_id)` antes do `shutdown`
  - `Bus.stop` faz `_nodes.clear()` e remove o `bus.port` do disco
- Regression test em `tests/test_bus_lifecycle.py` valida o contrato `canvas._close → bus.unregister`.

### Debug Monitor (2026-04-27)

- Novo módulo `termicanvas/diagnostics.py` (always-on, passive): buffer circular de 200 erros, 600 amostras de render time, `install_excepthooks()` chamado no `main()` que captura `sys.excepthook` + `threading.excepthook` preservando hooks anteriores via chain.
- 8 blocos `except: pass` antes silenciados em `terminal.py`/`bus.py` agora chamam `record_error(source, exc)` (mantendo o `pass` para não mudar o fluxo).
- Novo módulo `termicanvas/monitor.py`: `MetricsCollector` (QObject, 1 Hz, weakref para canvas/bus), `Sparkline` e `Histogram` paint widgets, `DebugMonitorWidget` com 4 abas e export JSON.
- 11 unit tests em `tests/test_diagnostics.py` + `tests/test_metrics_collector.py` cobrem buffer maxlen, hook chaining, weakref drop, snapshot fields e percentil.

### UX/UI fixes (2026-04-27)

- **Snap-to-grid:** drag e resize alinham nos 40 px do grid visual, com `Alt` para movimento livre. Fix de stutter em deltas pequenos via virtual-position tracking (drag continuo no cursor, render snapado).
- **Cor da borda:** `_apply_style` agora honra `_custom_color=True` mesmo quando desfocado (antes voltava para cinza neutro).
- **Persistência de cor:** `set_node_color` aplicado em todos os tipos (note/agent/prompt/debug_monitor) durante restore — antes só terminais carregavam a cor escolhida.
- **`QColorDialog` sob proxy widget:** parent agora é `QApplication.activeWindow()` em vez de `self` (NodeHeader vive dentro de `QGraphicsProxyWidget` e Qt mis-posicionava o modal).
- **Botão de editar role:** disponível em qualquer terminal de agente com `cwd` (antes era restrito a `manifest_mode == "managed"`, o que escondia o botão em toda pasta com `CLAUDE.md` pré-existente).
- **Ícones:** emojis dos botões + labels do Debug Monitor substituídos por SVGs monocromáticos via `termicanvas/icons.py` (consistência visual com o resto do app).

---

## Limitações conhecidas

- **Bus síncrono** — entrega de mensagens entre agentes via polling Qt (250 ms); ok pra uso real, mas não é tempo real.
- **Detecção de idle por regex** — funciona pra PowerShell e prompts Bash; CLIs com prompt customizado (Oh My Posh, Starship muito custom) podem não disparar idle.
- **Múltiplos Debug Monitors** — proibido por design; a segunda tentativa foca o existente.

---

## Roadmap

- Workspaces nomeados (carregar/salvar múltiplos layouts)
- UI dedicada pra editar Responsibilities (hoje é só editar markdown em `~/.termicanvas/roles/`)
- Suporte a mais CLIs (Aider, OpenCode, Cursor CLI)
- Agente↔nota: agente lê/escreve numa nota conectada via skill própria
- Profiler embutido no Debug Monitor (cProfile/py-spy on-demand)

![TermiCanvas em uso](imagem2.png)

---

## Histórico de design

1. Primeira iteração usou `QMdiArea` (janelas MDI nativas) — descartado por não permitir canvas infinito real.
2. Tentado `QGraphicsDropShadowEffect` nos nodes — quebra o render do `QPlainTextEdit` dentro de proxy widget (bug conhecido do Qt). Removido.
3. Sistema de "wires/pipes" entre terminais (estilo n8n) chegou a ser implementado e foi removido para manter o foco nos terminais. Voltou em forma reduzida (Prompt → Agent/Terminal, Agent → Agent/Terminal) com `route_output` e canvas-level connections.
4. Pan via Espaço usa event filter global no `QApplication` — necessário porque o terminal sempre captura foco do teclado.
5. Wheel sobre terminal precisou despachar diretamente na scrollbar do `QPlainTextEdit` (não via dispatch normal), porque o `QGraphicsView` fazia fallback para scroll do viewport.
6. `_render` do terminal usa snapshot de `screen.history.top` + `screen.history.bottom` + `screen.buffer`, agrupando runs por cor antes de aplicar `QTextCharFormat` — evita rebuild colorido caro a cada cell em TUIs animados.
7. Snap-to-grid usa virtual-position cumulativa para evitar que o cursor "perca" o node em deltas menores que meia célula.
