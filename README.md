# ⚖️ Tribunal

Bot Discord para resolução de conflitos entre duas partes de forma lírica. Casos exigem apresentação de provas (prints, clips, etc.) de ambos os lados antes do veredito. Resultados alimentam um ranking persistente.

100% baseado em embeds, canais e botões — sem slash commands.

## 🚀 Como usar

1. **Configure o `.env`:**
   ```
   DISCORD_TOKEN=seu_bot_token_aqui
   GUILD_ID=id_do_servidor
   ```

2. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Rode o bot:**
   ```bash
   python main.py
   ```

4. **O bot configura tudo automaticamente ao iniciar** (cargos, categorias, canais e embeds).

## 📁 Estrutura criada no servidor

### Cargos
| Cargo | Descrição |
|-------|-----------|
| 👨‍⚖️ Juiz | Conduz o julgamento e dá o veredito |
| 🛡️ Advogado | Defende o réu |
| ⚔️ Promotor | Acusa a favor da vítima |
| ⚖️ Réu | O acusado |
| 💔 Vítima | Quem sofreu a ofensa |

### Categorias & Canais
```
⚖️┃ᴛʀɪʙᴜɴᴀʟ
  ├── 🏛️┃ᴘᴀɪɴᴇʟ          → Botão para abrir tribuna
  ├── 📋┃ʀᴇɢʀᴀꜱ           → Regras do tribunal (read-only)
  ├── 🏆┃ʀᴀɴᴋɪɴɢ          → Ranking de vitórias/derrotas (read-only)
  ├── 📜┃ʜɪꜱᴛᴏʀɪᴄᴏ        → Registro de casos julgados (read-only)
  ├── ☕┃ꜱᴀʟᴀᴏ             → Chat geral
  └── 🔒┃ᴀᴅᴍɪɴ            → Painel administrativo (Juízes/Admins)

📂┃ᴄᴀꜱᴏꜱ ᴀᴛɪᴠᴏꜱ
  └── ⚖┃ᴄᴀꜱᴏ-0001         → Canais de ticket (criados dinamicamente)
```

## ⚖️ Fluxo do Tribunal

1. Membro clica em **Abrir Tribuna** no painel
2. Preenche o formulário: réu, vítima e acusação
3. Um canal é criado na categoria **Casos Ativos**
4. Outros membros podem assumir papel de **Juiz**, **Advogado** ou **Promotor** via botões
5. Ambas as partes **registram provas** (obrigatório) — prints, clips, links, etc.
6. O Juiz dá o **veredito** (Culpado/Inocente) com justificativa baseada nas provas
7. O resultado é registrado no **ranking** e no **histórico**, e o canal é arquivado

## 🏆 Sistema de Ranking

- Cada veredito registra vitória/derrota para as partes
- **Culpado**: vítima vence, réu perde
- **Inocente**: réu vence, vítima perde
- O ranking exibe o leaderboard (ordenado por derrotas) e as maiores rivalidades
- Persistido em `data/ranking.json`

## 🛠️ Deploy (DisCloud)

O `discloud.config` já está configurado. Basta fazer upload da pasta no painel da DisCloud.
