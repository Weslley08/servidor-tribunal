"""
Sistema de Tribunal -- Views, Modais e logica de tickets.

Tudo funciona por embeds e botoes, sem slash commands.

Fluxo:
  1. Membro clica "Abrir Tribuna" no painel
  2. Modal pede: reu, vitima, acusacao
  3. Bot cria canal de ticket na categoria "Casos Ativos"
  4. Ambas as partes registram provas (obrigatorio)
  5. Membros se voluntariam como Juiz, Advogado, Promotor via botoes
  6. Juiz da o veredito -> ranking atualizado, caso arquivado
  7. Painel admin permite acoes administrativas
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import discord
from discord import ui

from src.config import (
    CATEGORIA_CASOS_ATIVOS,
    CANAL_HISTORICO,
    CARGO_JUIZ,
    CARGO_ADVOGADO,
    CARGO_PROMOTOR,
    CARGO_REU,
    CARGO_VITIMA,
    EMOJI_JUIZ,
    EMOJI_ADVOGADO,
    EMOJI_PROMOTOR,
    EMOJI_ABRIR,
    EMOJI_FECHAR,
    EMOJI_VEREDITO,
    EMOJI_TRIBUNAL,
    EMOJI_PROVA,
)
from src.embeds import (
    embed_caso_aberto,
    embed_caso_atualizado,
    embed_prova,
    embed_veredito,
    embed_caso_fechado,
    embed_historico,
)
from src.casais import (
    SelecionarCasalView,
    buscar_casal_por_membro,
)

# -- Persistencia simples (JSON) -------------------------------------------
DATA_DIR = Path("data")
COUNTER_FILE = DATA_DIR / "counter.json"


def _carregar_contador() -> int:
    if COUNTER_FILE.exists():
        with open(COUNTER_FILE, "r") as f:
            return json.load(f).get("numero", 0)
    return 0


def _salvar_contador(n: int) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(COUNTER_FILE, "w") as f:
        json.dump({"numero": n}, f)


def proximo_numero() -> int:
    n = _carregar_contador() + 1
    _salvar_contador(n)
    return n


# -- Armazenamento em memoria dos casos ativos ----------------------------
# channel_id -> CasoData
casos_ativos: dict[int, CasoData] = {}


class CasoData:
    """Dados de um caso/ticket ativo."""

    def __init__(
        self,
        numero: int,
        autor_id: int,
        reu_id: int,
        vitima_id: int,
        acusacao: str,
        channel_id: int,
        message_id: int | None = None,
    ):
        self.numero = numero
        self.autor_id = autor_id
        self.reu_id = reu_id
        self.vitima_id = vitima_id
        self.acusacao = acusacao
        self.channel_id = channel_id
        self.message_id = message_id

        self.juiz_id: int | None = None
        self.advogado_id: int | None = None
        self.promotor_id: int | None = None

        # Provas: lista de dicts {autor_id, lado, tipo, descricao, link}
        self.provas: list[dict] = []

    @property
    def provas_acusacao(self) -> int:
        return sum(1 for p in self.provas if p["lado"] == "acusacao")

    @property
    def provas_defesa(self) -> int:
        return sum(1 for p in self.provas if p["lado"] == "defesa")

    def lado_do_membro(self, user_id: int) -> str | None:
        """Retorna 'acusacao' ou 'defesa' conforme o papel do membro."""
        if user_id in (self.vitima_id, self.promotor_id, self.autor_id):
            return "acusacao"
        if user_id in (self.reu_id, self.advogado_id):
            return "defesa"
        return None


# ==========================================================================
#  VIEW DO PAINEL (botao "Abrir Tribuna")
# ==========================================================================
EMOJI_CORACAO = "\u2764\ufe0f"  # ❤️
EMOJI_ALIANCA = "\U0001f48d"  # 💍


class PainelView(ui.View):
    """Botoes persistentes de abrir tribuna e registrar casal."""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Abrir Tribuna",
        style=discord.ButtonStyle.primary,
        emoji=EMOJI_ABRIR,
        custom_id="tribunal:abrir_tribuna",
        row=0,
    )
    async def abrir_tribuna(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AbrirTribunaModal())

    @ui.button(
        label="Registrar Casal",
        style=discord.ButtonStyle.success,
        emoji=EMOJI_CORACAO,
        custom_id="tribunal:registrar_casal",
        row=0,
    )
    async def registrar_casal(self, interaction: discord.Interaction, button: ui.Button):
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


# ==========================================================================
#  MODAL -- Abrir Tribuna
# ==========================================================================
class AbrirTribunaModal(ui.Modal, title="Abrir Tribuna"):
    reu_input = ui.TextInput(
        label="Quem e o reu? (nome ou @mencao)",
        placeholder="Ex: @Fulano",
        required=True,
        max_length=100,
    )

    vitima_input = ui.TextInput(
        label="Quem e a vitima? (nome ou @mencao)",
        placeholder="Ex: @Ciclana",
        required=True,
        max_length=100,
    )

    acusacao_input = ui.TextInput(
        label="Qual a acusacao?",
        style=discord.TextStyle.paragraph,
        placeholder="Descreva a acusacao com detalhes...",
        required=True,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "Erro: so funciona em servidores.", ephemeral=True
            )

        reu = await _resolver_membro(guild, self.reu_input.value.strip())
        vitima = await _resolver_membro(guild, self.vitima_input.value.strip())

        if reu is None:
            return await interaction.response.send_message(
                f"Nao encontrei o membro **{self.reu_input.value}** no servidor.",
                ephemeral=True,
            )
        if vitima is None:
            return await interaction.response.send_message(
                f"Nao encontrei o membro **{self.vitima_input.value}** no servidor.",
                ephemeral=True,
            )
        if reu.id == vitima.id:
            return await interaction.response.send_message(
                "O reu e a vitima nao podem ser a mesma pessoa!",
                ephemeral=True,
            )

        acusacao = self.acusacao_input.value.strip()
        numero = proximo_numero()
        autor = interaction.user

        # Criar canal do ticket
        cat_casos = discord.utils.get(guild.categories, name=CATEGORIA_CASOS_ATIVOS)
        if cat_casos is None:
            return await interaction.response.send_message(
                "Categoria de casos nao encontrada. Reinicie o bot.",
                ephemeral=True,
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_channels=True, manage_messages=True, embed_links=True,
            ),
            autor: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
            ),
            reu: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
            ),
            vitima: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
            ),
        }

        canal = await cat_casos.create_text_channel(
            name=f"\u2696\u2503\u1d04\u1d00\ua731\u1d0f-{numero:04d}",
            topic=f"Caso #{numero:04d} -- {reu.display_name} vs {vitima.display_name}",
            overwrites=overwrites,
            reason=f"Tribuna #{numero:04d} aberta por {autor}",
        )

        caso = CasoData(
            numero=numero, autor_id=autor.id, reu_id=reu.id,
            vitima_id=vitima.id, acusacao=acusacao, channel_id=canal.id,
        )

        # Atribuir cargos de reu e vitima
        await _atribuir_cargo(guild, reu, CARGO_REU)
        await _atribuir_cargo(guild, vitima, CARGO_VITIMA)

        # Enviar embed no canal do ticket
        embed = embed_caso_aberto(numero, autor, reu, vitima, acusacao)
        view = CasoView()
        msg = await canal.send(
            content=f"{reu.mention} {vitima.mention} -- Uma tribuna foi aberta!",
            embed=embed, view=view,
        )
        caso.message_id = msg.id
        casos_ativos[canal.id] = caso

        await interaction.response.send_message(
            f"Tribuna **#{numero:04d}** aberta! Veja em {canal.mention}",
            ephemeral=True,
        )


# ==========================================================================
#  VIEW DO CASO (botoes persistentes dentro do ticket)
# ==========================================================================
class CasoView(ui.View):
    """Botoes do caso. Persistente via custom_id fixo."""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Ser Juiz", style=discord.ButtonStyle.secondary,
        emoji=EMOJI_JUIZ, custom_id="caso:juiz", row=0,
    )
    async def btn_juiz(self, interaction: discord.Interaction, button: ui.Button):
        caso = _get_caso(interaction)
        if caso is None:
            return await interaction.response.send_message("Caso nao encontrado.", ephemeral=True)

        user = interaction.user
        if user.id in (caso.reu_id, caso.vitima_id):
            return await interaction.response.send_message(
                "Reu/Vitima nao pode ser Juiz!", ephemeral=True)
        if caso.juiz_id is not None:
            return await interaction.response.send_message(
                "Ja existe um Juiz neste caso.", ephemeral=True)

        caso.juiz_id = user.id
        await _atualizar_embed_caso(interaction, caso)
        await interaction.response.send_message(
            f"{user.mention} assumiu como **{CARGO_JUIZ}**!")
        await _atribuir_cargo(interaction.guild, user, CARGO_JUIZ)

    @ui.button(
        label="Ser Advogado (Reu)", style=discord.ButtonStyle.primary,
        emoji=EMOJI_ADVOGADO, custom_id="caso:advogado", row=0,
    )
    async def btn_advogado(self, interaction: discord.Interaction, button: ui.Button):
        caso = _get_caso(interaction)
        if caso is None:
            return await interaction.response.send_message("Caso nao encontrado.", ephemeral=True)

        user = interaction.user
        if user.id in (caso.reu_id, caso.vitima_id):
            return await interaction.response.send_message(
                "Reu/Vitima nao pode ser Advogado!", ephemeral=True)
        if caso.advogado_id is not None:
            return await interaction.response.send_message(
                "Ja existe um Advogado neste caso.", ephemeral=True)

        caso.advogado_id = user.id
        await interaction.channel.set_permissions(
            user, view_channel=True, send_messages=True, read_message_history=True)
        await _atualizar_embed_caso(interaction, caso)
        await interaction.response.send_message(
            f"{user.mention} assumiu como **{CARGO_ADVOGADO}**!")
        await _atribuir_cargo(interaction.guild, user, CARGO_ADVOGADO)

    @ui.button(
        label="Ser Promotor (Vitima)", style=discord.ButtonStyle.danger,
        emoji=EMOJI_PROMOTOR, custom_id="caso:promotor", row=0,
    )
    async def btn_promotor(self, interaction: discord.Interaction, button: ui.Button):
        caso = _get_caso(interaction)
        if caso is None:
            return await interaction.response.send_message("Caso nao encontrado.", ephemeral=True)

        user = interaction.user
        if user.id in (caso.reu_id, caso.vitima_id):
            return await interaction.response.send_message(
                "Reu/Vitima nao pode ser Promotor!", ephemeral=True)
        if caso.promotor_id is not None:
            return await interaction.response.send_message(
                "Ja existe um Promotor neste caso.", ephemeral=True)

        caso.promotor_id = user.id
        await interaction.channel.set_permissions(
            user, view_channel=True, send_messages=True, read_message_history=True)
        await _atualizar_embed_caso(interaction, caso)
        await interaction.response.send_message(
            f"{user.mention} assumiu como **{CARGO_PROMOTOR}**!")
        await _atribuir_cargo(interaction.guild, user, CARGO_PROMOTOR)

    @ui.button(
        label="Registrar Prova", style=discord.ButtonStyle.primary,
        emoji=EMOJI_PROVA, custom_id="caso:prova", row=1,
    )
    async def btn_prova(self, interaction: discord.Interaction, button: ui.Button):
        caso = _get_caso(interaction)
        if caso is None:
            return await interaction.response.send_message("Caso nao encontrado.", ephemeral=True)

        user = interaction.user
        lado = caso.lado_do_membro(user.id)
        if lado is None:
            return await interaction.response.send_message(
                "Somente envolvidos no caso (partes, advogado, promotor) podem registrar provas.",
                ephemeral=True,
            )

        await interaction.response.send_modal(ProvaModal(caso, lado))

    @ui.button(
        label="Dar Veredito", style=discord.ButtonStyle.success,
        emoji=EMOJI_VEREDITO, custom_id="caso:veredito", row=1,
    )
    async def btn_veredito(self, interaction: discord.Interaction, button: ui.Button):
        caso = _get_caso(interaction)
        if caso is None:
            return await interaction.response.send_message("Caso nao encontrado.", ephemeral=True)
        if caso.juiz_id is None:
            return await interaction.response.send_message(
                "Ainda nao ha Juiz designado!", ephemeral=True)
        if interaction.user.id != caso.juiz_id:
            return await interaction.response.send_message(
                "Somente o Juiz pode dar o veredito!", ephemeral=True)

        # Verificar provas de ambos os lados
        if caso.provas_acusacao == 0:
            return await interaction.response.send_message(
                f"{EMOJI_PROVA} A acusacao ainda nao apresentou provas. "
                "Ambas as partes devem registrar provas antes do veredito.",
                ephemeral=True,
            )
        if caso.provas_defesa == 0:
            return await interaction.response.send_message(
                f"{EMOJI_PROVA} A defesa ainda nao apresentou provas. "
                "Ambas as partes devem registrar provas antes do veredito.",
                ephemeral=True,
            )

        await interaction.response.send_modal(VereditoModal(caso))

    @ui.button(
        label="Fechar Caso", style=discord.ButtonStyle.secondary,
        emoji=EMOJI_FECHAR, custom_id="caso:fechar", row=1,
    )
    async def btn_fechar(self, interaction: discord.Interaction, button: ui.Button):
        caso = _get_caso(interaction)
        if caso is None:
            return await interaction.response.send_message("Caso nao encontrado.", ephemeral=True)

        user = interaction.user
        is_admin = user.guild_permissions.administrator
        is_juiz_cargo = discord.utils.get(user.roles, name=CARGO_JUIZ) is not None
        is_envolvido = user.id in (caso.autor_id, caso.juiz_id)

        if not (is_admin or is_juiz_cargo or is_envolvido):
            return await interaction.response.send_message(
                "Somente o autor, o Juiz do caso, quem tem cargo Juiz ou admin pode fechar.",
                ephemeral=True,
            )

        await interaction.response.send_modal(FecharCasoModal(caso))


# ==========================================================================
#  MODAL -- Registrar Prova
# ==========================================================================
class ProvaModal(ui.Modal, title="Registrar Prova"):
    def __init__(self, caso: CasoData, lado: str):
        super().__init__()
        self.caso = caso
        self.lado = lado

    tipo_input = ui.TextInput(
        label="Tipo da prova",
        placeholder="Ex: print, clip, audio, link, testemunho",
        required=True,
        max_length=50,
    )

    descricao_input = ui.TextInput(
        label="Descricao da prova",
        style=discord.TextStyle.paragraph,
        placeholder="Explique o que esta prova demonstra...",
        required=True,
        max_length=1000,
    )

    link_input = ui.TextInput(
        label="Link da evidencia (opcional)",
        placeholder="Ex: https://imgur.com/..., https://streamable.com/...",
        required=False,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        caso = self.caso
        tipo = self.tipo_input.value.strip()
        descricao = self.descricao_input.value.strip()
        link = self.link_input.value.strip() or None

        prova = {
            "autor_id": interaction.user.id,
            "lado": self.lado,
            "tipo": tipo,
            "descricao": descricao,
            "link": link,
        }
        caso.provas.append(prova)
        numero_prova = len(caso.provas)

        # Enviar embed da prova no canal
        ep = embed_prova(
            caso.numero, interaction.user, self.lado,
            tipo, descricao, link, numero_prova,
        )
        await interaction.response.send_message(embed=ep)

        # Atualizar embed principal com contagem de provas
        await _atualizar_embed_caso(interaction, caso)


# ==========================================================================
#  VIEW ADMIN -- so Juizes e admins
# ==========================================================================
class AdminView(ui.View):
    """Botoes administrativos persistentes."""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Reconfigurar Servidor", style=discord.ButtonStyle.primary,
        emoji=EMOJI_TRIBUNAL, custom_id="admin:reconfigurar", row=0,
    )
    async def btn_reconfigurar(self, interaction: discord.Interaction, button: ui.Button):
        if not _tem_permissao_admin(interaction):
            return await interaction.response.send_message(
                "Sem permissao.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        from src.setup import setup_servidor, enviar_embeds_fixos
        resultado = await setup_servidor(interaction.guild)
        await enviar_embeds_fixos(interaction.guild, resultado)
        await interaction.followup.send("Servidor reconfigurado!", ephemeral=True)

    @ui.button(
        label="Fechar Todos os Casos", style=discord.ButtonStyle.danger,
        emoji=EMOJI_FECHAR, custom_id="admin:fechar_todos", row=0,
    )
    async def btn_fechar_todos(self, interaction: discord.Interaction, button: ui.Button):
        if not _tem_permissao_admin(interaction):
            return await interaction.response.send_message(
                "Sem permissao.", ephemeral=True)

        if not casos_ativos:
            return await interaction.response.send_message(
                "Nenhum caso ativo no momento.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        fechados = 0

        for channel_id, caso in list(casos_ativos.items()):
            canal = guild.get_channel(channel_id)
            if canal:
                ef = embed_caso_fechado(caso.numero, "Fechamento administrativo", interaction.user)
                await canal.send(embed=ef)
                await _limpar_cargos_caso(guild, caso)
                await _arquivar_canal(canal, guild)
                fechados += 1
            casos_ativos.pop(channel_id, None)

        await interaction.followup.send(
            f"{fechados} caso(s) fechado(s).", ephemeral=True)

    @ui.button(
        label="Limpar Cargos", style=discord.ButtonStyle.secondary,
        emoji=EMOJI_VEREDITO, custom_id="admin:limpar_cargos", row=0,
    )
    async def btn_limpar_cargos(self, interaction: discord.Interaction, button: ui.Button):
        if not _tem_permissao_admin(interaction):
            return await interaction.response.send_message(
                "Sem permissao.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        cargos_nomes = [CARGO_JUIZ, CARGO_ADVOGADO, CARGO_PROMOTOR, CARGO_REU, CARGO_VITIMA]
        removidos = 0

        for nome in cargos_nomes:
            role = discord.utils.get(guild.roles, name=nome)
            if role:
                for member in role.members:
                    try:
                        await member.remove_roles(role, reason="Limpeza admin")
                        removidos += 1
                    except discord.Forbidden:
                        pass

        await interaction.followup.send(
            f"Cargos limpos! {removidos} atribuicao(oes) removida(s).", ephemeral=True)


# ==========================================================================
#  MODAL -- Veredito
# ==========================================================================
class VereditoModal(ui.Modal, title="Dar Veredito"):
    def __init__(self, caso: CasoData):
        super().__init__()
        self.caso = caso

    veredito_input = ui.TextInput(
        label="Culpado ou Inocente?",
        placeholder="Digite: culpado ou inocente",
        required=True, max_length=20,
    )

    justificativa_input = ui.TextInput(
        label="Justificativa do veredito",
        style=discord.TextStyle.paragraph,
        placeholder="Justifique sua decisao com base nas provas...",
        required=True, max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        caso = self.caso
        guild = interaction.guild
        veredito_raw = self.veredito_input.value.strip().lower()
        justificativa = self.justificativa_input.value.strip()

        if veredito_raw not in ("culpado", "inocente"):
            return await interaction.response.send_message(
                "Digite exatamente **culpado** ou **inocente**.", ephemeral=True)

        culpado = veredito_raw == "culpado"

        reu = guild.get_member(caso.reu_id)
        vitima = guild.get_member(caso.vitima_id)
        juiz = guild.get_member(caso.juiz_id)
        advogado = guild.get_member(caso.advogado_id) if caso.advogado_id else None
        promotor = guild.get_member(caso.promotor_id) if caso.promotor_id else None

        embed_v = embed_veredito(caso.numero, reu, vitima, juiz, culpado, justificativa)
        await interaction.response.send_message(embed=embed_v)

        # Registrar resultado no ranking
        from src.ranking import registrar_resultado, atualizar_ranking_canal
        if culpado:
            # Culpado: vitima vence, reu perde
            registrar_resultado(vencedor_id=caso.vitima_id, perdedor_id=caso.reu_id)
        else:
            # Inocente: reu vence, vitima perde
            registrar_resultado(vencedor_id=caso.reu_id, perdedor_id=caso.vitima_id)

        await _enviar_historico(
            guild, caso, reu, vitima, juiz, advogado, promotor,
            culpado, justificativa,
        )

        # Atualizar ranking no canal
        await atualizar_ranking_canal(guild)

        # Atualizar ranking de casais (se envolvidos sao casal)
        from src.casais import atualizar_casais_canal
        await atualizar_casais_canal(guild)

        await _limpar_cargos_caso(guild, caso)
        casos_ativos.pop(interaction.channel.id, None)

        await interaction.channel.send(
            f"{EMOJI_FECHAR} Caso encerrado. Canal sera arquivado em 60 segundos.")
        await _arquivar_canal(interaction.channel, guild)


# ==========================================================================
#  MODAL -- Fechar Caso (sem veredito)
# ==========================================================================
class FecharCasoModal(ui.Modal, title="Fechar Caso"):
    def __init__(self, caso: CasoData):
        super().__init__()
        self.caso = caso

    motivo_input = ui.TextInput(
        label="Motivo do fechamento",
        style=discord.TextStyle.paragraph,
        placeholder="Ex: Acordo entre as partes, caso sem fundamento...",
        required=True, max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        caso = self.caso
        guild = interaction.guild
        motivo = self.motivo_input.value.strip()

        embed_f = embed_caso_fechado(caso.numero, motivo, interaction.user)
        await interaction.response.send_message(embed=embed_f)

        reu = guild.get_member(caso.reu_id)
        vitima = guild.get_member(caso.vitima_id)
        juiz = guild.get_member(caso.juiz_id) if caso.juiz_id else "N/A"
        advogado = guild.get_member(caso.advogado_id) if caso.advogado_id else "N/A"
        promotor = guild.get_member(caso.promotor_id) if caso.promotor_id else "N/A"

        await _enviar_historico(
            guild, caso, reu, vitima, juiz, advogado, promotor,
            culpado=None, justificativa=motivo,
        )
        await _limpar_cargos_caso(guild, caso)
        casos_ativos.pop(interaction.channel.id, None)

        await interaction.channel.send(
            f"{EMOJI_FECHAR} Caso fechado. Canal sera arquivado em 60 segundos.")
        await _arquivar_canal(interaction.channel, guild)


# ==========================================================================
#  Helpers
# ==========================================================================
def _tem_permissao_admin(interaction: discord.Interaction) -> bool:
    """Verifica se o usuario e admin ou tem cargo Juiz."""
    user = interaction.user
    if user.guild_permissions.administrator:
        return True
    return discord.utils.get(user.roles, name=CARGO_JUIZ) is not None


async def _resolver_membro(guild: discord.Guild, texto: str) -> discord.Member | None:
    """Resolve membro por mencao, ID ou nome."""
    texto = texto.strip().strip("<@!>")

    if texto.isdigit():
        member = guild.get_member(int(texto))
        if member:
            return member
        try:
            return await guild.fetch_member(int(texto))
        except discord.NotFound:
            pass

    texto_lower = texto.lower()
    for member in guild.members:
        if (
            member.name.lower() == texto_lower
            or member.display_name.lower() == texto_lower
            or (member.global_name and member.global_name.lower() == texto_lower)
        ):
            return member
    return None


def _get_caso(interaction: discord.Interaction) -> CasoData | None:
    return casos_ativos.get(interaction.channel.id)


async def _atualizar_embed_caso(interaction: discord.Interaction, caso: CasoData) -> None:
    guild = interaction.guild
    reu = guild.get_member(caso.reu_id)
    vitima = guild.get_member(caso.vitima_id)
    juiz = guild.get_member(caso.juiz_id) if caso.juiz_id else None
    advogado = guild.get_member(caso.advogado_id) if caso.advogado_id else None
    promotor = guild.get_member(caso.promotor_id) if caso.promotor_id else None

    embed = embed_caso_atualizado(
        caso.numero, reu, vitima, caso.acusacao, juiz, advogado, promotor,
        provas_acusacao=caso.provas_acusacao, provas_defesa=caso.provas_defesa,
    )

    if caso.message_id:
        try:
            msg = await interaction.channel.fetch_message(caso.message_id)
            await msg.edit(embed=embed)
        except discord.NotFound:
            pass


async def _atribuir_cargo(guild: discord.Guild, member: discord.Member, cargo_nome: str) -> None:
    role = discord.utils.get(guild.roles, name=cargo_nome)
    if role and role not in member.roles:
        try:
            await member.add_roles(role, reason="Tribunal")
        except discord.Forbidden:
            print(f"[AVISO] Sem permissao para dar cargo {cargo_nome} a {member}")


async def _limpar_cargos_caso(guild: discord.Guild, caso: CasoData) -> None:
    mapeamento = {
        caso.juiz_id: CARGO_JUIZ,
        caso.advogado_id: CARGO_ADVOGADO,
        caso.promotor_id: CARGO_PROMOTOR,
        caso.reu_id: CARGO_REU,
        caso.vitima_id: CARGO_VITIMA,
    }

    for user_id, cargo_nome in mapeamento.items():
        if user_id is None:
            continue
        member = guild.get_member(user_id)
        role = discord.utils.get(guild.roles, name=cargo_nome)
        if member and role and role in member.roles:
            em_outro_caso = any(
                c for c in casos_ativos.values()
                if c.channel_id != caso.channel_id
                and user_id in (c.juiz_id, c.advogado_id, c.promotor_id, c.reu_id, c.vitima_id)
            )
            if not em_outro_caso:
                try:
                    await member.remove_roles(role, reason="Caso encerrado")
                except discord.Forbidden:
                    pass


async def _enviar_historico(
    guild: discord.Guild, caso: CasoData,
    reu, vitima, juiz, advogado, promotor,
    culpado: bool | None, justificativa: str,
) -> None:
    canal_hist = discord.utils.get(guild.text_channels, name=CANAL_HISTORICO)
    if canal_hist is None:
        print("[AVISO] Canal de historico nao encontrado.")
        return

    embed = embed_historico(
        caso.numero, reu, vitima, juiz, advogado, promotor,
        caso.acusacao, culpado, justificativa,
    )
    await canal_hist.send(embed=embed)


async def _arquivar_canal(channel: discord.TextChannel, guild: discord.Guild) -> None:
    await asyncio.sleep(60)

    overwrites = channel.overwrites
    for target in overwrites:
        if target != guild.me:
            overwrites[target] = discord.PermissionOverwrite(
                view_channel=True, send_messages=False, read_message_history=True,
            )

    # Troca icone de balanca para cadeado no nome do canal
    if "\u2696" in channel.name:
        novo_nome = channel.name.replace("\u2696", "\U0001f512", 1)
    else:
        novo_nome = f"\U0001f512\u2503{channel.name}"

    try:
        await channel.edit(
            overwrites=overwrites,
            name=novo_nome,
            reason="Caso encerrado -- arquivado",
        )
    except discord.Forbidden:
        print(f"[AVISO] Sem permissao para arquivar #{channel.name}")
