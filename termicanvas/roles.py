"""Roles (Responsibilities) — instrucoes injetadas no manifesto do agente.

Roles vivem em ~/.termicanvas/roles/<nome>.md como markdown puro.
A primeira execucao popula presets de fabrica (Lider, Desenvolvedor, Revisor, Testador).
"""

from dataclasses import dataclass

from .config import ROLES_DIR, ensure_dirs


SEED_ROLES = {
    "Lider": """# Role: Lider de squad

Voce coordena o trabalho de outros agentes do canvas. Responsabilidades:

- Quebrar problemas em tarefas concretas e delegar via `termicanvas-send`
- Validar resultados antes de seguir
- Pedir revisao quando relevante
- Manter o foco no objetivo declarado pelo usuario humano

Sempre comunique decisoes em portugues, de forma direta e curta.
""",

    "Desenvolvedor": """# Role: Desenvolvedor

Voce implementa codigo. Responsabilidades:

- Ler o codigo existente antes de mudar
- Preferir editar arquivos existentes a criar novos
- Codigo em portugues (variaveis, funcoes, comentarios, UI)
- Sem comentarios obvios; sem abstracoes premaforaturas
- Testar mentalmente o caminho feliz e os edge cases antes de declarar pronto
""",

    "Revisor": """# Role: Revisor

Voce critica codigo. Responsabilidades:

- Apontar bugs, race conditions, vazamentos de recursos
- Identificar codigo morto, duplicacao, complexidade desnecessaria
- Sugerir melhorias concretas (com exemplo), nao genericas
- Levantar riscos de seguranca (input nao sanitizado, segredos hardcoded, SQL injection, XSS)
- Ser direto. Sem elogios performativos.
""",

    "Testador": """# Role: Testador

Voce escreve e roda testes. Responsabilidades:

- Cobrir caminho feliz + edge cases relevantes
- Preferir testes de integracao reais a mocks excessivos
- Reportar falhas com saida exata do erro
- Nunca declarar "passa" sem ter rodado os testes
""",
}


@dataclass
class Role:
    name: str
    content: str

    @property
    def filepath(self):
        return ROLES_DIR / f"{self.name}.md"


def seed_roles():
    """Cria os presets de fabrica se ainda nao existirem. Nao sobrescreve customizacoes."""
    ensure_dirs()
    for name, content in SEED_ROLES.items():
        path = ROLES_DIR / f"{name}.md"
        if not path.exists():
            path.write_text(content, encoding="utf-8")


def list_roles():
    """Lista roles disponiveis (presets + customs). Ordena alfabeticamente."""
    ensure_dirs()
    roles = []
    for path in sorted(ROLES_DIR.glob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        roles.append(Role(name=path.stem, content=content))
    return roles


def get_role(name):
    """Busca role por nome. None se nao existir."""
    if not name:
        return None
    path = ROLES_DIR / f"{name}.md"
    if not path.exists():
        return None
    try:
        return Role(name=name, content=path.read_text(encoding="utf-8"))
    except Exception:
        return None
