"""Fabricas de Embeds para o Tribunal."""

from datetime import datetime, timezone, timedelta

import discord

from src.config import (
    COR_TRIBUNAL,
    COR_ABERTURA,
    COR_CULPADO,
    COR_INOCENTE,
    COR_INFO,
    COR_FECHAR,
    COR_ADMIN,
    EMOJI_TRIBUNAL,
    EMOJI_JUIZ,
    EMOJI_VEREDITO,
    EMOJI_CULPADO,
    EMOJI_INOCENTE,
    EMOJI_ABRIR,
    EMOJI_FECHAR,
    EMOJI_PROVA,
    CARGO_JUIZ,
    CARGO_ADVOGADO,
    CARGO_PROMOTOR,
    CARGO_REU,
    CARGO_VITIMA,
)

BRT = timezone(timedelta(hours=-3))


# ==========================================================================
#  Painel (canal abertura de tribuna)
# ==========================================================================
def embed_painel() -> discord.Embed:
    embed = discord.Embed(
        title=f"{EMOJI_TRIBUNAL} Tribunal",
        description=(
            "Aqui as partes resolvem seus conflitos perante o tribunal.\n"
            "Cada caso e julgado com base em **provas** apresentadas.\n\n"
            "**Como funciona:**\n"
            f"> {EMOJI_ABRIR} Clique em **Abrir Tribuna** abaixo\n"
            "> Preencha o formulario com a acusacao\n"
            "> Um canal privado sera criado para o julgamento\n"
            f"> {EMOJI_PROVA} Ambas as partes **devem apresentar provas**\n\n"
            "**Papeis do julgamento:**\n"
            f"> **{CARGO_JUIZ}** -- Conduz o processo e profere o veredito\n"
            f"> **{CARGO_ADVOGADO}** -- Defende o reu\n"
            f"> **{CARGO_PROMOTOR}** -- Acusa em nome da vitima\n\n"
            "*Voluntarios assumem papeis via botoes dentro do caso.*"
        ),
        color=COR_TRIBUNAL,
    )
    embed.set_footer(text="Tribunal // Apresente provas. Defenda sua honra.")
    return embed


# ==========================================================================
#  Regras
# ==========================================================================
def embed_regras() -> discord.Embed:
    embed = discord.Embed(
        title=f"{EMOJI_TRIBUNAL} Regras do Tribunal",
        description="As regras sao lei. Quem participa aceita cumpri-las.",
        color=COR_INFO,
    )
    embed.add_field(
        name="Artigo 1 -- Da Abertura",
        value=(
            "- Qualquer membro pode abrir uma tribuna.\n"
            "- O caso deve identificar um reu e uma vitima.\n"
            "- A acusacao deve ser descrita de forma clara e objetiva."
        ),
        inline=False,
    )
    embed.add_field(
        name="Artigo 2 -- Dos Papeis",
        value=(
            f"- **{CARGO_JUIZ}** -- Conduz o julgamento e da o veredito.\n"
            f"- **{CARGO_ADVOGADO}** -- Defende o reu com argumentos e provas.\n"
            f"- **{CARGO_PROMOTOR}** -- Acusa em favor da vitima.\n"
            "- Ninguem envolvido no caso pode assumir papel de juiz, advogado ou promotor."
        ),
        inline=False,
    )
    embed.add_field(
        name=f"Artigo 3 -- Das Provas {EMOJI_PROVA}",
        value=(
            "- **Ambas as partes devem apresentar provas** antes do veredito.\n"
            "- Provas aceitas: prints, clips, audios, links ou qualquer evidencia.\n"
            "- Use o botao **Registrar Prova** para anexar formalmente.\n"
            "- Sem provas de ambos os lados, o Juiz nao pode julgar."
        ),
        inline=False,
    )
    embed.add_field(
        name="Artigo 4 -- Do Veredito",
        value=(
            f"- {EMOJI_CULPADO} **Culpado** -- Reu condenado.\n"
            f"- {EMOJI_INOCENTE} **Inocente** -- Reu absolvido.\n"
            "- O veredito e final e ira para o ranking."
        ),
        inline=False,
    )
    embed.add_field(
        name="Artigo 5 -- Do Ranking",
        value=(
            "- Todo veredito alimenta o ranking de confrontos.\n"
            "- Culpado: vitima vence, reu perde.\n"
            "- Inocente: reu vence, vitima perde.\n"
            "- Confrontos diretos ficam registrados para sempre."
        ),
        inline=False,
    )
    embed.add_field(
        name="Artigo 6 -- Da Conduta",
        value=(
            "- Respeite os limites. Conflitos liricos, nao pessoais.\n"
            "- Sem ofensas reais, preconceito ou ataques pesados.\n"
            "- O Juiz tem autoridade para encerrar casos abusivos."
        ),
        inline=False,
    )
    embed.set_footer(text="Tribunal // Regimento Interno v2.0")
    return embed


