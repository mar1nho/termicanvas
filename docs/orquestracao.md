# Orquestracao

Um agente pode ser promovido a orquestrador para coordenar outros agentes no canvas.

## Promover agente

Marque `Promover a Orquestrador` no dialogo de criacao do agente.

O TermiCanvas adiciona um bloco delimitado ao manifesto do agente. A operacao e idempotente: se o bloco ja existir, ele e substituido.

## Spawn de agentes

Um orquestrador pode criar agentes usando:

```powershell
python -m termicanvas.cli spawn claude "Reviewer" --role-file role.md
python -m termicanvas.cli spawn codex "Builder" --role-file role.md
python -m termicanvas.cli spawn gemini "Research" --role-file role.md
```

O TermiCanvas cria uma pasta isolada em:

```text
<cwd>/.termicanvas/<slug-do-nome>/
```

Depois escreve o manifesto, inicia o terminal e desenha uma chain visual entre o orquestrador e o agente filho.

## Chains manuais

O botao de chain no header de um agente permite criar relacoes visuais entre agentes.
