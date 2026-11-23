#!/usr/bin/env bash
# Instala (ou atualiza) o servidor de salas do Falido da Luta como serviço no Ubuntu
# (ex.: máquina grátis do Oracle Cloud). Rodar na pasta onde estão servidor_relay.py e protocolo.py:
#     bash instalar_servidor.sh
# Do seu PC, o enviar_servidor.ps1 manda os arquivos e roda este script sozinho.
set -euo pipefail
PORTA=50506
PASTA="$(cd "$(dirname "$0")" && pwd)"
USUARIO="$(whoami)"

# 1) firewall da própria máquina (o Ubuntu da Oracle bloqueia tudo que não é SSH)
if ! sudo iptables -C INPUT -p udp --dport "$PORTA" -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT -p udp --dport "$PORTA" -j ACCEPT
fi
if command -v netfilter-persistent >/dev/null; then
    sudo netfilter-persistent save >/dev/null      # a regra continua depois de reiniciar
fi
if command -v ufw >/dev/null && sudo ufw status | grep -q "Status: active"; then
    sudo ufw allow "$PORTA"/udp
fi

# 2) serviço: liga junto com a máquina e volta sozinho se cair
sudo tee /etc/systemd/system/falido-relay.service >/dev/null <<EOF
[Unit]
Description=Servidor de salas do Falido da Luta
After=network.target

[Service]
User=$USUARIO
WorkingDirectory=$PASTA
ExecStart=/usr/bin/python3 -u $PASTA/servidor_relay.py $PORTA
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable falido-relay >/dev/null 2>&1
sudo systemctl restart falido-relay
sleep 1
if systemctl is-active --quiet falido-relay; then
    echo "Pronto: servidor de salas rodando na porta UDP $PORTA."
    echo "(Confira também a regra UDP $PORTA na Security List do painel da Oracle.)"
else
    echo "O serviço não subiu. Veja o motivo com: journalctl -u falido-relay -n 30"
    exit 1
fi