# ==========================================================================
#  Admin -- so Juizes e admins
# ==========================================================================
def embed_admin() -> discord.Embed:
    embed = discord.Embed(
        title=f"{EMOJI_JUIZ} Painel Administrativo",
        description=(
            "Ferramentas exclusivas para **Juizes** e **Administradores**.\n\n"
            "**Acoes disponiveis:**\n"
            f"> {EMOJI_TRIBUNAL} **Reconfigurar** -- Recria cargos/canais que faltam\n"
            f"> {EMOJI_FECHAR} **Fechar Todos os Casos** -- Encerra todos os tickets abertos\n"
            f"> {EMOJI_VEREDITO} **Limpar Cargos** -- Remove cargos temporarios de todos\n"
        ),
        color=COR_ADMIN,
    )
    embed.set_footer(text="Acesso restrito ao cargo Juiz e Administradores")
    return embed


# ==========================================================================
#  Caso -- embeds dentro do ticket
# ==========================================================================
def embed_caso_aberto(
    numero: int,
    autor: discord.Member,
    reu: discord.Member,
    vitima: discord.Member,
    acusacao: str,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"{EMOJI_TRIBUNAL} Caso #{numero:04d} -- Tribuna Aberta",
        description=f"**Acusacao:**\n>>> {acusacao}",
        color=COR_ABERTURA,
        timestamp=datetime.now(BRT),
    )
    embed.add_field(name="Aberto por", value=autor.mention, inline=True)
    embed.add_field(name=CARGO_REU, value=reu.mention, inline=True)
    embed.add_field(name=CARGO_VITIMA, value=vitima.mention, inline=True)
    embed.add_field(name=CARGO_JUIZ, value="*Aguardando...*", inline=True)
    embed.add_field(name=CARGO_ADVOGADO, value="*Aguardando...*", inline=True)
    embed.add_field(name=CARGO_PROMOTOR, value="*Aguardando...*", inline=True)
    embed.add_field(
        name=f"{EMOJI_PROVA} Provas",
        value="Acusacao: 0 | Defesa: 0",
        inline=False,
    )
    embed.set_footer(text="Apresente provas e assuma um papel usando os botoes.")
    return embed


