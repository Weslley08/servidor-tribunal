"""
Sistema de Ranking -- Persistencia e consulta de resultados.

Armazena vitorias, derrotas e confrontos diretos entre as partes.
Dados salvos em data/ranking.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import discord

from src.config import (
    COR_TRIBUNAL,
    EMOJI_TRIBUNAL,
    EMOJI_CULPADO,
    EMOJI_INOCENTE,
    CANAL_RANKING,
)

DATA_DIR = Path("data")
RANKING_FILE = DATA_DIR / "ranking.json"


# ==========================================================================
#  I/O
# ==========================================================================
def _carregar() -> dict:
    if RANKING_FILE.exists():
        with open(RANKING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"jogadores": {}}


def _salvar(data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(RANKING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _garantir_jogador(data: dict, user_id: int) -> dict:
    uid = str(user_id)
    if uid not in data["jogadores"]:
        data["jogadores"][uid] = {
            "vitorias": 0,
            "derrotas": 0,
            "confrontos": {},
        }
    return data["jogadores"][uid]


# ==========================================================================
#  Registro de resultados
# ==========================================================================
def registrar_resultado(vencedor_id: int, perdedor_id: int) -> None:
    """Registra vitoria/derrota e atualiza confronto direto."""
    data = _carregar()

    vencedor = _garantir_jogador(data, vencedor_id)
    perdedor = _garantir_jogador(data, perdedor_id)

    vencedor["vitorias"] += 1
    perdedor["derrotas"] += 1

    pid = str(perdedor_id)
    vid = str(vencedor_id)

    if pid not in vencedor["confrontos"]:
        vencedor["confrontos"][pid] = {"vitorias": 0, "derrotas": 0}
    vencedor["confrontos"][pid]["vitorias"] += 1

    if vid not in perdedor["confrontos"]:
        perdedor["confrontos"][vid] = {"vitorias": 0, "derrotas": 0}
    perdedor["confrontos"][vid]["derrotas"] += 1

    _salvar(data)


# ==========================================================================
#  Consultas
# ==========================================================================
def obter_leaderboard() -> list[dict]:
    """Retorna jogadores ordenados por mais derrotas."""
    data = _carregar()
    jogadores = []

    for uid, info in data["jogadores"].items():
        jogadores.append({
            "user_id": int(uid),
            "vitorias": info["vitorias"],
            "derrotas": info["derrotas"],
            "total": info["vitorias"] + info["derrotas"],
        })

    jogadores.sort(key=lambda x: (-x["derrotas"], -x["total"]))
    return jogadores


def obter_confrontos() -> list[dict]:
    """Retorna os confrontos diretos mais relevantes (top 15)."""
    data = _carregar()
    pares: dict[tuple, dict] = {}

    for uid, info in data["jogadores"].items():
        for opp_id, record in info["confrontos"].items():
            par = tuple(sorted([uid, opp_id]))
            if par not in pares:
                pares[par] = {
                    "user_a": int(par[0]),
                    "user_b": int(par[1]),
                    "a_vitorias": 0,
                    "b_vitorias": 0,
                }
            if uid == par[0]:
                pares[par]["a_vitorias"] = record.get("vitorias", 0)
            else:
                pares[par]["b_vitorias"] = record.get("vitorias", 0)

    resultado = list(pares.values())
    resultado.sort(key=lambda x: -(x["a_vitorias"] + x["b_vitorias"]))
    return resultado[:15]


# ==========================================================================
#  Embed de ranking
# ==========================================================================
def embed_ranking(guild: discord.Guild) -> discord.Embed:
    """Gera o embed completo do ranking."""
    leaderboard = obter_leaderboard()
    confrontos = obter_confrontos()

    embed = discord.Embed(
        title=f"{EMOJI_TRIBUNAL} Ranking do Tribunal",
        color=COR_TRIBUNAL,
    )

    if not leaderboard:
        embed.description = "*Nenhum caso julgado ainda. O tribunal aguarda.*"
        return embed

    # -- Placar Geral ------------------------------------------------------
    linhas = []
    for i, j in enumerate(leaderboard[:20], 1):
        member = guild.get_member(j["user_id"])
        nome = member.mention if member else f"<@{j['user_id']}>"
        v, d = j["vitorias"], j["derrotas"]
        pct = round(v / j["total"] * 100) if j["total"] > 0 else 0
        medal = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}.get(i, f"**{i}.**")
        linhas.append(f"{medal} {nome} -- {v}V / {d}D ({pct}%)")

    embed.add_field(
        name=f"{EMOJI_CULPADO} Placar Geral (por derrotas)",
        value="\n".join(linhas) or "*Vazio*",
        inline=False,
    )

    # -- Confrontos Diretos ------------------------------------------------
    if confrontos:
        linhas_c = []
        for c in confrontos[:10]:
            ma = guild.get_member(c["user_a"])
            mb = guild.get_member(c["user_b"])
            na = ma.mention if ma else f"<@{c['user_a']}>"
            nb = mb.mention if mb else f"<@{c['user_b']}>"
            linhas_c.append(f"{na} **{c['a_vitorias']}** x **{c['b_vitorias']}** {nb}")

        embed.add_field(
            name="\u2694\ufe0f Confrontos Diretos",
            value="\n".join(linhas_c),
            inline=False,
        )

    embed.set_footer(text="Tribunal // Atualizado a cada veredito")
    return embed


# ==========================================================================
#  Atualizar canal de ranking (chamado apos cada veredito)
# ==========================================================================
async def atualizar_ranking_canal(guild: discord.Guild) -> None:
    """Reenvia o embed de ranking no canal de ranking."""
    canal = discord.utils.get(guild.text_channels, name=CANAL_RANKING)
    if canal is None:
        print("[AVISO] Canal de ranking nao encontrado.")
        return

    # Limpar mensagens antigas do bot
    async for msg in canal.history(limit=50):
        if msg.author.id == guild.me.id:
            try:
                await msg.delete()
            except discord.NotFound:
                pass

    await canal.send(embed=embed_ranking(guild))
