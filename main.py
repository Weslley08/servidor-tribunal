"""
Tribunal -- Bot Discord para resolucao de conflitos entre partes.

100% baseado em embeds, canais e botoes. Sem slash commands.
Casos exigem apresentacao de provas (prints, clips, etc.) de ambos os lados.
Resultados alimentam um ranking persistente.

Ao iniciar, o bot:
  1. Busca cargos, categorias e canais existentes no servidor
  2. Atualiza topics e envia embeds fixos nos canais
  3. Toda interacao e feita por botoes e modais

Uso:
    1. Preencha o .env (veja .env.example)
    2. pip install -r requirements.txt
    3. python main.py
"""

import sys
import os
import asyncio
import traceback
from datetime import datetime, time, timezone, timedelta

# Fix encoding e buffering no Windows
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

import discord

from src.config import DISCORD_TOKEN, GUILD_ID, CANAL_COMANDOS_BOT, CANAL_ENTRADAS, CANAL_SAIDAS
from src.setup import setup_servidor, enviar_embeds_fixos
from src.tribunal import PainelView, CasoView, AdminView, _carregar_casos
from src.casais import PedidoCasalView, CasaisView


def main():
    intents = discord.Intents.default()
    intents.members = True

    client = discord.Client(intents=intents)

    async def _limpar_canal_comandos(guild: discord.Guild):
        """Apaga todas as mensagens do canal de comandos de bot."""
        canal = discord.utils.get(guild.text_channels, name=CANAL_COMANDOS_BOT)
        if canal is None:
            return
        try:
            deleted = await canal.purge(limit=500)
            print(f"[LIMPEZA] {len(deleted)} mensagens removidas de #{canal.name}", flush=True)
        except discord.Forbidden:
            print(f"[AVISO] Sem permissao para limpar #{canal.name}", flush=True)
        except Exception as e:
            print(f"[ERRO] Limpeza falhou: {e}", flush=True)

    async def _agendar_limpeza_diaria(guild: discord.Guild):
        """Loop que limpa o canal de comandos todo dia a meia-noite (BRT)."""
        BRT = timezone(timedelta(hours=-3))
        await asyncio.sleep(5)  # esperar setup terminar
        while True:
            agora = datetime.now(BRT)
            # Proximo meia-noite BRT
            amanha = (agora + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            espera = (amanha - agora).total_seconds()
            print(f"[LIMPEZA] Proxima limpeza em {espera:.0f}s ({amanha.strftime('%d/%m %H:%M BRT')})", flush=True)
            await asyncio.sleep(espera)
            await _limpar_canal_comandos(guild)

    @client.event
    async def on_ready():
        print(f"\n{'='*50}")
        print(f"  Tribunal -- Online!")
        print(f"  Bot: {client.user} (ID: {client.user.id})")
        print(f"  Guild alvo: {GUILD_ID}")
        print(f"{'='*50}\n")

        # Registrar views persistentes (sobrevivem a restarts)
        client.add_view(PainelView())
        client.add_view(CasoView())
        client.add_view(AdminView())
        client.add_view(PedidoCasalView())
        client.add_view(CasaisView())

        # Restaurar casos ativos do disco (sobrevive a restarts)
        _carregar_casos()

        # Auto-setup: cria cargos/canais e envia embeds fixos
        guild = client.get_guild(int(GUILD_ID))
        if guild is None:
            print(f"[ERRO] Guild {GUILD_ID} nao encontrada!", flush=True)
            return

        try:
            resultado = await setup_servidor(guild)
            await enviar_embeds_fixos(guild, resultado)
            print("[READY] Bot pronto! Tudo configurado via canais e embeds.", flush=True)
        except Exception as e:
            print(f"[ERRO] Falha no setup: {e}", flush=True)
            traceback.print_exc()

        # Iniciar limpeza diaria do canal de comandos
        client.loop.create_task(_agendar_limpeza_diaria(guild))

    @client.event
    async def on_member_join(member: discord.Member):
        canal = discord.utils.get(member.guild.text_channels, name=CANAL_ENTRADAS)
        if canal is None:
            return
        embed = discord.Embed(
            title="\U0001f7e2 Novo Membro",
            description=(
                f"{member.mention} entrou no servidor!\n\n"
                f"**Conta criada em:** {member.created_at.strftime('%d/%m/%Y')}\n"
                f"**Membros agora:** {member.guild.member_count}"
            ),
            color=0x2ECC71,
            timestamp=datetime.now(timezone(timedelta(hours=-3))),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        await canal.send(embed=embed)

    @client.event
    async def on_member_remove(member: discord.Member):
        canal = discord.utils.get(member.guild.text_channels, name=CANAL_SAIDAS)
        if canal is None:
            return
        # Calcular tempo no servidor
        if member.joined_at:
            delta = datetime.now(timezone.utc) - member.joined_at
            dias = delta.days
            if dias >= 365:
                tempo = f"{dias // 365} ano(s) e {dias % 365} dia(s)"
            elif dias >= 30:
                tempo = f"{dias // 30} mes(es) e {dias % 30} dia(s)"
            else:
                tempo = f"{dias} dia(s)"
        else:
            tempo = "Desconhecido"

        embed = discord.Embed(
            title="\U0001f534 Membro Saiu",
            description=(
                f"{member.mention} ({member.display_name}) saiu do servidor.\n\n"
                f"**Tempo no servidor:** {tempo}\n"
                f"**Membros agora:** {member.guild.member_count}"
            ),
            color=0xE74C3C,
            timestamp=datetime.now(timezone(timedelta(hours=-3))),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        await canal.send(embed=embed)

    print("[BOOT] Iniciando bot...", flush=True)
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