def embed_caso_atualizado(
    numero: int,
    reu: discord.Member,
    vitima: discord.Member,
    acusacao: str,
    juiz: discord.Member | None,
    advogado: discord.Member | None,
    promotor: discord.Member | None,
    provas_acusacao: int = 0,
    provas_defesa: int = 0,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"{EMOJI_TRIBUNAL} Caso #{numero:04d}",
        description=f"**Acusacao:**\n>>> {acusacao}",
        color=COR_ABERTURA,
    )
    embed.add_field(name=CARGO_REU, value=reu.mention, inline=True)
    embed.add_field(name=CARGO_VITIMA, value=vitima.mention, inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(
        name=CARGO_JUIZ,
        value=juiz.mention if juiz else "*Aguardando...*",
        inline=True,
    )
    embed.add_field(
        name=CARGO_ADVOGADO,
        value=advogado.mention if advogado else "*Aguardando...*",
        inline=True,
    )
    embed.add_field(
        name=CARGO_PROMOTOR,
        value=promotor.mention if promotor else "*Aguardando...*",
        inline=True,
    )
    embed.add_field(
        name=f"{EMOJI_PROVA} Provas",
        value=f"Acusacao: {provas_acusacao} | Defesa: {provas_defesa}",
        inline=False,
    )

    if juiz and advogado and promotor and provas_acusacao > 0 and provas_defesa > 0:
        embed.set_footer(text=f"Tribunal pronto para o veredito. {EMOJI_VEREDITO}")
    elif provas_acusacao == 0 or provas_defesa == 0:
        embed.set_footer(text=f"Ambas as partes devem registrar provas. {EMOJI_PROVA}")
    else:
        embed.set_footer(text="Assuma um papel usando os botoes abaixo.")
    return embed


def embed_prova(
    numero_caso: int,
    autor: discord.Member,
    lado: str,
    tipo: str,
    descricao: str,
    link: str | None,
    numero_prova: int,
) -> discord.Embed:
    cor = COR_CULPADO if lado == "acusacao" else COR_ABERTURA
    titulo_lado = "Acusacao" if lado == "acusacao" else "Defesa"

    embed = discord.Embed(
        title=f"{EMOJI_PROVA} Prova #{numero_prova} -- {titulo_lado}",
        description=f"**Tipo:** {tipo}\n\n>>> {descricao}",
        color=cor,
        timestamp=datetime.now(BRT),
    )
    embed.add_field(name="Apresentada por", value=autor.mention, inline=True)
    embed.add_field(name="Caso", value=f"#{numero_caso:04d}", inline=True)

    if link:
        embed.add_field(name="Evidencia", value=f"[Abrir link]({link})", inline=False)

    embed.set_footer(text=f"Tribunal // Prova registrada formalmente")
    return embed


def embed_veredito(
    numero: int,
    reu: discord.Member,
    vitima: discord.Member,
    juiz: discord.Member,
    culpado: bool,
    justificativa: str,
) -> discord.Embed:
    if culpado:
        titulo = f"{EMOJI_CULPADO} CULPADO"
        cor = COR_CULPADO
        resultado = "O reu foi considerado **CULPADO**."
    else:
        titulo = f"{EMOJI_INOCENTE} INOCENTE"
        cor = COR_INOCENTE
        resultado = "O reu foi considerado **INOCENTE**."

    embed = discord.Embed(
        title=f"{EMOJI_VEREDITO} Caso #{numero:04d} -- {titulo}",
        description=f"{resultado}\n\n**Justificativa:**\n>>> {justificativa}",
        color=cor,
        timestamp=datetime.now(BRT),
    )
    embed.add_field(name=CARGO_REU, value=reu.mention, inline=True)
    embed.add_field(name=CARGO_VITIMA, value=vitima.mention, inline=True)
    embed.add_field(name=CARGO_JUIZ, value=juiz.mention, inline=True)
    embed.set_footer(text="Tribunal // Caso encerrado -- ranking atualizado")
    return embed


def embed_caso_fechado(numero: int, motivo: str, fechado_por: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title=f"{EMOJI_FECHAR} Caso #{numero:04d} -- Encerrado",
        description=f"**Motivo:** {motivo}",
        color=COR_FECHAR,
        timestamp=datetime.now(BRT),
    )
    embed.add_field(name="Fechado por", value=fechado_por.mention, inline=True)
    embed.set_footer(text="Tribunal // Caso arquivado sem veredito")
    return embed


def embed_historico(
    numero: int,
    reu: discord.Member | str,
    vitima: discord.Member | str,
    juiz: discord.Member | str,
    advogado: discord.Member | str,
    promotor: discord.Member | str,
    acusacao: str,
    culpado: bool | None,
    justificativa: str,
) -> discord.Embed:
    if culpado is None:
        cor = COR_FECHAR
        resultado = "Arquivado"
    elif culpado:
        cor = COR_CULPADO
        resultado = f"{EMOJI_CULPADO} Culpado"
    else:
        cor = COR_INOCENTE
        resultado = f"{EMOJI_INOCENTE} Inocente"

    _m = lambda x: x.mention if isinstance(x, discord.Member) else str(x)

    embed = discord.Embed(
        title=f"{EMOJI_TRIBUNAL} Caso #{numero:04d} -- {resultado}",
        description=f"**Acusacao:**\n>>> {acusacao}",
        color=cor,
        timestamp=datetime.now(BRT),
    )
    embed.add_field(name=CARGO_REU, value=_m(reu), inline=True)
    embed.add_field(name=CARGO_VITIMA, value=_m(vitima), inline=True)
    embed.add_field(name=CARGO_JUIZ, value=_m(juiz), inline=True)
    embed.add_field(name=CARGO_ADVOGADO, value=_m(advogado), inline=True)
    embed.add_field(name=CARGO_PROMOTOR, value=_m(promotor), inline=True)

    if justificativa:
        embed.add_field(name="Justificativa", value=justificativa[:1024], inline=False)

    embed.set_footer(text="Tribunal // Historico")
    return embed
