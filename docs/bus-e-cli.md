# Bus e CLI

O bus local permite que agentes conversem entre si usando HTTP em `127.0.0.1`.

## Variaveis injetadas

Cada agente recebe:

- `TERMICANVAS_BUS_URL`
- `TERMICANVAS_NODE_ID`

## Comandos

```powershell
python -m termicanvas.cli list
python -m termicanvas.cli whoami
python -m termicanvas.cli send <node_id> "mensagem"
python -m termicanvas.cli broadcast "mensagem"
python -m termicanvas.cli inbox
python -m termicanvas.cli status <msg_id>
python -m termicanvas.cli spawn <kind> "<nome>"
```

Kinds aceitos no `spawn`:

- `claude`
- `codex`
- `gemini`
- `powershell`
- `cmd`

## Entrega

Mensagens ficam em fila e sao entregues quando o terminal alvo esta idle e sem foco. Isso evita que uma mensagem seja injetada enquanto o usuario esta digitando.

Mensagens expiram apos o TTL configurado no bus.
