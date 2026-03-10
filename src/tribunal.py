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
    CANAL_CASOS,
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
    EMOJI_CULPADO,
    EMOJI_INOCENTE,
    COR_TRIBUNAL,
    COR_CULPADO,
    COR_INOCENTE,
    COR_ABERTURA,
    COR_FECHAR,
)
from src.embeds import (
    embed_caso_aberto,
    embed_caso_atualizado,
    embed_prova,
    embed_veredito,
    embed_caso_fechado,
    embed_historico,
    embed_resumo_caso,
    embed_resumo_caso_encerrado,
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
        self.resumo_msg_id: int | None = None  # msg no canal de casos

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
PENDENTE = "\u23f3"            # ⏳


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
        await interaction.response.send_message(
            f"{EMOJI_TRIBUNAL} **Abrir Tribuna** -- Selecione o **reu** e a **vitima** abaixo:",
            view=SelecionarPartesView(),
            ephemeral=True,
        )

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
#  SELECIONAR PARTES (dropdowns de usuario)
# ==========================================================================
class SelecionarPartesView(ui.View):
    """Dois dropdowns para selecionar reu e vitima, depois abre modal."""

    def __init__(self):
        super().__init__(timeout=120)
        self.reu: discord.Member | None = None
        self.vitima: discord.Member | None = None
        self._interaction_msg = None

    @ui.select(
        cls=ui.UserSelect,
        placeholder="Selecione o reu...",
        min_values=1, max_values=1,
        row=0,
    )
    async def select_reu(self, interaction: discord.Interaction, select: ui.UserSelect):
        self.reu = select.values[0]
        if self.vitima is not None:
            return await self._abrir_modal(interaction)
        await interaction.response.send_message(
            f"\u2705 Reu: {self.reu.mention}\n{PENDENTE} Agora selecione a **vitima** no menu acima.",
            ephemeral=True,
        )

    @ui.select(
        cls=ui.UserSelect,
        placeholder="Selecione a vitima...",
        min_values=1, max_values=1,
        row=1,
    )
    async def select_vitima(self, interaction: discord.Interaction, select: ui.UserSelect):
        self.vitima = select.values[0]
        if self.reu is not None:
            return await self._abrir_modal(interaction)
        await interaction.response.send_message(
            f"\u2705 Vitima: {self.vitima.mention}\n{PENDENTE} Agora selecione o **reu** no menu acima.",
            ephemeral=True,
        )

    async def _abrir_modal(self, interaction: discord.Interaction):
        if self.reu.id == self.vitima.id:
            return await interaction.response.send_message(
                "\u274c O reu e a vitima nao podem ser a mesma pessoa!",
                ephemeral=True,
            )
        if self.reu.bot or self.vitima.bot:
            return await interaction.response.send_message(
                "\u274c Bots nao podem ser reu ou vitima!",
                ephemeral=True,
            )
        if self.reu.id == interaction.user.id or self.vitima.id == interaction.user.id:
            pass  # Permitido: usuario pode abrir tribuna contra si ou envolvendo a si
        await interaction.response.send_modal(
            AcusacaoModal(reu=self.reu, vitima=self.vitima)
        )
        self.stop()

    async def on_timeout(self):
        pass


# ==========================================================================
#  MODAL -- Acusacao (motivo da abertura)
# ==========================================================================
class AcusacaoModal(ui.Modal, title="Abrir Tribuna"):
    acusacao_input = ui.TextInput(
        label="Qual a acusacao?",
        style=discord.TextStyle.paragraph,
        placeholder="Descreva a acusacao com detalhes...",
        required=True,
        max_length=1000,
    )

    def __init__(self, reu: discord.Member, vitima: discord.Member):
        super().__init__()
        self.reu = reu
        self.vitima = vitima

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "Erro: so funciona em servidores.", ephemeral=True
            )

        reu = self.reu
        vitima = self.vitima
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
            content=(
                f"{EMOJI_TRIBUNAL} **Tribuna aberta!**\n"
                f"{reu.mention} {vitima.mention} -- leiam o caso abaixo e apresentem suas provas."
            ),
            embed=embed, view=view,
        )
        caso.message_id = msg.id
        casos_ativos[canal.id] = caso

        # Publicar resumo no canal de casos em andamento
        canal_casos = discord.utils.get(guild.text_channels, name=CANAL_CASOS)
        if canal_casos:
            resumo_embed = embed_resumo_caso(
                numero, reu, vitima, acusacao, canal,
            )
            resumo_view = CasoPublicoView(canal.id)
            resumo_msg = await canal_casos.send(embed=resumo_embed, view=resumo_view)
            caso.resumo_msg_id = resumo_msg.id

        await interaction.response.send_message(
            f"\u2705 Tribuna **#{numero:04d}** aberta com sucesso!\n"
            f"> {EMOJI_TRIBUNAL} Canal: {canal.mention}\n"
            f"> Reu: {reu.mention} | Vitima: {vitima.mention}",
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
                "\u274c Reu/Vitima nao pode ser Advogado!", ephemeral=True)
        if caso.advogado_id is not None:
            adv = interaction.guild.get_member(caso.advogado_id)
            nome = adv.display_name if adv else "Alguem"
            return await interaction.response.send_message(
                f"\u274c **{nome}** ja e o Advogado neste caso.", ephemeral=True)

        caso.advogado_id = user.id
        await interaction.channel.set_permissions(
            user, view_channel=True, send_messages=True, read_message_history=True)
        await _atualizar_embed_caso(interaction, caso)

        embed_role = discord.Embed(
            description=f"{EMOJI_ADVOGADO} {user.mention} assumiu como **{CARGO_ADVOGADO}** (defesa do reu)",
            color=COR_ABERTURA,
        )
        await interaction.response.send_message(embed=embed_role)
        await _atribuir_cargo(interaction.guild, user, CARGO_ADVOGADO)
        await _atualizar_resumo_caso(interaction.guild, caso)

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
                "\u274c Reu/Vitima nao pode ser Promotor!", ephemeral=True)
        if caso.promotor_id is not None:
            prom = interaction.guild.get_member(caso.promotor_id)
            nome = prom.display_name if prom else "Alguem"
            return await interaction.response.send_message(
                f"\u274c **{nome}** ja e o Promotor neste caso.", ephemeral=True)

        caso.promotor_id = user.id
        await interaction.channel.set_permissions(
            user, view_channel=True, send_messages=True, read_message_history=True)
        await _atualizar_embed_caso(interaction, caso)

        embed_role = discord.Embed(
            description=f"{EMOJI_PROMOTOR} {user.mention} assumiu como **{CARGO_PROMOTOR}** (acusacao pela vitima)",
            color=COR_CULPADO,
        )
        await interaction.response.send_message(embed=embed_role)
        await _atribuir_cargo(interaction.guild, user, CARGO_PROMOTOR)
        await _atualizar_resumo_caso(interaction.guild, caso)

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

        # O Juiz e um cargo fixo -- verificar se o usuario tem o cargo
        user = interaction.user
        tem_cargo_juiz = discord.utils.get(user.roles, name=CARGO_JUIZ) is not None
        if not tem_cargo_juiz and not user.guild_permissions.administrator:
            return await interaction.response.send_message(
                f"Somente quem tem o cargo **{CARGO_JUIZ}** pode dar o veredito!", ephemeral=True)

        # Verificar provas de ambos os lados
        if caso.provas_acusacao == 0:
            return await interaction.response.send_message(
                f"{EMOJI_PROVA} A **acusacao** ainda nao apresentou provas.\n"
                "Ambas as partes devem registrar provas antes do veredito.",
                ephemeral=True,
            )
        if caso.provas_defesa == 0:
            return await interaction.response.send_message(
                f"{EMOJI_PROVA} A **defesa** ainda nao apresentou provas.\n"
                "Ambas as partes devem registrar provas antes do veredito.",
                ephemeral=True,
            )

        guild = interaction.guild
        reu = guild.get_member(caso.reu_id)
        vitima = guild.get_member(caso.vitima_id)

        embed_escolha = discord.Embed(
            title=f"{EMOJI_VEREDITO} Dar Veredito -- Caso #{caso.numero:04d}",
            description=(
                f"**Reu:** {reu.mention}\n"
                f"**Vitima:** {vitima.mention}\n"
                f"**Provas:** {caso.provas_acusacao} acusacao | {caso.provas_defesa} defesa\n\n"
                "Escolha o resultado do julgamento:"
            ),
            color=COR_TRIBUNAL,
        )
        await interaction.response.send_message(
            embed=embed_escolha,
            view=EscolherVereditoView(caso),
            ephemeral=True,
        )

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
                "Somente o autor, quem tem cargo Juiz ou admin pode fechar.",
                ephemeral=True,
            )

        guild = interaction.guild
        reu = guild.get_member(caso.reu_id)
        vitima = guild.get_member(caso.vitima_id)

        embed_conf = discord.Embed(
            title=f"{EMOJI_FECHAR} Fechar Caso #{caso.numero:04d}?",
            description=(
                f"**Reu:** {reu.mention if reu else 'N/A'}\n"
                f"**Vitima:** {vitima.mention if vitima else 'N/A'}\n\n"
                "O caso sera encerrado **sem veredito** e o canal sera arquivado.\n"
                "Tem certeza?"
            ),
            color=COR_FECHAR,
        )
        await interaction.response.send_message(
            embed=embed_conf,
            view=ConfirmarFecharCasoView(caso, user.id),
            ephemeral=True,
        )


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

        total = len(casos_ativos)
        embed_conf = discord.Embed(
            title=f"{EMOJI_FECHAR} Confirmar Fechamento em Massa",
            description=(
                f"Voce esta prestes a fechar **{total} caso(s)** ativos.\n\n"
                "Essa acao e **irreversivel**. Todos os canais serao arquivados\n"
                "e nenhum veredito sera registrado.\n\n"
                "Tem certeza?"
            ),
            color=COR_FECHAR,
        )
        await interaction.response.send_message(
            embed=embed_conf,
            view=ConfirmarFecharTodosView(interaction.user.id),
            ephemeral=True,
        )

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
        cargos_nomes = [CARGO_ADVOGADO, CARGO_PROMOTOR, CARGO_REU, CARGO_VITIMA]  # Juiz e fixo
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
#  VIEW -- Confirmar Fechamento em Massa
# ==========================================================================
class ConfirmarFecharTodosView(ui.View):
    """Confirmacao antes de fechar todos os casos."""

    def __init__(self, admin_id: int):
        super().__init__(timeout=30)
        self.admin_id = admin_id

    @ui.button(
        label="Sim, Fechar Todos", style=discord.ButtonStyle.danger,
        emoji=EMOJI_FECHAR, row=0,
    )
    async def btn_confirmar(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.admin_id:
            return await interaction.response.send_message(
                "Somente quem iniciou pode confirmar.", ephemeral=True)

        await interaction.response.edit_message(
            content=f"{EMOJI_FECHAR} Fechando todos os casos...", embed=None, view=None,
        )
        guild = interaction.guild
        fechados = 0

        for channel_id, caso in list(casos_ativos.items()):
            canal = guild.get_channel(channel_id)
            if canal:
                ef = embed_caso_fechado(caso.numero, "Fechamento administrativo", interaction.user)
                await canal.send(embed=ef)
                await _limpar_cargos_caso(guild, caso)
                await _encerrar_resumo_caso(guild, caso)
                await _arquivar_canal(canal, guild)
                fechados += 1
            casos_ativos.pop(channel_id, None)

        await interaction.edit_original_response(
            content=f"{EMOJI_FECHAR} **{fechados} caso(s)** fechado(s) com sucesso.",
        )

    @ui.button(
        label="Cancelar", style=discord.ButtonStyle.secondary, row=0,
    )
    async def btn_cancelar(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content="Operacao cancelada.", embed=None, view=None,
        )
        self.stop()

    async def on_timeout(self):
        pass


# ==========================================================================
#  VIEW -- Confirmar Fechamento de Caso Individual
# ==========================================================================
class ConfirmarFecharCasoView(ui.View):
    """Confirmacao antes de fechar um caso individual."""

    def __init__(self, caso: CasoData, user_id: int):
        super().__init__(timeout=30)
        self.caso = caso
        self.user_id = user_id

    @ui.button(
        label="Sim, Fechar", style=discord.ButtonStyle.danger,
        emoji=EMOJI_FECHAR, row=0,
    )
    async def btn_confirmar(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "Somente quem iniciou pode confirmar.", ephemeral=True)
        await interaction.response.send_modal(FecharCasoModal(self.caso))
        self.stop()

    @ui.button(
        label="Cancelar", style=discord.ButtonStyle.secondary, row=0,
    )
    async def btn_cancelar(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content="Fechamento cancelado.", embed=None, view=None,
        )
        self.stop()

    async def on_timeout(self):
        pass


# ==========================================================================
#  VIEW -- Escolher Veredito (Culpado ou Inocente via botoes)
# ==========================================================================
class EscolherVereditoView(ui.View):
    """Botoes de Culpado / Inocente. Apos clicar, abre modal de justificativa."""

    def __init__(self, caso: CasoData):
        super().__init__(timeout=120)
        self.caso = caso

    @ui.button(
        label="Culpado", style=discord.ButtonStyle.danger,
        emoji=EMOJI_CULPADO, row=0,
    )
    async def btn_culpado(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(
            JustificativaVereditoModal(self.caso, culpado=True)
        )
        self.stop()

    @ui.button(
        label="Inocente", style=discord.ButtonStyle.success,
        emoji=EMOJI_INOCENTE, row=0,
    )
    async def btn_inocente(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(
            JustificativaVereditoModal(self.caso, culpado=False)
        )
        self.stop()

    @ui.button(
        label="Cancelar", style=discord.ButtonStyle.secondary,
        emoji=EMOJI_FECHAR, row=0,
    )
    async def btn_cancelar(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content=f"{EMOJI_FECHAR} Veredito cancelado.", view=None, embed=None,
        )
        self.stop()

    async def on_timeout(self):
        pass


# ==========================================================================
#  MODAL -- Justificativa do Veredito
# ==========================================================================
class JustificativaVereditoModal(ui.Modal, title="Justificativa do Veredito"):
    def __init__(self, caso: CasoData, culpado: bool):
        super().__init__()
        self.caso = caso
        self.culpado = culpado

    justificativa_input = ui.TextInput(
        label="Justifique sua decisao",
        style=discord.TextStyle.paragraph,
        placeholder="Justifique com base nas provas apresentadas...",
        required=True, max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        caso = self.caso
        guild = interaction.guild
        justificativa = self.justificativa_input.value.strip()
        culpado = self.culpado

        reu = guild.get_member(caso.reu_id)
        vitima = guild.get_member(caso.vitima_id)

        # Mostrar confirmacao antes de finalizar
        resultado_txt = f"{EMOJI_CULPADO} **CULPADO**" if culpado else f"{EMOJI_INOCENTE} **INOCENTE**"
        embed_conf = discord.Embed(
            title=f"{EMOJI_VEREDITO} Confirmar Veredito -- Caso #{caso.numero:04d}",
            description=(
                f"**Resultado:** {resultado_txt}\n\n"
                f"**Reu:** {reu.mention}\n"
                f"**Vitima:** {vitima.mention}\n\n"
                f"**Justificativa:**\n>>> {justificativa}"
            ),
            color=COR_CULPADO if culpado else COR_INOCENTE,
        )
        embed_conf.set_footer(text="Essa acao e irreversivel. O caso sera encerrado.")

        await interaction.response.send_message(
            embed=embed_conf,
            view=ConfirmarVereditoView(caso, culpado, justificativa),
            ephemeral=True,
        )


# ==========================================================================
#  VIEW -- Confirmacao do Veredito
# ==========================================================================
class ConfirmarVereditoView(ui.View):
    """Confirmacao final antes de aplicar o veredito."""

    def __init__(self, caso: CasoData, culpado: bool, justificativa: str):
        super().__init__(timeout=60)
        self.caso = caso
        self.culpado = culpado
        self.justificativa = justificativa

    @ui.button(
        label="Confirmar Veredito", style=discord.ButtonStyle.danger,
        emoji=EMOJI_VEREDITO, row=0,
    )
    async def btn_confirmar(self, interaction: discord.Interaction, button: ui.Button):
        caso = self.caso
        guild = interaction.guild
        culpado = self.culpado
        justificativa = self.justificativa

        # Registrar quem deu o veredito como juiz do caso
        caso.juiz_id = interaction.user.id

        reu = guild.get_member(caso.reu_id)
        vitima = guild.get_member(caso.vitima_id)
        juiz = interaction.user
        advogado = guild.get_member(caso.advogado_id) if caso.advogado_id else None
        promotor = guild.get_member(caso.promotor_id) if caso.promotor_id else None

        # Fechar a mensagem efemera de confirmacao
        await interaction.response.edit_message(
            content=f"{EMOJI_VEREDITO} Veredito aplicado!",
            embed=None, view=None,
        )

        # Enviar veredito no canal do caso
        canal = guild.get_channel(caso.channel_id)
        if canal:
            embed_v = embed_veredito(caso.numero, reu, vitima, juiz, culpado, justificativa)
            await canal.send(embed=embed_v)

        # Registrar resultado no ranking
        from src.ranking import registrar_resultado, atualizar_ranking_canal
        if culpado:
            registrar_resultado(vencedor_id=caso.vitima_id, perdedor_id=caso.reu_id)
        else:
            registrar_resultado(vencedor_id=caso.reu_id, perdedor_id=caso.vitima_id)

        await _enviar_historico(
            guild, caso, reu, vitima, juiz, advogado, promotor,
            culpado, justificativa,
        )

        await atualizar_ranking_canal(guild)

        from src.casais import atualizar_casais_canal
        await atualizar_casais_canal(guild)

        await _limpar_cargos_caso(guild, caso)
        await _encerrar_resumo_caso(guild, caso)
        casos_ativos.pop(caso.channel_id, None)

        if canal:
            await canal.send(
                f"{EMOJI_FECHAR} Caso encerrado. Canal sera arquivado em 60 segundos.")
            await _arquivar_canal(canal, guild)

    @ui.button(
        label="Cancelar", style=discord.ButtonStyle.secondary,
        emoji=EMOJI_FECHAR, row=0,
    )
    async def btn_cancelar(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content=f"{EMOJI_FECHAR} Veredito cancelado. Nada foi alterado.",
            embed=None, view=None,
        )
        self.stop()

    async def on_timeout(self):
        pass


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
        await _encerrar_resumo_caso(guild, caso)
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

    # Notificar quando caso fica pronto para veredito
    pronto = (
        advogado is not None
        and promotor is not None
        and caso.provas_acusacao > 0
        and caso.provas_defesa > 0
    )
    if pronto and not getattr(caso, '_notificado_pronto', False):
        caso._notificado_pronto = True
        cargo_juiz = discord.utils.get(guild.roles, name=CARGO_JUIZ)
        mention_juiz = cargo_juiz.mention if cargo_juiz else f"**{CARGO_JUIZ}**"
        embed_pronto = discord.Embed(
            title=f"\u2705 Caso #{caso.numero:04d} -- Pronto para Veredito!",
            description=(
                f"Todas as condicoes foram atendidas:\n"
                f"> \u2705 Advogado: {advogado.mention}\n"
                f"> \u2705 Promotor: {promotor.mention}\n"
                f"> \u2705 Provas da acusacao: {caso.provas_acusacao}\n"
                f"> \u2705 Provas da defesa: {caso.provas_defesa}\n\n"
                f"{mention_juiz}, o caso aguarda seu veredito. "
                f"Use o botao **{EMOJI_VEREDITO} Dar Veredito**."
            ),
            color=COR_INOCENTE,
        )
        await interaction.channel.send(embed=embed_pronto)


async def _atribuir_cargo(guild: discord.Guild, member: discord.Member, cargo_nome: str) -> None:
    role = discord.utils.get(guild.roles, name=cargo_nome)
    if role and role not in member.roles:
        try:
            await member.add_roles(role, reason="Tribunal")
        except discord.Forbidden:
            print(f"[AVISO] Sem permissao para dar cargo {cargo_nome} a {member}")


async def _limpar_cargos_caso(guild: discord.Guild, caso: CasoData) -> None:
    # Juiz e cargo fixo, nao limpa
    mapeamento = {
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
        provas_acusacao=caso.provas_acusacao,
        provas_defesa=caso.provas_defesa,
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


# ==========================================================================
#  VIEW PUBLICA (botoes no canal de casos em andamento)
# ==========================================================================
class CasoPublicoView(ui.View):
    """Botoes de advogado/promotor no canal publico de casos."""

    def __init__(self, ticket_channel_id: int | None = None):
        super().__init__(timeout=None)
        self._ticket_channel_id = ticket_channel_id

    def _get_caso_por_ticket(self) -> CasoData | None:
        if self._ticket_channel_id:
            return casos_ativos.get(self._ticket_channel_id)
        return None

    @ui.button(
        label="Ser Advogado (Reu)", style=discord.ButtonStyle.primary,
        emoji=EMOJI_ADVOGADO, custom_id="publico:advogado", row=0,
    )
    async def btn_advogado_pub(self, interaction: discord.Interaction, button: ui.Button):
        caso = self._find_caso_from_message(interaction)
        if caso is None:
            return await interaction.response.send_message(
                "\u274c Caso nao encontrado ou ja encerrado.", ephemeral=True)

        user = interaction.user
        if user.id in (caso.reu_id, caso.vitima_id):
            return await interaction.response.send_message(
                "\u274c Reu/Vitima nao pode ser Advogado!", ephemeral=True)
        if caso.advogado_id is not None:
            adv = interaction.guild.get_member(caso.advogado_id)
            nome = adv.display_name if adv else "Alguem"
            return await interaction.response.send_message(
                f"\u274c **{nome}** ja e o Advogado neste caso.", ephemeral=True)

        guild = interaction.guild
        caso.advogado_id = user.id

        canal_ticket = guild.get_channel(caso.channel_id)
        if canal_ticket:
            await canal_ticket.set_permissions(
                user, view_channel=True, send_messages=True, read_message_history=True)

        await _atribuir_cargo(guild, user, CARGO_ADVOGADO)
        await _atualizar_resumo_caso(guild, caso)

        if caso.message_id and canal_ticket:
            await _atualizar_embed_caso_direto(guild, canal_ticket, caso)

        await interaction.response.send_message(
            f"\u2705 Voce agora e o **{CARGO_ADVOGADO}** no Caso #{caso.numero:04d}!\n"
            f"Acesse o canal do caso: {canal_ticket.mention if canal_ticket else 'N/A'}",
            ephemeral=True,
        )
        if canal_ticket:
            embed_vol = discord.Embed(
                description=f"{EMOJI_ADVOGADO} {user.mention} se voluntariou como **{CARGO_ADVOGADO}**",
                color=COR_ABERTURA,
            )
            await canal_ticket.send(embed=embed_vol)

    @ui.button(
        label="Ser Promotor (Vitima)", style=discord.ButtonStyle.danger,
        emoji=EMOJI_PROMOTOR, custom_id="publico:promotor", row=0,
    )
    async def btn_promotor_pub(self, interaction: discord.Interaction, button: ui.Button):
        caso = self._find_caso_from_message(interaction)
        if caso is None:
            return await interaction.response.send_message(
                "\u274c Caso nao encontrado ou ja encerrado.", ephemeral=True)

        user = interaction.user
        if user.id in (caso.reu_id, caso.vitima_id):
            return await interaction.response.send_message(
                "\u274c Reu/Vitima nao pode ser Promotor!", ephemeral=True)
        if caso.promotor_id is not None:
            prom = interaction.guild.get_member(caso.promotor_id)
            nome = prom.display_name if prom else "Alguem"
            return await interaction.response.send_message(
                f"\u274c **{nome}** ja e o Promotor neste caso.", ephemeral=True)

        guild = interaction.guild
        caso.promotor_id = user.id

        canal_ticket = guild.get_channel(caso.channel_id)
        if canal_ticket:
            await canal_ticket.set_permissions(
                user, view_channel=True, send_messages=True, read_message_history=True)

        await _atribuir_cargo(guild, user, CARGO_PROMOTOR)
        await _atualizar_resumo_caso(guild, caso)

        if caso.message_id and canal_ticket:
            await _atualizar_embed_caso_direto(guild, canal_ticket, caso)

        await interaction.response.send_message(
            f"\u2705 Voce agora e o **{CARGO_PROMOTOR}** no Caso #{caso.numero:04d}!\n"
            f"Acesse o canal do caso: {canal_ticket.mention if canal_ticket else 'N/A'}",
            ephemeral=True,
        )
        if canal_ticket:
            embed_vol = discord.Embed(
                description=f"{EMOJI_PROMOTOR} {user.mention} se voluntariou como **{CARGO_PROMOTOR}**",
                color=COR_CULPADO,
            )
            await canal_ticket.send(embed=embed_vol)

    def _find_caso_from_message(self, interaction: discord.Interaction) -> CasoData | None:
        """Encontra o caso associado a esta mensagem de resumo."""
        msg_id = interaction.message.id
        for caso in casos_ativos.values():
            if caso.resumo_msg_id == msg_id:
                return caso
        return None


# ==========================================================================
#  Helpers -- resumo publico
# ==========================================================================
async def _atualizar_resumo_caso(guild: discord.Guild, caso: CasoData) -> None:
    """Atualiza a mensagem de resumo no canal de casos."""
    if caso.resumo_msg_id is None:
        return

    canal_casos = discord.utils.get(guild.text_channels, name=CANAL_CASOS)
    if canal_casos is None:
        return

    reu = guild.get_member(caso.reu_id)
    vitima = guild.get_member(caso.vitima_id)
    advogado = guild.get_member(caso.advogado_id) if caso.advogado_id else None
    promotor = guild.get_member(caso.promotor_id) if caso.promotor_id else None
    canal_ticket = guild.get_channel(caso.channel_id)

    if not (reu and vitima and canal_ticket):
        return

    embed = embed_resumo_caso(
        caso.numero, reu, vitima, caso.acusacao, canal_ticket,
        advogado=advogado, promotor=promotor,
    )

    try:
        msg = await canal_casos.fetch_message(caso.resumo_msg_id)
        await msg.edit(embed=embed)
    except discord.NotFound:
        pass


async def _encerrar_resumo_caso(guild: discord.Guild, caso: CasoData) -> None:
    """Marca a mensagem de resumo como encerrada."""
    if caso.resumo_msg_id is None:
        return

    canal_casos = discord.utils.get(guild.text_channels, name=CANAL_CASOS)
    if canal_casos is None:
        return

    embed = embed_resumo_caso_encerrado(caso.numero)
    try:
        msg = await canal_casos.fetch_message(caso.resumo_msg_id)
        await msg.edit(embed=embed, view=None)
    except discord.NotFound:
        pass


async def _atualizar_embed_caso_direto(
    guild: discord.Guild, canal: discord.TextChannel, caso: CasoData,
) -> None:
    """Atualiza o embed do caso no canal do ticket (sem interaction)."""
    reu = guild.get_member(caso.reu_id)
    vitima = guild.get_member(caso.vitima_id)
    juiz = guild.get_member(caso.juiz_id) if caso.juiz_id else None
    advogado = guild.get_member(caso.advogado_id) if caso.advogado_id else None
    promotor = guild.get_member(caso.promotor_id) if caso.promotor_id else None

    embed = embed_caso_atualizado(
        caso.numero, reu, vitima, caso.acusacao, juiz, advogado, promotor,
        provas_acusacao=caso.provas_acusacao, provas_defesa=caso.provas_defesa,
    )

    try:
        msg = await canal.fetch_message(caso.message_id)
        await msg.edit(embed=embed)
    except discord.NotFound:
        pass
