"""Specs de CLIs de agente (Claude Code, Gemini CLI) e helpers de roles.

Aplicacao de role
=================

Quando o user opta por "criar role gerenciado" no modal (so disponivel quando
o cwd NAO tem manifesto), o TermiCanvas escreve o role direto em
`<cwd>/CLAUDE.md` (ou `GEMINI.md`). O agente le esse arquivo no startup como
qualquer projeto normal — sem injecao de mensagem, sem poluir o terminal.

Pra distinguir um manifesto gerado pelo TermiCanvas de um do projeto, o
arquivo gerado tem o marker `TERMICANVAS_MARKER` na primeira linha. Spawns
subsequentes sobrescrevem se o marker estiver presente; preservam se nao.

O botao 📝 no header do agente abre `<cwd>/CLAUDE.md` no editor pra ajustar.
"""

import json
from pathlib import Path

from .roles import get_role


# Comandos do CLI do TermiCanvas que devem ser pre-aprovados em
# .claude/settings.local.json pra evitar prompt de permissao em cada chamada.
# O padrao "*" cobre qualquer subcomando + argumentos.
_CLI_PERMISSIONS = [
    "Bash(python -m termicanvas.cli:*)",
]


def install_termicanvas_permissions(cwd, agent_kind):
    """Pre-aprova comandos do termicanvas CLI no .claude/settings.local.json.

    Evita que o agente Claude pause em cada `python -m termicanvas.cli ...`
    pedindo permissao. Faz MERGE: se ja existir um settings.local.json no
    projeto, preserva tudo e so adiciona os entries que faltam em
    `permissions.allow`.

    Retorna o path do arquivo, ou None se nao aplicavel/falhou.
    """
    if agent_kind != "claude":
        # Gemini tem sistema de permissoes diferente — fora do escopo por ora.
        return None

    cwd_path = Path(cwd)
    if not cwd_path.is_dir():
        return None

    settings_dir  = cwd_path / ".claude"
    settings_path = settings_dir / "settings.local.json"

    try:
        settings_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return None

    current = {}
    if settings_path.exists():
        try:
            current = json.loads(settings_path.read_text(encoding="utf-8"))
            if not isinstance(current, dict):
                current = {}
        except Exception:
            current = {}

    perms = current.setdefault("permissions", {})
    allow = perms.setdefault("allow", [])
    if not isinstance(allow, list):
        allow = []
        perms["allow"] = allow

    changed = False
    for entry in _CLI_PERMISSIONS:
        if entry not in allow:
            allow.append(entry)
            changed = True

    if not changed and settings_path.exists():
        return settings_path

    try:
        settings_path.write_text(
            json.dumps(current, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return settings_path
    except Exception:
        return None


TERMICANVAS_MARKER = "<!-- TermiCanvas managed role -->"
ORCHESTRATOR_BEGIN = "<!-- TermiCanvas orchestrator -->"
ORCHESTRATOR_END   = "<!-- /TermiCanvas orchestrator -->"


# Specs das CLIs suportadas. Plugavel — adicionar nova CLI = nova entrada aqui.
AGENT_KINDS = {
    "claude": {
        "label":     "Claude Code",
        "command":   "claude",
        "manifest":  "CLAUDE.md",
        "skills_dir": ".claude/skills",
        "icon":      "C",
    },
    "gemini": {
        "label":     "Gemini CLI",
        "command":   "gemini",
        "manifest":  "GEMINI.md",
        "skills_dir": ".gemini/extensions",
        "icon":      "G",
    },
}


def managed_manifest_path(cwd, agent_kind):
    """Caminho do CLAUDE.md/GEMINI.md gerenciado pelo TermiCanvas no cwd."""
    if agent_kind not in AGENT_KINDS:
        return None
    return Path(cwd) / AGENT_KINDS[agent_kind]["manifest"]


def install_role(cwd, agent_kind, role_name, mode="managed", node_id=None):
    """Aplica role no projeto. Retorna o path do manifesto criado/atualizado.

    mode="existing": no-op. Agente usa o manifesto que ja existe (se existir).
    mode="managed":  escreve role + skill instructions em `<cwd>/CLAUDE.md`
                     (ou GEMINI.md). Sobrescreve apenas se o arquivo nao existir
                     OU se ja foi gerado pelo TermiCanvas (tem TERMICANVAS_MARKER
                     na primeira linha). Nunca pisa em manifesto do projeto.

    `node_id` e aceito por compat mas nao usado — agora ha 1 manifesto por cwd.
    """
    if agent_kind not in AGENT_KINDS or mode != "managed":
        return None

    cwd_path = Path(cwd)
    if not cwd_path.is_dir():
        return None

    role = get_role(role_name) if role_name else None
    role_body = role.content if role else "# Role livre\n\nResponda em portugues, de forma direta.\n"
    role_label = role_name or "Livre"

    full_content = (
        f"{TERMICANVAS_MARKER}\n\n"
        f"# Agente — role: {role_label}\n\n"
        + role_body
        + "\n\n---\n\n"
        + _send_skill_instructions()
    )

    target = managed_manifest_path(cwd_path, agent_kind)
    if target is None:
        return None

    # Preserva manifesto que NAO foi gerado pelo TermiCanvas
    if target.exists():
        try:
            head = target.read_text(encoding="utf-8").splitlines()[:1]
        except Exception:
            return target
        if not head or TERMICANVAS_MARKER not in head[0]:
            # arquivo do projeto — nao toca
            return target

    try:
        target.write_text(full_content, encoding="utf-8")
    except Exception:
        return None

    return target


def is_managed_manifest(cwd, agent_kind):
    """True se o manifesto no cwd foi gerado pelo TermiCanvas."""
    target = managed_manifest_path(cwd, agent_kind)
    if not target or not target.exists():
        return False
    try:
        head = target.read_text(encoding="utf-8").splitlines()[:1]
    except Exception:
        return False
    return bool(head and TERMICANVAS_MARKER in head[0])


def _send_skill_instructions():
    """Bloco de instrucao injetado no role explicando como usar termicanvas-send."""
    return (
        "## Skill: termicanvas-send\n\n"
        "Voce esta rodando dentro de um terminal do TermiCanvas. Outros agentes\n"
        "podem estar em outros terminais do mesmo canvas. Para conversar com\n"
        "eles, use o comando abaixo via Bash/PowerShell:\n\n"
        "```\n"
        "python -m termicanvas.cli send <node_id_destino> \"sua mensagem\"\n"
        "```\n\n"
        "Variaveis de ambiente disponiveis:\n"
        "- `TERMICANVAS_BUS_URL` — URL do bus local\n"
        "- `TERMICANVAS_NODE_ID` — seu proprio ID\n\n"
        "Para listar terminais ativos:\n\n"
        "```\n"
        "python -m termicanvas.cli list\n"
        "```\n\n"
        "Mensagens enviadas ficam no inbox do destinatario. O bus cutuca\n"
        "automaticamente o terminal alvo a rodar `inbox` quando ele estiver\n"
        "idle e sem foco. Resposta nao eh instantanea — depende do destinatario\n"
        "processar e responder via `send`.\n"
    )


def spawn_response_instructions():
    """Bloco apendido automaticamente em TODO manifesto de agente spawnado
    via /spawn. Garante que o agente responda via bus em vez de escrever
    no PTY como se houvesse humano lendo."""
    return """## Como receber e responder mensagens (TermiCanvas)

Voce esta rodando dentro do TermiCanvas. **Nao existe usuario humano lendo seu
terminal** — apenas o orquestrador (e outros agentes via bus) se comunicam com
voce. Tudo eh maquina-a-maquina.

### Como mensagens chegam

Mensagens NAO sao injetadas no seu chat. Elas ficam num **inbox** no bus, e voce
precisa rodar o comando abaixo pra consumir:

```
python -m termicanvas.cli inbox
```

O bus cutuca esse comando automaticamente no seu PTY quando voce esta idle e sem
foco — basta rodar ele quando aparecer. Voce tambem pode rodar manualmente a
qualquer momento. Cada GET consome (remove) as mensagens da fila.

Formato de saida do `inbox` quando ha mensagens:
```
[msg_id] de <node_id_emissor>: <texto da mensagem>
```

Se aparecer `(inbox vazia)`, nao tem nada pra processar.

### Como responder

```
python -m termicanvas.cli send <node_id_origem> "[<seu_papel>] resposta..."
```

- O `node_id` do emissor vem no prefixo `de <node_id>:` do `inbox`
- Se nao tiver certeza, rode `python -m termicanvas.cli list` pra ver quem
  enviou (procure pelo `name`)
- **Prefixe suas respostas** com `[<seu_papel>]` (ex: `[Jira Expert]`) pra
  o orquestrador identificar a origem
- **Apos enviar, fique idle silenciosamente** — nao escreva mensagem final
  resumindo o que fez. O orquestrador nao precisa de eco.
- Tarefas que falham: avise via send antes de ficar idle.

### Comandos auxiliares (todos pre-aprovados, sem prompt)

- `python -m termicanvas.cli whoami` — seu node_id
- `python -m termicanvas.cli list` — lista agentes ativos
- `python -m termicanvas.cli inbox` — consome mensagens pendentes pra voce
- `python -m termicanvas.cli status <msg_id>` — checa entrega
"""


def _default_role_for(agent_name):
    """Role padrao quando o orquestrador nao passou role_md customizado.
    Gera manifesto rico e legivel ao inves de um stub minimalista."""
    name = (agent_name or "Agente").strip() or "Agente"
    return (
        f"# {name}\n\n"
        f"Voce e o agente **{name}**, rodando no TermiCanvas como subordinado\n"
        f"de um orquestrador. Sua funcao especifica nao foi informada — execute\n"
        f"o que for pedido respeitando as regras gerais abaixo e pergunte ao\n"
        f"orquestrador quando o pedido for ambiguo.\n\n"
        f"## Identidade\n\n"
        f"- Nome: **{name}**\n"
        f"- Papel: agente generico (definir conforme tarefas)\n"
        f"- Orquestrado por outro agente Claude no mesmo canvas\n\n"
        f"## Idioma e tom\n\n"
        f"- Portugues (pt-BR), letras minusculas\n"
        f"- Respostas diretas, objetivas, sem floreios\n"
        f"- Codigo em portugues (variaveis, comentarios, UI)\n\n"
        f"## Regras inegociaveis\n\n"
        f"1. **Nunca criar/editar/deletar sem autorizacao explicita** —\n"
        f"   exigir palavras literais (\"pode\", \"ok\", \"sim\", \"vai\",\n"
        f"   \"aprovo\", \"manda ver\", \"executa\", \"confirmo\") antes de\n"
        f"   qualquer write em sistema externo.\n"
        f"2. **Nunca hardcodar tokens, credenciais ou dados reais** —\n"
        f"   usar placeholders.\n"
        f"3. **Ler codigo antes de sugerir mudancas** — nada de chutar.\n"
        f"4. **Apresentar plano antes** de qualquer mudanca nao-trivial.\n\n"
        f"## Quando responder ao orquestrador\n\n"
        f"- Prefixar resposta com `[{name}]` para o orquestrador identificar\n"
        f"  a origem da mensagem.\n"
        f"- Se a tarefa for ambigua, pedir esclarecimento antes de executar.\n"
        f"- Se travar em algo (permissao, dependencia, erro), reportar e\n"
        f"  aguardar nova instrucao em vez de tentar contornar.\n"
    )


def build_spawned_manifest(role_md, agent_name=""):
    """Monta o conteudo final do manifesto de um agente spawnado: marker +
    role (customizado pelo orquestrador ou default rico) + instrucoes padrao
    de resposta. Garante que o arquivo nunca seja vazio."""
    role_clean = (role_md or "").lstrip("﻿").strip()
    if not role_clean:
        role_clean = _default_role_for(agent_name)
    return (
        f"{TERMICANVAS_MARKER}\n\n"
        f"{role_clean}\n\n"
        f"---\n\n"
        f"{spawn_response_instructions()}\n"
    )


def _orchestrator_prompt():
    """System prompt completo de orquestracao. Apendido ao manifesto quando o
    user promove o agente. Bloco e demarcado pelos markers ORCHESTRATOR_BEGIN
    e ORCHESTRATOR_END pra permitir atualizacao idempotente."""
    return """## Voce e um Orquestrador

Voce esta rodando no TermiCanvas com a capacidade de **coordenar outros agentes**
em terminais paralelos no mesmo canvas. Sua funcao primaria e dividir trabalho,
delegar partes pra outros agentes, monitorar progresso e agregar respostas.

### Servidores e variaveis disponiveis

- **Bus local** (HTTP em 127.0.0.1) — orquestra mensagens entre agentes
- `TERMICANVAS_BUS_URL` — URL completa do bus (env var ja injetada)
- `TERMICANVAS_NODE_ID` — seu proprio ID neste canvas (env var ja injetada)

### Comandos da CLI termicanvas

```
python -m termicanvas.cli list                       # lista todos os agentes ativos
python -m termicanvas.cli whoami                     # seu node_id
python -m termicanvas.cli send <node_id> "mensagem"  # mensagem direta a 1 agente
python -m termicanvas.cli broadcast "mensagem"       # mensagem pra TODOS os agentes
python -m termicanvas.cli inbox                      # lista mensagens pendentes pra voce
python -m termicanvas.cli status <msg_id>            # checa se mensagem foi entregue
python -m termicanvas.cli spawn <kind> "<nome>"      # cria um novo agente no canvas
```

### Criando agentes dinamicamente

Voce pode invocar novos agentes durante a sessao. O TermiCanvas vai:
1. Criar uma pasta isolada em `<seu_cwd>/.termicanvas/<slug_do_nome>/`
2. Escrever um manifesto (CLAUDE.md/GEMINI.md) com o role_md que voce passar
3. Spawnar o terminal correspondente no canvas, posicionado abaixo do seu

**Recomendado — use `--role-file`** (evita o limite de 965 bytes do parser
de comandos do Claude Code). Salve o role num arquivo temporario primeiro:

PowerShell:
```powershell
@'
# Dev Agent
Voce e um desenvolvedor full-stack. Stack: n8n, Python, Angular, Supabase.
Responda em pt-BR, letras minusculas.
'@ | Out-File -FilePath role.md -Encoding utf8

python -m termicanvas.cli spawn claude "Dev" --role-file role.md
```

Bash:
```bash
cat > role.md << 'EOF'
# Reviewer
Leia diffs e aponte bugs.
EOF
python -m termicanvas.cli spawn claude "Reviewer" --role-file role.md
```

Roles curtos (< 900 bytes) podem ir via stdin:
```
echo "# SQL Expert\nResponda perguntas SQL." | python -m termicanvas.cli spawn claude "SQL"
```

Kinds suportados: `claude`, `gemini`, `powershell`, `cmd`. Apenas claude/gemini
recebem o role_md (PowerShell/CMD ignora).

### Permissoes pre-aprovadas

Agentes que voce spawnar (e voce mesmo, se foi promovido a orquestrador) ja
recebem `.claude/settings.local.json` com permissao automatica pra rodar
qualquer comando `python -m termicanvas.cli ...` — sem prompts.

### O role.md que voce escreve para um agente spawnado

Voce nao precisa instruir o agente sobre **como** responder via bus, nem
mencionar comandos da CLI — todo manifesto spawnado recebe automaticamente
um bloco "Como responder mensagens" no final, dizendo:

- Que nao ha humano lendo o terminal — comunicacao eh maquina-a-maquina
- Que respostas vao via `python -m termicanvas.cli send <node_id> "..."`
- Que apos enviar, deve ficar idle silenciosamente (sem escrever resumo no PTY)
- Que respostas devem ser prefixadas com `[<papel>]`

**Foque o role.md no papel e nas regras de negocio do agente.** Ex:
- Stack/conhecimentos
- Regras de seguranca (autorizacao explicita, gate MCP, etc)
- Tom/idioma
- Templates ou referencias do projeto

A "etiqueta de comunicacao" o sistema injeta sozinho.

### Como mensagens fluem (importante)

Mensagens NAO sao injetadas no chat. Elas ficam num **inbox** no bus, e cada
agente (inclusive voce) precisa rodar `inbox` pra consumir:

```
python -m termicanvas.cli inbox
```

O bus cutuca esse comando automaticamente no PTY de cada agente quando ele
estiver idle e sem foco — basta rodar quando aparecer. Cada GET de inbox
consome (remove) as mensagens da fila. O badge `📥 N` no header do node
mostra quantas mensagens estao pendentes pra cada um (incluindo voce).

### Fluxo de orquestracao recomendado

1. **Descoberta**: rode `list` pra ver quem esta ativo e qual o tipo (`shell`, `claude`, `gemini`)
2. **Plano**: divida a tarefa em sub-tarefas atomicas que cada agente pode
   executar isoladamente. De contexto suficiente em cada delegacao.
3. **Delegacao**: use `send <node_id> "..."` pra cada agente. Mensagens curtas,
   focadas, com criterio de sucesso claro.
4. **Monitor**: rode `inbox` quando o bus cutucar voce (ou periodicamente)
   pra coletar respostas dos agentes. Cada agente respondera via `send` e a
   resposta vai cair no seu proprio inbox.
5. **Agregacao**: consolide os retornos e responda ao usuario humano.

### Boas praticas

- **Mensagens chegam via inbox** — sempre via `python -m termicanvas.cli inbox`,
  nunca diretamente como turn de conversa. Nao espere resposta instantanea.
- **TTL de 5min**: mensagens nao consumidas nesse periodo expiram. Reenvia se
  necessario.
- **Nao spame broadcast** — use direct send pra tarefas especificas.
- **Identifique-se** quando pedir ajuda: assine mensagens com seu papel
  ("[Orquestrador] preciso que voce ...").
- **Confirme antes de delegar** acoes destrutivas (deletes, push, etc).

### Quando NAO orquestrar

- Tarefas que voce mesmo pode resolver mais rapido que delegando
- Quando so ha 1 agente ativo alem de voce (overhead nao compensa)
- Quando o usuario quer apenas uma resposta direta, nao uma equipe
"""


def promote_to_orchestrator(cwd, agent_kind):
    """Apende (ou atualiza) o bloco de orquestracao no manifesto do agente.

    - Se o manifesto nao existe, cria um arquivo so com o bloco do orquestrador
      precedido pelo TERMICANVAS_MARKER (vira manifesto gerenciado).
    - Se ja existe e tem o bloco (entre os 2 markers), substitui in-place
      preservando o conteudo do projeto.
    - Se existe mas nao tem o bloco, apende no final precedido por `---`.

    Retorna o path do manifesto, ou None se algo falhou.
    """
    if agent_kind not in AGENT_KINDS:
        return None

    target = managed_manifest_path(cwd, agent_kind)
    if target is None:
        return None

    block = f"{ORCHESTRATOR_BEGIN}\n\n{_orchestrator_prompt()}\n{ORCHESTRATOR_END}\n"

    if not target.exists():
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            full = f"{TERMICANVAS_MARKER}\n\n# Agente Orquestrador\n\n{block}"
            target.write_text(full, encoding="utf-8")
            return target
        except Exception:
            return None

    try:
        current = target.read_text(encoding="utf-8")
    except Exception:
        return None

    if ORCHESTRATOR_BEGIN in current and ORCHESTRATOR_END in current:
        # Substitui o bloco existente preservando o resto.
        start = current.index(ORCHESTRATOR_BEGIN)
        end   = current.index(ORCHESTRATOR_END) + len(ORCHESTRATOR_END)
        new = current[:start] + block.rstrip() + current[end:]
    else:
        # Apende no final, com separador.
        sep = "\n\n---\n\n" if current.strip() else ""
        new = current.rstrip() + sep + block

    try:
        target.write_text(new, encoding="utf-8")
    except Exception:
        return None

    # Promovido a orquestrador precisa do CLI fluindo sem prompts.
    install_termicanvas_permissions(cwd, agent_kind)

    return target


def startup_command(agent_kind):
    """Comando inicial que sobe a CLI do agente apos PTY estar pronto."""
    spec = AGENT_KINDS.get(agent_kind)
    if not spec:
        return None
    return spec["command"]
