# Como jogar o Falido da Luta online

Cada jogador roda o jogo no próprio computador. No menu principal escolha **Online**.

## Antes de tudo

- Os dois precisam ter **exatamente a mesma versão** do jogo (a mesma pasta `Luta`). Se os
  arquivos da luta forem diferentes, o jogo recusa a conexão e avisa.
- Na primeira vez, o Windows pode perguntar se o Python pode usar a rede: clique em **Permitir**
  (marque redes privadas e públicas).
- Quem **cria a sala** é sempre o P1 (esquerda); quem **entra** é o P2 (direita).
- Os dois conjuntos de teclas funcionam no online: A/D ou setas, W ou cima, R/T ou N/M, Y ou vírgula.
- No online a luta não pausa: o Esc abre um menu por cima, mas a luta continua.

## Jeito 1: VPN (mais fácil pela internet)

Programas gratuitos como **Radmin VPN**, **Tailscale** ou **ZeroTier** fazem os dois computadores
parecerem estar na mesma rede, sem mexer no roteador.

1. Os dois instalam o mesmo programa e entram na mesma rede dele.
2. Um escolhe **Criar sala**. A tela mostra os IPs da máquina; use o da VPN
   (Radmin costuma começar com `26.`, Tailscale com `100.`).
3. O outro escolhe **Entrar pelo IP** e digita esse IP.

Na mesma casa (mesmo Wi-Fi) é igual, sem VPN: use o IP que aparece na tela (ex.: `192.168.0.10`).

## Jeito 2: abrir a porta no roteador

1. Quem vai criar a sala abre (redireciona) a porta **UDP 50505** no roteador para o IP local
   do computador (o que aparece na tela da sala).
2. Descobre o IP público (pesquise "qual meu ip") e passa para o amigo.
3. O amigo escolhe **Entrar pelo IP** e digita esse IP público.

Muitas operadoras usam CGNAT, e aí abrir a porta não adianta. Nesse caso use a VPN ou o servidor.

## Jeito 3: servidor de salas

Um computador com IP público (um VPS, ou o PC de alguém que consiga abrir a porta) roda:

```
python online/servidor_relay.py
```

Ele usa a porta **UDP 50506** e só precisa de Python (não precisa de pygame, nem do jogo
inteiro: bastam `servidor_relay.py` e `protocolo.py`). Depois os dois jogadores escolhem
**Sala no servidor**, digitam o endereço desse servidor e o **mesmo código de sala**
(qualquer palavra, ex.: `FALIDOS`). Quem chegar primeiro é o P1. Os pacotes passam pelo
servidor, então o ping fica um pouco maior que na conexão direta.

## Como funciona (para quem mexer no código)

- Os dois computadores calculam a **mesma luta**, frame a frame. Pela rede só vão os botões
  (6 bits por frame), por UDP, repetidos até o outro confirmar (pacote perdido não trava nada).
- Os botões apertados agora valem alguns frames depois (o "atraso dos botões", mostrado na
  luta). O jogo escolhe o atraso pelo ping, entre 2 e 9 frames. Se os botões do outro não
  chegaram a tempo, a luta espera um pouco em vez de adivinhar.
- A cada 30 frames os dois comparam um resumo (crc) da luta. Se der diferente, a luta é
  interrompida com o aviso "dessincronizou".
- Por isso a lógica da luta (`fighter.py` e a classe `Match` do `main.py`) precisa ser
  **determinística**: nada de relógio do computador (`pygame.time.get_ticks`) nem de `random`
  em coisa que muda a luta. Efeitos visuais (faíscas, tremor) podem usar os dois à vontade.
- Arquivos: `protocolo.py` (formato dos pacotes), `sessao.py` (conexão, ping, seleção),
  `lockstep.py` (troca de botões e conferência), `servidor_relay.py` (servidor de salas).
