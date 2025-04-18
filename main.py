import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import asyncio

intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.message_content = True
intents.guild_reactions = True
intents.members = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)
conn = sqlite3.connect("role_panels.db", check_same_thread=False, isolation_level=None)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS role_panels (
    channel_id INTEGER,
    message_id INTEGER PRIMARY KEY,
    title TEXT,
    color TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS role_reactions (
    message_id INTEGER,
    emoji TEXT,
    role_id INTEGER,
    PRIMARY KEY (message_id, emoji)
)
""")
conn.commit()
selected_panels = {}
db_lock = asyncio.Lock()
def get_default_emoji(index):
    emojis = ["🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭", "🇮", "🇯", "🇰", "🇱", "🇲", "🇳", "🇴", "🇵", "🇶", "🇷", "🇸", "🇹", "🇺", "🇻", "🇼", "🇽", "🇾", "🇿", "🔴", "🟠", "🟡", "🟢", "🔵", "🟣", "🟤", "⚫", "⚪", "🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛", "⬜", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    return emojis[index] if index < len(emojis) else "❓"

@bot.tree.command(name="rp_create", description="新しい役職パネルを作成")
@app_commands.default_permissions(manage_roles=True)
async def rp_create(interaction: discord.Interaction, role: discord.Role, title: str = "役職パネル", color: str = "#000000", emoji: str = "🇦"):
    embed = discord.Embed(title=title, color=int(color.strip("#"), 16))
    embed.add_field(name="", value=f"{emoji}:{role.mention}", inline=False)
    embed.set_footer(text="役職パネル")
    message = await interaction.channel.send(embed=embed)
    await message.add_reaction(emoji)
    c.execute("INSERT INTO role_panels (channel_id, message_id, title, color) VALUES (?, ?, ?, ?)",
              (interaction.channel_id, message.id, title, color))
    c.execute("INSERT INTO role_reactions (message_id, emoji, role_id) VALUES (?, ?, ?)",
              (message.id, emoji, role.id))
    conn.commit()
    await interaction.response.send_message("役職パネルを作成しました！", ephemeral=True)

@bot.tree.command(name="rp_add", description="役職パネルに役職を追加")
@app_commands.default_permissions(manage_roles=True)
async def rp_add(interaction: discord.Interaction, role: discord.Role, emoji: str = None):
    panel_id = selected_panels.get(interaction.user.id)
    if not panel_id:
        c.execute("SELECT message_id FROM role_panels WHERE channel_id = ? ORDER BY message_id DESC LIMIT 1", (interaction.channel_id,))
        result = c.fetchone()
        if result:
            panel_id = result[0]
        else:
            await interaction.response.send_message("このチャンネルには役職パネルがありません。", ephemeral=True)
            return
    
    message = await interaction.channel.fetch_message(int(panel_id))
    emoji = emoji if emoji else get_default_emoji(len(message.embeds[0].fields))
    embed = message.embeds[0]
    embed.add_field(name="", value=f"{emoji}:{role.mention}", inline=False)
    await message.edit(embed=embed)
    await message.add_reaction(emoji)
    async with db_lock:
        c.execute("INSERT INTO role_reactions (message_id, emoji, role_id) VALUES (?, ?, ?)", (message.id, emoji, role.id))
        conn.commit()
    await interaction.response.send_message("役職を追加しました！", ephemeral=True)

@bot.tree.command(name="rp_edit", description="パネルのタイトルや色を編集")
@app_commands.default_permissions(manage_roles=True)
async def rp_edit(interaction: discord.Interaction, title: str = None, color: str = None):
    panel_id = selected_panels.get(interaction.user.id)
    if not panel_id:
        await interaction.response.send_message("選択中のパネルがありません。", ephemeral=True)
        return
    
    message = await interaction.channel.fetch_message(int(panel_id))
    embed = message.embeds[0]
    if title:
        embed.title = title
        c.execute("UPDATE role_panels SET title = ? WHERE message_id = ?", (title, panel_id))
    if color:
        embed.color = int(color.strip("#"), 16)
        c.execute("UPDATE role_panels SET color = ? WHERE message_id = ?", (color, panel_id))
    
    await message.edit(embed=embed)
    conn.commit()
    await interaction.response.send_message("パネルを編集しました！", ephemeral=True)

@bot.tree.command(name="rp_reset", description="サーバーの役職パネルデータを完全にリセット")
@app_commands.default_permissions(administrator=True)
async def rp_reset(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("このコマンドはサーバー内でのみ使用できます。", ephemeral=True)
        return
    
    async with db_lock:
        channels = [channel.id for channel in interaction.guild.channels]
        c.execute("SELECT message_id FROM role_panels WHERE channel_id IN ({})".format(
            ','.join(['?']*len(channels))
        ), channels)
        message_ids = [row[0] for row in c.fetchall()]
        
        for message_id in message_ids:
            c.execute("DELETE FROM role_reactions WHERE message_id = ?", (message_id,))
        
        c.execute("DELETE FROM role_panels WHERE channel_id IN ({})".format(
            ','.join(['?']*len(channels))
        ), channels)
        conn.commit()
    
    selected_panels.clear()
    await interaction.response.send_message("このサーバーの役職パネルデータを完全にリセットしました。", ephemeral=True)


@bot.tree.command(name="rp_select", description="チャンネル内のパネルを選択")
@app_commands.default_permissions(manage_roles=True)
async def rp_select(interaction: discord.Interaction):
    c.execute("SELECT message_id, title FROM role_panels WHERE channel_id = ?", (interaction.channel_id,))
    panels = c.fetchall()
    if not panels:
        await interaction.response.send_message("このチャンネルにはパネルがありません。")
        return
    
    embed = discord.Embed(title="どのパネルを選択しますか？", color=0x303030)
    labels = ["🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭", "🇮", "🇯", "🇰", "🇱", "🇲", "🇳", "🇴", "🇵", "🇶", "🇷", "🇸", "🇹", "🇺", "🇻", "🇼", "🇽", "🇾", "🇿", "🔴", "🟠", "🟡", "🟢", "🔵", "🟣", "🟤", "⚫", "⚪", "🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛", "⬜", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for idx, (message_id, title) in enumerate(panels):
        link = f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{message_id}"
        label = labels[idx % len(labels)]
        embed.add_field(name="", value=f"{label}: {link}", inline=False)
    
    select = discord.ui.Select(placeholder="パネルを選択...")
    for idx, (message_id, title) in enumerate(panels):
        label = labels[idx % len(labels)]
        select.add_option(label=f"{label}: {title}", value=str(message_id))
    
    async def select_callback(interaction: discord.Interaction):
        selected_panels[interaction.user.id] = int(select.values[0])
        await interaction.response.send_message(
            f"以下のパネルを選択しました:\nhttps://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{select.values[0]}",
        )
    
    select.callback = select_callback
    view = discord.ui.View(timeout=None)
    view.add_item(select)
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="rp_selected", description="現在選択されているパネルを表示")
@app_commands.default_permissions(manage_roles=True)
async def rp_selected(interaction: discord.Interaction):
    panel_id = selected_panels.get(interaction.user.id)
    if not panel_id:
        await interaction.response.send_message("選択中のパネルがありません。")
        return
    
    await interaction.response.send_message(f"あなたは以下のパネルを選択しています:\nhttps://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{panel_id}")

@bot.tree.command(name="rp_delete", description="選択したパネルを削除")
@app_commands.default_permissions(manage_roles=True)
async def rp_delete(interaction: discord.Interaction):
    panel_id = selected_panels.get(interaction.user.id)
    if not panel_id:
        await interaction.response.send_message("選択中のパネルがありません。", ephemeral=True)
        return
    async with db_lock:
        c.execute("DELETE FROM role_panels WHERE message_id = ?", (panel_id,))
        c.execute("DELETE FROM role_reactions WHERE message_id = ?", (panel_id,))
        conn.commit()
    
    selected_panels.pop(interaction.user.id, None)
    await interaction.response.send_message("選択したパネルを削除しました。", ephemeral=True)

@bot.tree.command(name="rp_refresh", description="選択されたパネルのリアクションを付けなおす")
@app_commands.default_permissions(manage_roles=True)
async def rp_refresh(interaction: discord.Interaction):
    panel_id = selected_panels.get(interaction.user.id)
    if not panel_id:
        await interaction.response.send_message("選択中のパネルがありません。", ephemeral=True)
        return
    
    message = await interaction.channel.fetch_message(int(panel_id))
    c.execute("SELECT emoji FROM role_reactions WHERE message_id = ?", (panel_id,))
    emojis = [row[0] for row in c.fetchall()]
    
    for emoji in emojis:
        await message.add_reaction(emoji)
    
    await interaction.response.send_message("リアクションを更新しました！", ephemeral=True)

@bot.tree.command(name="rp_remove", description="選択されたパネルから役職を削除")
@app_commands.default_permissions(manage_roles=True)
async def rp_remove(interaction: discord.Interaction, roles: discord.Role):
    panel_id = selected_panels.get(interaction.user.id)
    if not panel_id:
        await interaction.response.send_message("選択中のパネルがありません。", ephemeral=True)
        return
    
    message = await interaction.channel.fetch_message(int(panel_id))
    embed = message.embeds[0]
    
    updated_fields = [field for field in embed.fields if not any(role.name == field.name for role in roles)]
    embed.clear_fields()
    for field in updated_fields:
        embed.add_field(name=field.name, value=field.value, inline=False)
    
    await message.edit(embed=embed)
    for role in roles:
        c.execute("DELETE FROM role_reactions WHERE message_id = ? AND role_id = ?", (panel_id, role.id))
    conn.commit()
    
    await interaction.response.send_message("指定した役職を削除しました。", ephemeral=True)

@bot.tree.command(name="rp_copy", description="選択されたパネルをコピー")
@app_commands.default_permissions(manage_roles=True)
async def rp_copy(interaction: discord.Interaction):
    panel_id = selected_panels.get(interaction.user.id)
    if not panel_id:
        await interaction.response.send_message("選択中のパネルがありません。")
        return
    
    message = await interaction.channel.fetch_message(int(panel_id))
    embed = message.embeds[0]
    new_message = await interaction.channel.send(embed=embed)
    c.execute("INSERT INTO role_panels (channel_id, message_id, title, color) VALUES (?, ?, ?, ?)",
        (interaction.channel_id, new_message.id, embed.title, "#000000"))
    c.execute("SELECT emoji, role_id FROM role_reactions WHERE message_id = ?", (panel_id,))
    reactions = c.fetchall()
    
    for emoji, role_id in reactions:
        await new_message.add_reaction(emoji)
        c.execute("INSERT INTO role_reactions (message_id, emoji, role_id) VALUES (?, ?, ?)",
                  (new_message.id, emoji, role_id))
    conn.commit()
    
    await interaction.response.send_message("パネルをコピーしました。")

@bot.tree.command(name="rp_debug", description="デバッグ情報を表示")
@app_commands.default_permissions(manage_roles=True)
async def rp_debug(interaction: discord.Interaction):
    permissions = interaction.channel.permissions_for(interaction.user)
    
    embed = discord.Embed(title="デバッグ情報", color=0x00ff00)
    embed.add_field(name="ギルドID", value=interaction.guild.id, inline=False)
    embed.add_field(name="チャンネルID", value=interaction.channel.id, inline=False)
    embed.add_field(name="ユーザーID", value=interaction.user.id, inline=False)
    embed.add_field(name="役職の管理があるか？", value='✅' if permissions.manage_roles else '❌', inline=False)
    
    permissions_info = [
        f"VIEW_CHANNEL: {'✅' if permissions.view_channel else '❌'}",
        f"SEND_MESSAGES: {'✅' if permissions.send_messages else '❌'}",
        f"EMBED_LINKS: {'✅' if permissions.embed_links else '❌'}",
        f"USE_EXTERNAL_EMOJIS: {'✅' if permissions.use_external_emojis else '❌'}",
        f"MANAGE_MESSAGES: {'✅' if permissions.manage_messages else '❌'}",
        f"READ_MESSAGE_HISTORY: {'✅' if permissions.read_message_history else '❌'}",
        f"ADD_REACTIONS: {'✅' if permissions.add_reactions else '❌'}"
    ]
    
    embed.add_field(name="チャンネル権限情報", value="\n".join(permissions_info), inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Sync failed: {e}")

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return
    
    c.execute("SELECT role_id FROM role_reactions WHERE message_id = ? AND emoji = ?", (payload.message_id, str(payload.emoji)))
    result = c.fetchone()
    if not result:
        return
    
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    role = guild.get_role(result[0])
    channel = bot.get_channel(payload.channel_id)
    
    if role in member.roles:
        await member.remove_roles(role)
        message = await channel.fetch_message(payload.message_id)
        await message.remove_reaction(payload.emoji, member)
        
        embed = discord.Embed(description=f"{role.mention}の役職を解除しました。", color=0x303030)
        msg = await channel.send(f"<@{payload.user_id}>", embed=embed)
        await asyncio.sleep(3)
        await msg.delete()
    else:
        await member.add_roles(role)
        message = await channel.fetch_message(payload.message_id)
        await message.remove_reaction(payload.emoji, member)
        embed = discord.Embed(description=f"{role.mention}の役職を付与しました。", color=0x303030)
        msg = await channel.send(f"<@{payload.user_id}>", embed=embed)
        await asyncio.sleep(3)
        await msg.delete()

bot.run("YOUR TOKEN")
