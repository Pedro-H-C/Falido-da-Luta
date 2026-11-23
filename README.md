# Falido da Luta

Jogo de luta 2D feito em Python com [pygame](https://www.pygame.org/): 5 lutadores, golpe rápido,
golpe forte, SUPER de cada personagem, parry, dash, modo contra a CPU (3 dificuldades),
dois jogadores no mesmo PC e modo online (direto pelo Radmin VPN / mesmo Wi-Fi; guia em
[Luta/online/COMO_JOGAR_ONLINE.md](Luta/online/COMO_JOGAR_ONLINE.md)).

## Baixar e jogar

1. Na página [Releases](../../releases), baixe o `FalidoDaLuta.zip` da versão mais nova.
2. Descompacte o .zip inteiro e abra `FalidoDaLuta/FalidoDaLuta.exe` (Windows).

Não precisa instalar Python nem nada.

### Controles

| | P1 | P2 |
|---|---|---|
| Andar | A / D | Setas |
| Pular | W | Seta para cima |
| Golpe rápido / forte | R / T | N / M |
| SUPER | Y | Vírgula |

Toque para trás na hora do golpe: **parry**. Dois toques numa direção: **dash**.
Esc: pausa. F11: tela cheia.

## Rodar pelo código

```
pip install -r Luta/requirements.txt
python Luta/main.py
```

Gerar o .exe no próprio PC: `python Luta/tools/gerar_jogo.py` (ou dois cliques em
`Luta/gerar_jogo.bat`). O resultado sai em `Luta/dist/FalidoDaLuta.zip`.
As versões publicadas em Releases são geradas automaticamente pelo GitHub Actions
(`.github/workflows/gerar-jogo.yml`) a partir deste código.

## Créditos

- Código, arte dos lutadores e sons dos golpes: Pedro-H-C.
- Músicas: Kevin MacLeod ([incompetech.com](https://incompetech.com/)), licença
  [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/):
  "Curse of the Scarab" (luta) e a música do menu.
- Sons de interface: [Kenney](https://www.kenney.nl/) (Interface Sounds), licença CC0.
- Fonte: Turok.

## Licença

Código sob a licença MIT (ver [LICENSE](LICENSE)). Os arquivos de terceiros listados em
Créditos mantêm as licenças deles.

## Code signing policy / Política de assinatura de código

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by
[SignPath Foundation](https://signpath.org/).

- Committers and reviewers: [Pedro-H-C](https://github.com/Pedro-H-C)
- Approvers: [Pedro-H-C](https://github.com/Pedro-H-C)

Only executables built by the GitHub Actions workflow of this repository, from the source code in
this repository, are signed. Every signing request is manually approved.

### Privacy policy / Privacidade

This program will not transfer any information to other networked systems unless specifically
requested by the user. Only when a player chooses **Online** does the game connect to the room
server and to the other player, and the only data sent is what the match needs: the room code,
the pressed buttons and the game version. No personal data is collected or stored.

O jogo só usa a internet quando o jogador escolhe **Online**. Nesse caso ele manda apenas o que a
partida precisa: o código da sala, os botões apertados e a versão do jogo. Nenhum dado pessoal é
coletado nem guardado.
