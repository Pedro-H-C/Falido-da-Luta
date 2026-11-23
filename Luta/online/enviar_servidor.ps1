# Manda o servidor de salas para a máquina do Oracle Cloud e instala/atualiza o serviço.
# No PowerShell, na pasta Luta:
#     .\online\enviar_servidor.ps1 -IP 1.2.3.4 -Chave C:\oracle\ssh-key.key
# (Se o Windows bloquear o script: powershell -ExecutionPolicy Bypass -File .\online\enviar_servidor.ps1 ...)
param(
    [Parameter(Mandatory = $true)][string]$IP,
    [Parameter(Mandatory = $true)][string]$Chave,
    [string]$Usuario = "ubuntu"
)
$pasta = Split-Path -Parent $MyInvocation.MyCommand.Path
$destino = "$Usuario@$IP"

function Test-Passo($nome) {
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Falhou: $nome" -ForegroundColor Red
        exit 1
    }
}

# o ssh do Windows recusa chave que outros usuários do PC podem ler
icacls $Chave /inheritance:r /grant:r "$($env:USERNAME):(R)" | Out-Null

ssh -i $Chave -o StrictHostKeyChecking=accept-new $destino 'mkdir -p ~/relay'
Test-Passo "conectar na máquina (confira o IP e a chave)"
scp -i $Chave "$pasta\servidor_relay.py" "$pasta\protocolo.py" "$pasta\instalar_servidor.sh" "${destino}:~/relay/"
Test-Passo "mandar os arquivos"
# o git do Windows pode trocar o fim de linha dos arquivos; o Linux quer só \n
ssh -i $Chave $destino 'sed -i "s/\r$//" ~/relay/* && bash ~/relay/instalar_servidor.sh'
Test-Passo "instalar o serviço"
