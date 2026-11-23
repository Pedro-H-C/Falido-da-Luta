# Como jogar o Falido da Luta online

Tem dois jeitos: **direto** (pelo Radmin VPN ou no mesmo Wi-Fi, funciona sem servidor nenhum)
e **pelo servidor de salas** (com código, sem instalar nada; só aparece no menu quando o jogo
tem um servidor configurado).

## Jogar direto (Radmin VPN ou mesmo Wi-Fi)

1. Os dois instalam o **Radmin VPN** (grátis, sem cadastro) e entram na **mesma rede** dele: um
   cria a rede (Rede > Criar rede, com nome e senha) e o outro entra nela (Rede > Entrar em
   uma rede existente). No mesmo Wi-Fi não precisa do Radmin.
2. Um escolhe **Online > Criar sala direta**. A tela mostra os IPs dele; o do Radmin começa
   com `26.`.
3. O outro escolhe **Online > Entrar pelo IP** e digita esse IP (o jogo lembra o último).
4. Se o Windows perguntar se o jogo pode usar a rede, clique em **Permitir** marcando também
   as redes **públicas** (o Windows costuma tratar a rede do Radmin como pública).

Se não conectar: confira se o Radmin está ligado nos dois, se estão na mesma rede dele (o
amigo aparece online na lista) e se o Windows não bloqueou o jogo no firewall.

## Jogar pelo servidor (código da sala)

1. Os dois jogadores abrem o jogo e escolhem **Online**.
2. Um escolhe **Criar sala**. O jogo mostra um código de 4 letras (ex.: `B4MU`).
3. Ele passa o código para o amigo, que escolhe **Entrar com código** e digita esse código.
4. Os dois escolhem os lutadores e a luta começa.

Detalhes:

- Os dois precisam ter **exatamente a mesma versão** do jogo (a mesma pasta `Luta`). Se os
  arquivos da luta forem diferentes, o jogo recusa a conexão e avisa.
- Quem **cria a sala** é o P1 (esquerda); quem **entra** é o P2 (direita).
- Os dois conjuntos de teclas funcionam no online: A/D ou setas, W ou cima, R/T ou N/M, Y ou vírgula.
- No online a luta não pausa: o Esc abre um menu por cima, mas a luta continua.
- Na primeira vez, o Windows pode perguntar se o Python pode usar a rede: clique em **Permitir**.
- Ninguém precisa abrir porta no roteador nem instalar VPN: os dois falam com o servidor de salas.

## O servidor de salas

O jogo encontra o amigo por um servidor na internet que roda `servidor_relay.py`. Ele só junta
os dois jogadores pelo código e repassa os pacotes; a luta é calculada nos computadores dos
jogadores. Só precisa de Python (não precisa de pygame): bastam `servidor_relay.py` e
`protocolo.py`. Usa a porta **UDP 50506**.

O endereço do servidor fica no jogo, em `ONLINE_SERVER` no começo da parte ONLINE do `main.py`.
Vazio, o online avisa que não está configurado.

### Onde ele roda

Numa máquina grátis do **Oracle Cloud** ("Always Free"), região São Paulo:

1. Conta criada em oracle.com/br/cloud/free com a região inicial **Brazil East (Sao Paulo)**.
2. Máquina: Compute > Instances > Create instance, imagem **Ubuntu**, shape **Always Free**
   (VM.Standard.E2.1.Micro ou VM.Standard.A1.Flex), com IP público e a chave SSH baixada.
3. Porta liberada no painel: na Security List da subnet, regra de entrada **UDP 50506** vinda
   de `0.0.0.0/0`.

### Instalar ou atualizar

No PowerShell, na pasta `Luta`, com o IP da máquina e o arquivo da chave:

```
.\online\enviar_servidor.ps1 -IP 1.2.3.4 -Chave C:\oracle\ssh-key.key
```

Ele manda os arquivos e roda `instalar_servidor.sh` na máquina, que libera a porta no firewall
do Ubuntu e instala o serviço `falido-relay` (liga sozinho com a máquina e volta se cair).
Rode de novo sempre que `servidor_relay.py` ou `protocolo.py` mudarem. Mudanças só na luta
(`fighter.py`, `main.py`) não precisam de nada no servidor.

Conferir o servidor (entrando com `ssh -i C:\oracle\ssh-key.key ubuntu@1.2.3.4`):

- `systemctl status falido-relay` mostra se está rodando;
- `journalctl -u falido-relay -f` mostra as salas sendo criadas (Ctrl+C para sair).

Se o jogo disser que o servidor não respondeu: confira a regra UDP 50506 na Security List, se o
serviço está rodando e se o IP em `ONLINE_SERVER` é o da máquina.

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
  em coisa que muda a luta. Efeitos visuais e sons podem usar os dois à vontade.
- Arquivos: `protocolo.py` (formato dos pacotes), `sessao.py` (conexão, ping, seleção),
  `lockstep.py` (troca de botões e conferência), `servidor_relay.py` (servidor de salas),
  `instalar_servidor.sh` e `enviar_servidor.ps1` (instalação do servidor).
- A sala direta é `NetSession.host` (espera na porta UDP 50505) e `NetSession.join` (entra pelo
  IP); a sala no servidor é `NetSession.relay`.
