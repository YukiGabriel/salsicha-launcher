# Salsicha Launcher 🌭
Launcher Minecraft com login Microsoft e modo offline.

## Rodar (dev)
```bash
uv sync
uv run python main.py
# ou pelo atalho instalado:
salsicha-launcher
```

## Logs do jogo
- Saída do Minecraft em `~/.salsicha-launcher/logs/game-<data>.log`

## Config
- Diretório do jogo: `~/.salsicha-launcher/minecraft`
- Contas salvas: `~/.salsicha-launcher/accounts.json`
- Para login Microsoft, crie um App no Azure e preencha Client ID + Redirect URL na tela.
  Docs: https://minecraft-launcher-lib.readthedocs.io/en/stable/tutorial/microsoft_login.html

## Stack
Python + PySide6 + minecraft-launcher-lib.
