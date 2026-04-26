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

from pathlib import Path

from .roles import get_role


TERMICANVAS_MARKER = "<!-- TermiCanvas managed role -->"


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
        "Mensagens enviadas chegam ao destinatario quando ele estiver idle e nao\n"
        "estiver em foco no canvas — entao nao espere resposta imediata.\n"
    )


def startup_command(agent_kind):
    """Comando inicial que sobe a CLI do agente apos PTY estar pronto."""
    spec = AGENT_KINDS.get(agent_kind)
    if not spec:
        return None
    return spec["command"]
