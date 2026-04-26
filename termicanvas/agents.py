"""Specs de CLIs de agente (Claude Code, Gemini CLI) e helpers de instalacao.

Modos de manifesto:
- "existing" — TermiCanvas nao toca em nada; o agente usa o CLAUDE.md/GEMINI.md
              que ja existir no cwd (responsabilidade do projeto).
- "managed"  — TermiCanvas escreve `<cwd>/.termicanvas/role.md` e anexa um bloco
              delimitado no CLAUDE.md/GEMINI.md raiz com `@.termicanvas/role.md`.
              Ao fechar o terminal, o bloco e removido.
"""

from pathlib import Path

from .roles import get_role


# Marcadores do bloco gerenciado — substituiveis idempotentemente
ROLE_BLOCK_BEGIN = "<!-- BEGIN TERMICANVAS-ROLE -->"
ROLE_BLOCK_END   = "<!-- END TERMICANVAS-ROLE -->"


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


def role_md_path(cwd):
    """Caminho do role gerenciado dentro do projeto-alvo."""
    return Path(cwd) / ".termicanvas" / "role.md"


def install_role(cwd, agent_kind, role_name, mode="managed"):
    """Aplica role no projeto. Retorna o path do arquivo gerenciado (ou None).

    mode="existing": no-op. Agente usa o manifesto que ja existir.
    mode="managed":  cria/atualiza .termicanvas/role.md com conteudo do role,
                     e anexa @.termicanvas/role.md ao CLAUDE.md raiz dentro
                     de um bloco delimitado.
    """
    if agent_kind not in AGENT_KINDS:
        return None
    if mode != "managed":
        return None

    cwd_path = Path(cwd)
    if not cwd_path.is_dir():
        return None

    role = get_role(role_name) if role_name else None
    role_content = role.content if role else "# Role livre\n\nResponda em portugues, de forma direta.\n"

    role_content_with_skill = (
        role_content
        + "\n\n---\n\n"
        + _send_skill_instructions()
    )

    # 1. Escreve .termicanvas/role.md
    role_path = role_md_path(cwd_path)
    role_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        role_path.write_text(role_content_with_skill, encoding="utf-8")
    except Exception:
        return None

    # 2. Anexa bloco delimitado ao manifesto raiz
    manifest_name = AGENT_KINDS[agent_kind]["manifest"]
    root_manifest = cwd_path / manifest_name
    _upsert_role_block(root_manifest, role_path)

    return role_path


def remove_role_block(cwd, agent_kind):
    """Remove o bloco delimitado do CLAUDE.md/GEMINI.md raiz.

    Idempotente. Nao apaga .termicanvas/role.md (preserva edicoes do user).
    """
    if agent_kind not in AGENT_KINDS:
        return
    manifest_name = AGENT_KINDS[agent_kind]["manifest"]
    root_manifest = Path(cwd) / manifest_name
    if not root_manifest.exists():
        return
    try:
        text = root_manifest.read_text(encoding="utf-8")
    except Exception:
        return

    new_text = _strip_role_block(text)
    if new_text == text:
        return  # bloco nao estava presente

    try:
        # Se ficou vazio (so tinha o bloco), apaga o arquivo
        if new_text.strip():
            root_manifest.write_text(new_text, encoding="utf-8")
        else:
            root_manifest.unlink()
    except Exception:
        pass


def _upsert_role_block(manifest_path, role_path):
    """Cria/atualiza o bloco TERMICANVAS-ROLE no manifesto raiz."""
    block = (
        f"\n{ROLE_BLOCK_BEGIN}\n"
        f"@.termicanvas/role.md\n"
        f"{ROLE_BLOCK_END}\n"
    )

    if manifest_path.exists():
        try:
            current = manifest_path.read_text(encoding="utf-8")
        except Exception:
            return
        stripped = _strip_role_block(current)
        new_text = stripped.rstrip() + "\n" + block
    else:
        new_text = block.lstrip()

    try:
        manifest_path.write_text(new_text, encoding="utf-8")
    except Exception:
        pass


def _strip_role_block(text):
    """Remove qualquer bloco BEGIN/END TERMICANVAS-ROLE existente."""
    if ROLE_BLOCK_BEGIN not in text:
        return text
    out = []
    skipping = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == ROLE_BLOCK_BEGIN:
            skipping = True
            continue
        if stripped == ROLE_BLOCK_END:
            skipping = False
            continue
        if not skipping:
            out.append(line)
    return "".join(out)


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
