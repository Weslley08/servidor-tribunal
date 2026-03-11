"""
Sistema de Casais -- Registro de casais e ranking de relacionamentos.

Armazena casais registrados e cruza dados com o ranking do tribunal
para gerar estatisticas de cada casal.

Dados salvos em data/casais.json.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import discord
from discord import ui

from src.config import (
    COR_TRIBUNAL,
    COR_ABERTURA,
    COR_INFO,
    COR_CULPADO,
    COR_INOCENTE,
    EMOJI_TRIBUNAL,
    EMOJI_CULPADO,
    EMOJI_INOCENTE,
    CANAL_CASAIS,
    CATEGORIA_CASOS_ATIVOS,
)

BRT = timezone(timedelta(hours=-3))
EMOJI_CASAL = "\U0001f491"          # 💑
EMOJI_CORACAO = "\u2764\ufe0f"      # ❤️
EMOJI_QUEBRADO = "\U0001f494"       # 💔
EMOJI_ALIANCA = "\U0001f48d"        # 💍

DATA_DIR = Path("data")
CASAIS_FILE = DATA_DIR / "casais.json"


# ==========================================================================
#  I/O
# ==========================================================================
def _carregar() -> dict:
    if CASAIS_FILE.exists():
        try:
            with open(CASAIS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "casais" in data:
                return data
        except (json.JSONDecodeError, ValueError):
            print(f"[CASAIS] Arquivo {CASAIS_FILE} vazio ou corrompido — usando default.")
    return {"casais": []}


def _salvar(data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(CASAIS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ==========================================================================
#  Operacoes de registro
# ==========================================================================
def registrar_casal(membro1_id: int, membro2_id: int) -> bool:
    """Registra um casal. Retorna False se ja existe."""
    data = _carregar()

    # Verificar se ja existe
    for c in data["casais"]:
        par = {c["membro1_id"], c["membro2_id"]}
        if par == {membro1_id, membro2_id}:
            return False

    data["casais"].append({
        "membro1_id": membro1_id,
        "membro2_id": membro2_id,
        "registrado_em": datetime.now(BRT).isoformat(),
    })
    _salvar(data)
    return True


def remover_casal(membro1_id: int, membro2_id: int) -> bool:
    """Remove um casal. Retorna False se nao existia."""
    data = _carregar()
    par = {membro1_id, membro2_id}

    for i, c in enumerate(data["casais"]):
        if {c["membro1_id"], c["membro2_id"]} == par:
            data["casais"].pop(i)
            _salvar(data)
            return True
    return False


def obter_casais() -> list[dict]:
    """Retorna lista de todos os casais registrados."""
    return _carregar()["casais"]


def buscar_casal_por_membro(user_id: int) -> dict | None:
    """Retorna o casal em que o membro participa (ou None)."""
    for c in obter_casais():
        if user_id in (c["membro1_id"], c["membro2_id"]):
            return c
    return None


def parceiro_de(user_id: int) -> int | None:
    """Retorna o ID do parceiro(a), ou None se nao tem casal."""
    casal = buscar_casal_por_membro(user_id)
    if casal is None:
        return None
    if casal["membro1_id"] == user_id:
        return casal["membro2_id"]
    return casal["membro1_id"]


# ==========================================================================
#  Ranking de casais (cruza com dados do tribunal)
# ==========================================================================
def _obter_confronto_casal(membro1_id: int, membro2_id: int) -> dict:
    """Busca o confronto direto entre dois membros no ranking do tribunal."""
    from src.ranking import _carregar as carregar_ranking

    data = carregar_ranking()
    uid1 = str(membro1_id)
    uid2 = str(membro2_id)

    v1 = 0  # vitorias de membro1 contra membro2
    v2 = 0  # vitorias de membro2 contra membro1

    if uid1 in data.get("jogadores", {}):
        confrontos = data["jogadores"][uid1].get("confrontos", {})
        if uid2 in confrontos:
            v1 = confrontos[uid2].get("vitorias", 0)

    if uid2 in data.get("jogadores", {}):
        confrontos = data["jogadores"][uid2].get("confrontos", {})
        if uid1 in confrontos:
            v2 = confrontos[uid1].get("vitorias", 0)

    return {
        "membro1_vitorias": v1,
        "membro2_vitorias": v2,
        "total_casos": v1 + v2,
    }


def obter_ranking_casais() -> list[dict]:
    """Retorna casais ordenados por total de casos entre si."""
    casais = obter_casais()
    resultado = []

    for c in casais:
        confronto = _obter_confronto_casal(c["membro1_id"], c["membro2_id"])
        resultado.append({
            "membro1_id": c["membro1_id"],
            "membro2_id": c["membro2_id"],
            "registrado_em": c["registrado_em"],
            **confronto,
        })

    resultado.sort(key=lambda x: -x["total_casos"])
    return resultado


# ==========================================================================
#  Embeds
# ==========================================================================
def embed_painel_casais() -> discord.Embed:
    """Embed do painel de registro de casais."""
    embed = discord.Embed(
        title=f"{EMOJI_CASAL} Registro de Casais",
        description=(
            "Registre seu casal no tribunal!\n\n"
            "**O que o registro faz:**\n"
            f"> {EMOJI_ALIANCA} Oficializa o casal perante o tribunal\n"
            f"> {EMOJI_TRIBUNAL} Rastreia os conflitos entre voces\n"
            "> Mostra quem vence mais na relacao\n\n"
            "**Botoes:**\n"
            f"> {EMOJI_CORACAO} **Registrar Casal** -- Informe seu par\n"
            f"> {EMOJI_QUEBRADO} **Separar** -- Desfaz o registro\n"
        ),
        color=COR_TRIBUNAL,
    )
    embed.set_footer(text="Tribunal // Casais registrados")
    return embed


def embed_ranking_casais(guild: discord.Guild) -> discord.Embed:
    """Gera embed do ranking de casais."""
    ranking = obter_ranking_casais()

    embed = discord.Embed(
        title=f"{EMOJI_CASAL} Ranking de Casais",
        color=COR_INFO,
    )

    if not ranking:
        embed.description = "*Nenhum casal registrado ainda.*"
        return embed

    linhas = []
    for i, c in enumerate(ranking[:15], 1):
        m1 = guild.get_member(c["membro1_id"])
        m2 = guild.get_member(c["membro2_id"])
        n1 = m1.mention if m1 else f"<@{c['membro1_id']}>"
        n2 = m2.mention if m2 else f"<@{c['membro2_id']}>"

        medal = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}.get(i, f"**{i}.**")

        if c["total_casos"] == 0:
            placar = "*sem conflitos*"
        else:
            placar = f"**{c['membro1_vitorias']}** x **{c['membro2_vitorias']}**"

        linhas.append(f"{medal} {n1} {EMOJI_CORACAO} {n2} -- {placar}")

    embed.add_field(
        name=f"{EMOJI_ALIANCA} Casais Registrados",
        value="\n".join(linhas),
        inline=False,
    )

    # Status geral
    total = len(ranking)
    com_conflito = sum(1 for c in ranking if c["total_casos"] > 0)
    embed.add_field(
        name="Estatisticas",
        value=(
            f"Total de casais: **{total}**\n"
            f"Com conflitos: **{com_conflito}**\n"
            f"Em paz: **{total - com_conflito}**"
        ),
        inline=False,
    )

    embed.set_footer(text="Tribunal // Atualizado a cada veredito")
    return embed


def embed_casal_registrado(
    membro1: discord.Member, membro2: discord.Member,
) -> discord.Embed:
    """Embed de confirmacao de registro de casal."""
    embed = discord.Embed(
        title=f"{EMOJI_ALIANCA} Casal Registrado!",
        description=(
            f"{membro1.mention} {EMOJI_CORACAO} {membro2.mention}\n\n"
            "O casal foi oficializado perante o tribunal.\n"
            "Conflitos entre voces serao rastreados no ranking."
        ),
        color=COR_ABERTURA,
        timestamp=datetime.now(BRT),
    )
    embed.set_footer(text="Tribunal // Novo casal registrado")
    return embed


def embed_casal_separado(
    membro1: discord.Member | int, membro2: discord.Member | int,
) -> discord.Embed:
    """Embed de confirmacao de separacao."""
    _m = lambda x: x.mention if isinstance(x, discord.Member) else f"<@{x}>"
    embed = discord.Embed(
        title=f"{EMOJI_QUEBRADO} Casal Desfeito",
        description=(
            f"{_m(membro1)} e {_m(membro2)} se separaram.\n"
            "O registro foi removido, mas o historico permanece."
        ),
        color=COR_CULPADO,
        timestamp=datetime.now(BRT),
    )
    embed.set_footer(text="Tribunal // Registro removido")
    return embed


# -- Pedidos pendentes (channel_id -> PedidoData) -------------------------
pedidos_pendentes: dict[int, "PedidoData"] = {}


class PedidoData:
    """Dados de um pedido de casal pendente."""
    def __init__(self, membro1_id: int, membro2_id: int, channel_id: int):
        self.membro1_id = membro1_id
        self.membro2_id = membro2_id
        self.channel_id = channel_id
        self.aceitos: set[int] = set()  # IDs que aceitaram


# ==========================================================================
#  Views e Modais
# ==========================================================================
class SelecionarCasalView(ui.View):
    """View efemera com dropdown de membros para selecionar o casal."""

    def __init__(self):
        super().__init__(timeout=120)

    @ui.select(
        cls=ui.UserSelect,
        placeholder="Selecione os dois membros do casal",
        min_values=2,
        max_values=2,
    )
    async def selecionar(self, interaction: discord.Interaction, select: ui.UserSelect):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "Erro: so funciona em servidores.", ephemeral=True)

        membro1 = select.values[0]
        membro2 = select.values[1]

        # Validacoes
        if membro1.id == membro2.id:
            return await interaction.response.send_message(
                "Voce selecionou a mesma pessoa duas vezes!", ephemeral=True)
        if membro1.bot or membro2.bot:
            return await interaction.response.send_message(
                "Voce nao pode registrar um bot como casal!", ephemeral=True)

        # Verificar se algum ja esta em outro casal
        casal1 = buscar_casal_por_membro(membro1.id)
        if casal1 is not None:
            return await interaction.response.send_message(
                f"**{membro1.display_name}** ja esta em um casal! "
                "Precisa separar primeiro.", ephemeral=True)
        casal2 = buscar_casal_por_membro(membro2.id)
        if casal2 is not None:
            return await interaction.response.send_message(
                f"**{membro2.display_name}** ja esta em um casal! "
                "Precisa separar primeiro.", ephemeral=True)

        # Criar ticket de pedido
        cat_casos = discord.utils.get(guild.categories, name=CATEGORIA_CASOS_ATIVOS)
        if cat_casos is None:
            return await interaction.response.send_message(
                "Categoria de casos nao encontrada. Reinicie o bot.",
                ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_channels=True, manage_messages=True, embed_links=True,
            ),
            membro1: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
            ),
            membro2: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
            ),
        }

        canal = await cat_casos.create_text_channel(
            name=f"{EMOJI_ALIANCA}\u2503\u1d18\u1d07\u1d05\u026a\u1d05\u1d0f",  # 💍┃ᴘᴇᴅɪᴅᴏ
            topic=f"Pedido de casal: {membro1.display_name} e {membro2.display_name}",
            overwrites=overwrites,
            reason=f"Pedido de casal por {interaction.user}",
        )

        # Registrar pedido pendente
        pedido = PedidoData(membro1.id, membro2.id, canal.id)
        pedidos_pendentes[canal.id] = pedido

        # Enviar embed no ticket
        embed = discord.Embed(
            title=f"{EMOJI_ALIANCA} Pedido de Casal",
            description=(
                f"{membro1.mention} {EMOJI_CORACAO} {membro2.mention}\n\n"
                "**Ambos** precisam aceitar para oficializar o casal.\n"
                "Se qualquer um recusar, o pedido sera cancelado.\n\n"
                f"> {EMOJI_ALIANCA} Clique em **Aceitar** para confirmar\n"
                f"> {EMOJI_QUEBRADO} Clique em **Recusar** para negar"
            ),
            color=COR_ABERTURA,
            timestamp=datetime.now(BRT),
        )
        embed.set_footer(text="Tribunal // Aguardando confirmacao")

        await canal.send(
            content=f"{membro1.mention} {membro2.mention} -- Confirmem o pedido!",
            embed=embed,
            view=PedidoCasalView(),
        )

        await interaction.response.send_message(
            f"{EMOJI_ALIANCA} Pedido criado! Veja em {canal.mention}\n"
            "Ambos precisam aceitar para oficializar.",
            ephemeral=True,
        )

    async def on_timeout(self):
        pass


class PedidoCasalView(ui.View):
    """Botoes de Aceitar/Recusar no ticket de pedido de casal. Persistente."""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Aceitar",
        style=discord.ButtonStyle.success,
        emoji=EMOJI_CORACAO,
        custom_id="casais:aceitar_pedido",
        row=0,
    )
    async def btn_aceitar(self, interaction: discord.Interaction, button: ui.Button):
        pedido = pedidos_pendentes.get(interaction.channel_id)
        if pedido is None:
            return await interaction.response.send_message(
                "Pedido nao encontrado ou ja finalizado.", ephemeral=True)

        user = interaction.user
        if user.id not in (pedido.membro1_id, pedido.membro2_id):
            return await interaction.response.send_message(
                "Apenas os membros do casal podem aceitar!", ephemeral=True)

        if user.id in pedido.aceitos:
            return await interaction.response.send_message(
                "Voce ja aceitou! Aguardando o outro.", ephemeral=True)

        pedido.aceitos.add(user.id)
        await interaction.response.send_message(
            f"{EMOJI_CORACAO} {user.mention} aceitou o pedido!")

        # Verificar se ambos aceitaram
        if pedido.membro1_id in pedido.aceitos and pedido.membro2_id in pedido.aceitos:
            guild = interaction.guild

            ok = registrar_casal(pedido.membro1_id, pedido.membro2_id)
            if not ok:
                await interaction.channel.send("Esse casal ja esta registrado!")
            else:
                m1 = guild.get_member(pedido.membro1_id)
                m2 = guild.get_member(pedido.membro2_id)
                embed = embed_casal_registrado(m1, m2)
                await interaction.channel.send(
                    content=f"{EMOJI_ALIANCA} **Casal oficializado!**",
                    embed=embed,
                )
                await atualizar_casais_canal(guild)

            # Limpar e deletar canal apos 10s
            del pedidos_pendentes[interaction.channel_id]
            await interaction.channel.send(
                "*Este canal sera fechado em 10 segundos...*")
            await asyncio.sleep(10)
            try:
                await interaction.channel.delete(reason="Pedido de casal finalizado")
            except discord.NotFound:
                pass

    @ui.button(
        label="Recusar",
        style=discord.ButtonStyle.danger,
        emoji=EMOJI_QUEBRADO,
        custom_id="casais:recusar_pedido",
        row=0,
    )
    async def btn_recusar(self, interaction: discord.Interaction, button: ui.Button):
        pedido = pedidos_pendentes.get(interaction.channel_id)
        if pedido is None:
            return await interaction.response.send_message(
                "Pedido nao encontrado ou ja finalizado.", ephemeral=True)

        user = interaction.user
        if user.id not in (pedido.membro1_id, pedido.membro2_id):
            return await interaction.response.send_message(
                "Apenas os membros do casal podem recusar!", ephemeral=True)

        await interaction.response.send_message(
            f"{EMOJI_QUEBRADO} {user.mention} recusou o pedido. Casal **nao** registrado.")

        # Limpar e deletar canal apos 10s
        if interaction.channel_id in pedidos_pendentes:
            del pedidos_pendentes[interaction.channel_id]
        await interaction.channel.send(
            "*Este canal sera fechado em 10 segundos...*")
        await asyncio.sleep(10)
        try:
            await interaction.channel.delete(reason="Pedido de casal recusado")
        except discord.NotFound:
            pass  # view efemera, nada a fazer


class CasaisView(ui.View):
    """Botoes persistentes no canal de casais."""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Registrar Casal",
        style=discord.ButtonStyle.success,
        emoji=EMOJI_CORACAO,
        custom_id="casais:registrar",
        row=0,
    )
    async def btn_registrar(self, interaction: discord.Interaction, button: ui.Button):
        # Verificar se quem clicou ja tem casal
        casal = buscar_casal_por_membro(interaction.user.id)
        if casal is not None:
            parceiro_id = (
                casal["membro2_id"] if casal["membro1_id"] == interaction.user.id
                else casal["membro1_id"]
            )
            return await interaction.response.send_message(
                f"Voce ja esta em um casal com <@{parceiro_id}>! "
                "Separe-se primeiro antes de registrar outro.",
                ephemeral=True,
            )
        await interaction.response.send_message(
            f"{EMOJI_ALIANCA} Selecione os **dois membros** do casal:",
            view=SelecionarCasalView(),
            ephemeral=True,
        )

    @ui.button(
        label="Separar",
        style=discord.ButtonStyle.danger,
        emoji=EMOJI_QUEBRADO,
        custom_id="casais:separar",
        row=0,
    )
    async def btn_separar(self, interaction: discord.Interaction, button: ui.Button):
        casal = buscar_casal_por_membro(interaction.user.id)
        if casal is None:
            return await interaction.response.send_message(
                "Voce nao esta registrado em nenhum casal.", ephemeral=True)

        parceiro_id = (
            casal["membro2_id"] if casal["membro1_id"] == interaction.user.id
            else casal["membro1_id"]
        )
        guild = interaction.guild
        parceiro = guild.get_member(parceiro_id)
        nome_parceiro = parceiro.display_name if parceiro else f"<@{parceiro_id}>"

        embed_conf = discord.Embed(
            title=f"{EMOJI_QUEBRADO} Confirmar Separacao",
            description=(
                f"Voce quer se separar de **{nome_parceiro}**?\n\n"
                "O registro do casal sera removido, mas o historico permanece.\n"
                "Essa acao e **irreversivel**."
            ),
            color=0xE74C3C,
        )
        await interaction.response.send_message(
            embed=embed_conf,
            view=ConfirmarSeparacaoView(
                interaction.user.id,
                casal["membro1_id"], casal["membro2_id"],
                parceiro_id,
            ),
            ephemeral=True,
        )


class ConfirmarSeparacaoView(ui.View):
    """Confirmacao antes de separar o casal."""

    def __init__(self, user_id: int, membro1_id: int, membro2_id: int, parceiro_id: int):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.membro1_id = membro1_id
        self.membro2_id = membro2_id
        self.parceiro_id = parceiro_id

    @ui.button(
        label="Sim, Separar",
        style=discord.ButtonStyle.danger,
        emoji=EMOJI_QUEBRADO,
        row=0,
    )
    async def btn_confirmar(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "Somente quem iniciou pode confirmar.", ephemeral=True)

        remover_casal(self.membro1_id, self.membro2_id)

        guild = interaction.guild
        parceiro = guild.get_member(self.parceiro_id)
        embed = embed_casal_separado(interaction.user, parceiro or self.parceiro_id)
        await interaction.response.edit_message(embed=embed, view=None)

        await atualizar_casais_canal(guild)

    @ui.button(
        label="Cancelar",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def btn_cancelar(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content="Separacao cancelada.", embed=None, view=None,
        )
        self.stop()

    async def on_timeout(self):
        pass


async def atualizar_casais_canal(guild: discord.Guild) -> None:
    """Reenvia os embeds no canal de casais (ranking + botoes)."""
    canal = discord.utils.get(guild.text_channels, name=CANAL_CASAIS)
    if canal is None:
        print("[AVISO] Canal de casais nao encontrado.")
        return

    # Limpar mensagens antigas do bot
    async for msg in canal.history(limit=50):
        if msg.author.id == guild.me.id:
            try:
                await msg.delete()
            except discord.NotFound:
                pass

    # Enviar ranking e painel com botoes de registrar/separar
    await canal.send(embed=embed_painel_casais(), view=CasaisView())
    await canal.send(embed=embed_ranking_casais(guild))
