"""
Setup do servidor: localiza canais e categorias existentes e atualiza embeds fixos.

Executado toda vez que o bot inicia. NAO cria cargos, categorias ou canais --
apenas busca os que ja existem no servidor e atualiza topics/embeds.
"""

import discord

from src.config import (
    CATEGORIA_TRIBUNAL,
    CATEGORIA_CASOS_ATIVOS,
    CATEGORIA_CALLS,
    CANAL_PAINEL,
    CANAL_HISTORICO,
    CANAL_REGRAS,
    CANAL_RANKING,
    CANAL_CASAIS,
    CANAL_CASOS,
    CANAL_SALAO,
    CANAL_ADMIN,
    CHAT_RESENHA,
    CANAL_COMANDOS_BOT,
    CATEGORIA_LOGS,
    CANAL_ENTRADAS,
    CANAL_SAIDAS,
    CARGO_JUIZ,
    CARGO_ADVOGADO,
    CARGO_PROMOTOR,
    CARGO_REU,
    CARGO_VITIMA,
)
from src.embeds import embed_painel, embed_regras, embed_admin


def _find(collection, name: str):
    return discord.utils.get(collection, name=name)


# -- Topics esperados (sincroniza se mudou) --------------------------------
_TOPICS = {
    "canal_painel": "Clique no botao abaixo para abrir uma tribuna!",
    "canal_historico": "Registro de todos os casos julgados",
    "canal_regras": "Regras do Tribunal",
    "canal_ranking": "Ranking de vitorias e derrotas",
    "canal_casais": "Registre seu casal e veja o ranking de relacionamentos",
    "canal_casos": "Casos em andamento -- se voluntarie como advogado ou promotor!",
    "canal_salao": "Converse sobre os casos e de opinioes!",
    "canal_admin": "Painel administrativo do Tribunal (Juizes e Admins)",
    "canal_entradas": "Registro de novos membros no servidor",
    "canal_saidas": "Registro de membros que sairam do servidor",
    "chat_resenha": "Resenha livre! Manda o papo sem julgamento.",
    "canal_comandos_bot": "Use comandos de bots de musica e outros aqui. Limpo automaticamente todo dia.",
}


async def _sync_topic(canal: discord.TextChannel | None, topic_key: str):
    """Atualiza o topic do canal se necessario."""
    if canal is None:
        return
    topic = _TOPICS.get(topic_key, "")
    if canal.topic != topic:
        await canal.edit(topic=topic, reason="Setup Tribunal -- topic atualizado")
        print(f"  ~ Topic atualizado: #{canal.name}")


