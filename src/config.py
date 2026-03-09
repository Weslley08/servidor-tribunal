"""Configuracao centralizada carregada do .env."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "").strip()
GUILD_ID: str = os.getenv("GUILD_ID", "").strip()

if not DISCORD_TOKEN:
    print("x DISCORD_TOKEN e obrigatorio no .env")
    sys.exit(1)

if not GUILD_ID:
    print("x GUILD_ID e obrigatorio no .env")
    sys.exit(1)


# -- Nomes de categorias e canais -----------------------------------------
CATEGORIA_TRIBUNAL = "\u2696\ufe0f\u2503\u1d1b\u0280\u026a\u0299\u1d1c\u0274\u1d00\u029f"  # ⚖️┃ᴛʀɪʙᴜɴᴀʟ
CATEGORIA_CASOS_ATIVOS = "\U0001f4c2\u2503\u1d04\u1d00\ua731\u1d0f\ua731 \u1d00\u1d1b\u026a\u1d20\u1d0f\ua731"  # 📂┃ᴄᴀꜱᴏꜱ ᴀᴛɪᴠᴏꜱ
CANAL_PAINEL = "\U0001f4e9\u2503\u1d00\u0299\u0280\u026a\u0280-\u1d1b\u0280\u026a\u0299\u1d1c\u0274\u1d00"  # 📩┃ᴀʙʀɪʀ-ᴛʀɪʙᴜɴᴀ
CANAL_HISTORICO = "\U0001f4dc\u2503\u029c\u026a\ua731\u1d1b\u00f3\u0280\u026a\u1d04\u1d0f"  # 📜┃ʜɪꜱᴛóʀɪᴄᴏ
CANAL_REGRAS = "\U0001f4cb\u2503\u0280\u1d07\u0262\u0280\u1d00\ua731"  # 📋┃ʀᴇɢʀᴀꜱ
CANAL_RANKING = "\U0001f3c6\u2503\u0280\u1d00\u0274\u1d0b\u026a\u0274\u0262"  # 🏆┃ʀᴀɴᴋɪɴɢ
CANAL_CASAIS = "\U0001f491\u2503\u1d04\u1d00\ua731\u1d00\u026a\ua731"  # 💑┃ᴄᴀꜱᴀɪꜱ
CANAL_SALAO = "\U0001f4ac\u2503\ua731\u1d00\u029f\u00e3\u1d0f"  # 💬┃ꜱᴀʟãᴏ
CANAL_ADMIN = "\U0001f512\u2503\u1d00\u1d05\u1d0d\u026a\u0274"  # 🔒┃ᴀᴅᴍɪɴ

# -- Categoria e canais de voz (calls) ------------------------------------
CATEGORIA_CALLS = "\U0001f50a\u2503\u1d04\u1d00\u029f\u029f\ua731"  # 🔊┃ᴄᴀʟʟꜱ
CALL_RESENHA = "\u2615\u2503\u0280\u1d07\ua731\u1d07\u0274\u029c\u1d00"  # ☕┃ʀᴇꜱᴇɴʜᴀ
CALL_JOGANDO = "\U0001f3ae\u2503\u1d0a\u1d0f\u0262\u1d00\u0274\u1d05\u1d0f"  # 🎮┃ᴊᴏɢᴀɴᴅᴏ
CALL_ASSISTINDO = "\U0001f4fa\u2503\u1d00\ua731\ua731\u026a\ua731\u1d1b\u026a\u0274\u1d05\u1d0f"  # 📺┃ᴀꜱꜱɪꜱᴛɪɴᴅᴏ
CALL_MUSICA = "\U0001f3b5\u2503\u1d0d\u00fa\ua731\u026a\u1d04\u1d00"  # 🎵┃ᴍúꜱɪᴄᴀ
CALL_TREINO = "\U0001f4aa\u2503\u1d1b\u0280\u1d07\u026a\u0274\u1d0f"  # 💪┃ᴛʀᴇɪɴᴏ
CALL_GERAL = "\U0001f399\ufe0f\u2503\u0262\u1d07\u0280\u1d00\u029f"  # 🎙️┃ɢᴇʀᴀʟ
CHAT_RESENHA = "\u2615\u2503\u0280\u1d07\ua731\u1d07\u0274\u029c\u1d00-\u1d04\u029c\u1d00\u1d1b"  # ☕┃ʀᴇꜱᴇɴʜᴀ-ᴄʜᴀᴛ
CANAL_COMANDOS_BOT = "\U0001f916\u2503\u1d04\u1d0f\u1d0d\u1d00\u0274\u1d05\u1d0f\ua731"  # 🤖┃ᴄᴏᴍᴀɴᴅᴏꜱ

# -- Categoria e canal de logs ---------------------------------------------
CATEGORIA_LOGS = "\U0001f4cb\u2503\u029f\u1d0f\u0262\ua731"  # 📋┃ʟᴏɢꜱ
CANAL_ENTRADAS = "\U0001f7e2\u2503\u1d07\u0274\u1d1b\u0280\u1d00\u1d05\u1d00\ua731"  # 🟢┃ᴇɴᴛʀᴀᴅᴀꜱ
CANAL_SAIDAS = "\U0001f534\u2503\ua731\u1d00\u00ed\u1d05\u1d00\ua731"  # 🔴┃ꜱᴀíᴅᴀꜱ

# -- Nomes de cargos ------------------------------------------------------
CARGO_JUIZ = "\U0001f468\u200d\u2696\ufe0f \u1d0a\u1d1c\u026a\u1d22"  # 👨‍⚖️ ᴊᴜɪᴢ
CARGO_ADVOGADO = "\U0001f6e1\ufe0f \u1d00\u1d05\u1d20\u1d0f\u0262\u1d00\u1d05\u1d0f"  # 🛡️ ᴀᴅᴠᴏɢᴀᴅᴏ
CARGO_PROMOTOR = "\u2694\ufe0f \u1d18\u0280\u1d0f\u1d0d\u1d0f\u1d1b\u1d0f\u0280"  # ⚔️ ᴘʀᴏᴍᴏᴛᴏʀ
CARGO_REU = "\u2696\ufe0f \u0280\u00e9\u1d1c"  # ⚖️ ʀéᴜ
CARGO_VITIMA = "\U0001f494 \u1d20\u00ed\u1d1b\u026a\u1d0d\u1d00"  # 💔 ᴠíᴛɪᴍᴀ

# -- Emojis ----------------------------------------------------------------
EMOJI_TRIBUNAL = "\u2696\ufe0f"
EMOJI_ADVOGADO = "\U0001f6e1\ufe0f"
EMOJI_PROMOTOR = "\u2694\ufe0f"
EMOJI_JUIZ = "\U0001f468\u200d\u2696\ufe0f"
EMOJI_VEREDITO = "\U0001f528"
EMOJI_CULPADO = "\U0001f534"
EMOJI_INOCENTE = "\U0001f7e2"
EMOJI_ABRIR = "\U0001f4e9"
EMOJI_FECHAR = "\U0001f512"
EMOJI_PROVA = "\U0001f4ce"   # 📎
EMOJI_RANKING = "\U0001f3c6"  # 🏆

# -- Cores dos embeds (hex int) --------------------------------------------
COR_TRIBUNAL = 0xFFD700   # Dourado
COR_ABERTURA = 0x3498DB   # Azul
COR_CULPADO = 0xE74C3C    # Vermelho
COR_INOCENTE = 0x2ECC71   # Verde
COR_INFO = 0x9B59B6       # Roxo
COR_FECHAR = 0x95A5A6     # Cinza
COR_ADMIN = 0xE67E22      # Laranja
