---
name: termicanvas-send
description: Comunica com outros agentes hospedados no canvas TermiCanvas
---

# TermiCanvas — Comunicação Entre Agentes

Skill para enviar mensagens a outros agentes (Claude Code, Gemini, etc.) que estão hospedados no mesmo canvas TermiCanvas.

## Quando usar

Use esta skill sempre que precisar:

- Pedir uma **revisão** de código ou texto a outro agente do canvas
- Solicitar um **teste** ou validação que outro agente está mais bem posicionado para executar
- Buscar uma **segunda opinião** sobre uma decisão técnica ou de design
- **Dividir trabalho** entre agentes especializados (ex.: pedir ao agente Gemini que cuide do front enquanto você cuida do back)
- Encaminhar contexto que outro agente precisa para continuar uma tarefa

Não use para conversas com o próprio Gustavo — esta skill é exclusivamente entre agentes.

## Como usar

### Variáveis de ambiente

Antes de invocar o CLI, garanta que estas variáveis estão definidas no shell do agente:

- `TERMICANVAS_BUS_URL` — URL do bus de mensagens do canvas (ex.: `http://localhost:8765`)
- `TERMICANVAS_NODE_ID` — seu próprio ID de nó dentro do canvas (definido pelo host TermiCanvas no momento em que ele iniciou seu CLI)

Se uma das duas estiver ausente, o CLI falhará com erro claro — não tente adivinhar valores.

### Comandos

Listar agentes disponíveis no canvas:

```bash
python -m termicanvas.cli list
```

Enviar uma mensagem para um agente específico:

```bash
python -m termicanvas.cli send <node_id> "mensagem aqui"
```

Verificar seu próprio nó (útil para debug):

```bash
python -m termicanvas.cli whoami
```

## Regras de entrega

A entrega de mensagens no TermiCanvas é **assíncrona e condicional**:

- A mensagem só é entregue quando o destinatário está **idle** (sem tarefa rodando) **E desselecionado** (sem foco do usuário no painel dele)
- Isso significa que **não há resposta imediata garantida** — não fique em loop esperando reply
- Se você precisa do retorno antes de continuar, sinalize isso na mensagem e siga com outras tarefas; volte a checar depois
- Mensagens enviadas para agentes ocupados ficam enfileiradas até que ele entre em idle

## Boas práticas

- **Inclua contexto suficiente** — o outro agente não tem acesso ao seu histórico. Cite arquivos por caminho absoluto, cole trechos relevantes, explique o que já foi tentado
- **Não inunde** — evite mandar várias mensagens em sequência. Consolide em uma só, bem estruturada
- **Encerre conversas com confirmação** — quando a tarefa colaborativa terminar, mande um `send` curto confirmando o fim ("ok, terminei aqui, obrigado") para que o outro agente saiba que pode liberar contexto
- **Identifique-se quando relevante** — se a mensagem inicia uma colaboração nova, mencione seu papel ("sou o agente do projeto X, preciso de ajuda com Y")
- **Prefira pedidos acionáveis** — em vez de "o que você acha?", peça "revise o arquivo Z e aponte problemas de segurança"
