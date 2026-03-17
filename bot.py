import discord
from discord.ext import commands
from discord import app_commands
import os

TOKEN = os.getenv("TOKEN")

MAX_PLAYERS = 4

intents = discord.Intents.default()
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

active_recruits = {}


def count_members(channel):

    players = 0
    spectators = 0

    for member in channel.members:

        if "[📺관전중]" in member.display_name:
            spectators += 1
        else:
            players += 1

    return players, spectators


def make_bar(players):

    filled = "█" * players
    empty = "□" * (MAX_PLAYERS - players)

    return filled + empty


def get_color(remain):

    if remain <= 0:
        return 0xff0000

    elif remain == 1:
        return 0xffcc00

    else:
        return 0x00ff00


class Recruit(discord.ui.View):

    def __init__(self, channel, host):
        super().__init__(timeout=None)
        self.channel = channel
        self.host = host
        self.message = None

    async def update_embed(self):

        players, spectators = count_members(self.channel)

        remain = MAX_PLAYERS - players

        bar = make_bar(players)

        color = get_color(remain)

        embed = self.message.embeds[0]

        embed.color = color

        embed.description = f"""
👤 모집자 : {self.host.mention}
🔊 채널 : {self.channel.name}

👥 플레이어 : {players} / {MAX_PLAYERS}
📺 관전자 : {spectators}

{bar}

🪑 남은 자리 : {remain}
"""

        await self.message.edit(embed=embed, view=self)

        if players >= MAX_PLAYERS:
            await self.auto_close()

    async def auto_close(self):

        embed = self.message.embeds[0]
        embed.title = "🎮 PUBG 모집 종료"
        embed.color = 0xff0000

        for item in self.children:
            item.disabled = True

        await self.message.edit(embed=embed, view=self)

        if self.channel.id in active_recruits:
            del active_recruits[self.channel.id]

    @discord.ui.button(label="참가하기", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):

        invite = await self.channel.create_invite(max_age=300)

        await interaction.response.send_message(
            invite.url,
            ephemeral=True
        )

    @discord.ui.button(label="모집종료", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user != self.host:
            await interaction.response.send_message(
                "모집자만 종료할 수 있습니다.",
                ephemeral=True
            )
            return

        await self.auto_close()

        await interaction.response.defer()


@bot.event
async def on_ready():

    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)}개의 명령어 동기화 완료")
    except Exception as e:
        print(e)

    print("봇 준비 완료")


@bot.tree.command(name="구인", description="배그 구인")
@app_commands.describe(message="하고 싶은 말")
async def recruit(interaction: discord.Interaction, message: str):

    if not interaction.user.voice:
        await interaction.response.send_message(
            "먼저 음성채널에 들어가 주세요.",
            ephemeral=True
        )
        return

    voice_channel = interaction.user.voice.channel

    players, spectators = count_members(voice_channel)

    remain = MAX_PLAYERS - players

    bar = make_bar(players)

    color = get_color(remain)

    embed = discord.Embed(
        title="🎮 PUBG 구인",
        description=f"""
👤 모집자 : {interaction.user.mention}
🔊 채널 : {voice_channel.name}

👥 플레이어 : {players} / {MAX_PLAYERS}
📺 관전자 : {spectators}

{bar}

🪑 남은 자리 : {remain}

💬 {message}
""",
        color=color
    )

    view = Recruit(voice_channel, interaction.user)

    await interaction.response.send_message(embed=embed, view=view)

    msg = await interaction.original_response()

    view.message = msg

    active_recruits[voice_channel.id] = view


@bot.event
async def on_voice_state_update(member, before, after):

    channels = []

    if before.channel:
        channels.append(before.channel)

    if after.channel:
        channels.append(after.channel)

    for channel in channels:

        if channel.id in active_recruits:

            view = active_recruits[channel.id]

            if view.host not in channel.members:
                await view.auto_close()
                return

            await view.update_embed()


bot.run(TOKEN)