# ==========================================================================
#  Setup principal
# ==========================================================================
async def setup_servidor(guild: discord.Guild) -> dict:
    """Busca cargos, categorias e canais existentes. Retorna dict com tudo."""
    print(f"\n{'='*50}")
    print(f"  Setup -- {guild.name}")
    print(f"{'='*50}")

    # -- 1. Cargos (buscar existentes) -------------------------------------
    print("\n[CARGOS]")
    cargos: dict[str, discord.Role | None] = {}
    for nome in (CARGO_JUIZ, CARGO_ADVOGADO, CARGO_PROMOTOR, CARGO_REU, CARGO_VITIMA):
        role = _find(guild.roles, nome)
        if role:
            print(f"  . {role.name}")
        else:
            print(f"  ! NAO encontrado: {nome}")
        cargos[nome] = role

    # -- 2. Categorias (buscar existentes) ---------------------------------
    print("\n[CATEGORIAS]")
    cat_tribunal = _find(guild.categories, CATEGORIA_TRIBUNAL)
    cat_casos    = _find(guild.categories, CATEGORIA_CASOS_ATIVOS)
    cat_calls    = _find(guild.categories, CATEGORIA_CALLS)
    cat_logs     = _find(guild.categories, CATEGORIA_LOGS)

    for nome, cat in [
        (CATEGORIA_TRIBUNAL, cat_tribunal), (CATEGORIA_CASOS_ATIVOS, cat_casos),
        (CATEGORIA_CALLS, cat_calls), (CATEGORIA_LOGS, cat_logs),
    ]:
        print(f"  {'.' if cat else '!'} {nome}" + (" (NAO encontrada)" if not cat else ""))

    # -- 3. Canais (buscar existentes + sync topics) -----------------------
    print("\n[CANAIS]")

    def _buscar_texto(nome: str, categoria: discord.CategoryChannel | None) -> discord.TextChannel | None:
        if categoria is None:
            # Fallback: buscar em todos os canais da guild
            canal = _find(guild.text_channels, nome)
        else:
            canal = _find(categoria.text_channels, nome)
        print(f"  {'.' if canal else '!'} #{nome}" + (" (NAO encontrado)" if not canal else ""))
        return canal

    canal_painel     = _buscar_texto(CANAL_PAINEL, cat_tribunal)
    canal_historico  = _buscar_texto(CANAL_HISTORICO, cat_tribunal)
    canal_regras     = _buscar_texto(CANAL_REGRAS, cat_tribunal)
    canal_ranking    = _buscar_texto(CANAL_RANKING, cat_tribunal)
    canal_casais     = _buscar_texto(CANAL_CASAIS, cat_tribunal)
    canal_casos      = _buscar_texto(CANAL_CASOS, cat_tribunal)
    canal_salao      = _buscar_texto(CANAL_SALAO, cat_tribunal)
    canal_admin      = _buscar_texto(CANAL_ADMIN, cat_tribunal)
    canal_entradas   = _buscar_texto(CANAL_ENTRADAS, cat_logs)
    canal_saidas     = _buscar_texto(CANAL_SAIDAS, cat_logs)
    chat_resenha     = _buscar_texto(CHAT_RESENHA, cat_calls)
    canal_comandos   = _buscar_texto(CANAL_COMANDOS_BOT, cat_calls)

    # Sincronizar topics
    print("\n[TOPICS]")
    await _sync_topic(canal_painel, "canal_painel")
    await _sync_topic(canal_historico, "canal_historico")
    await _sync_topic(canal_regras, "canal_regras")
    await _sync_topic(canal_ranking, "canal_ranking")
    await _sync_topic(canal_casais, "canal_casais")
    await _sync_topic(canal_casos, "canal_casos")
    await _sync_topic(canal_salao, "canal_salao")
    await _sync_topic(canal_admin, "canal_admin")
    await _sync_topic(canal_entradas, "canal_entradas")
    await _sync_topic(canal_saidas, "canal_saidas")
    await _sync_topic(chat_resenha, "chat_resenha")
    await _sync_topic(canal_comandos, "canal_comandos_bot")

    print(f"\n{'='*50}")
    print("  Setup concluido!")
    print(f"{'='*50}\n")

    return {
        "cargos": cargos,
        "cat_tribunal": cat_tribunal,
        "cat_casos": cat_casos,
        "canal_painel": canal_painel,
        "canal_historico": canal_historico,
        "canal_regras": canal_regras,
        "canal_ranking": canal_ranking,
        "canal_casais": canal_casais,
        "canal_casos": canal_casos,
        "canal_salao": canal_salao,
        "canal_admin": canal_admin,
        "cat_logs": cat_logs,
        "canal_entradas": canal_entradas,
        "canal_saidas": canal_saidas,
        "cat_calls": cat_calls,
        "chat_resenha": chat_resenha,
        "canal_comandos_bot": canal_comandos,
    }


# ==========================================================================
#  Embeds fixos nos canais (idempotente: limpa e reenvia)
# ==========================================================================
async def _limpar_bot_msgs(canal: discord.TextChannel, bot_user: discord.User):
    """Remove mensagens do bot no canal (para evitar duplicatas)."""
    async for msg in canal.history(limit=50):
        if msg.author.id == bot_user.id:
            try:
                await msg.delete()
            except discord.NotFound:
                pass


async def enviar_embeds_fixos(guild: discord.Guild, resultado: dict):
    """Envia embeds fixos em todos os canais que precisam."""
    from src.tribunal import PainelView, AdminView

    bot_user = guild.me

    # -- Painel de abertura de tribuna
    canal_painel = resultado["canal_painel"]
    if canal_painel:
        await _limpar_bot_msgs(canal_painel, bot_user)
        await canal_painel.send(embed=embed_painel(), view=PainelView())
        print(f"  [EMBED] Painel enviado em #{canal_painel.name}")

    # -- Regras do tribunal
    canal_regras = resultado["canal_regras"]
    if canal_regras:
        await _limpar_bot_msgs(canal_regras, bot_user)
        await canal_regras.send(embed=embed_regras())
        print(f"  [EMBED] Regras enviadas em #{canal_regras.name}")

    # -- Ranking
    from src.ranking import atualizar_ranking_canal
    await atualizar_ranking_canal(guild)
    print(f"  [EMBED] Ranking atualizado")

    # -- Casais (ranking + painel com botoes)
    from src.casais import atualizar_casais_canal
    await atualizar_casais_canal(guild)
    print(f"  [EMBED] Casais atualizado")

    # -- Painel admin
    canal_admin = resultado["canal_admin"]
    if canal_admin:
        await _limpar_bot_msgs(canal_admin, bot_user)
        await canal_admin.send(embed=embed_admin(), view=AdminView())
        print(f"  [EMBED] Admin enviado em #{canal_admin.name}")
