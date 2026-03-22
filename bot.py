import discord
from discord.ext import commands
from discord import app_commands
import os

TOKEN = os.getenv("TOKEN")

MAX_PLAYERS = 4
CHANNEL_ID = 1477735324582154342  # 구인 채널 고정

intents = discord.Intents.default()
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

active_recruits = {}


def count_members(channel):
    players = 0
    spectators = 0

    for member in channel.members:
        if member.bot:
            continue  # ✅ 봇 제외

        if "[📺관전중]" in member.display_name:
            spectators += 1
        else:
            players += 1

    return players, spectators


def make_bar(players):
    return "█" * players + "□" * (MAX_PLAYERS - players)


def get_color(remain):
    if remain <= 0:
        return 0xff0000
    elif remain == 1:
        return 0xffcc00
    else:
        return 0x00ff00


class Recruit(discord.ui.View):
    def __init__(self, channel, host, message_content):
        super().__init__(timeout=None)
        self.channel = channel
        self.host = host
        self.message = None
        self.message_content = message_content  # 원래 메시지 저장

    async def update_embed(self):
        print("📌 update_embed 실행됨")

        players, spectators = count_members(self.channel)
        remain = MAX_PLAYERS - players

        embed = self.message.embeds[0]
        embed.color = get_color(remain)

        embed.description = f"""
👤 모집자 : {self.host.mention}
🔊 채널 : {self.channel.name}

👥 플레이어 : {players} / {MAX_PLAYERS}
📺 관전자 : {spectators}

{make_bar(players)}

🪑 남은 자리 : {remain}

💬 {self.message_content}
"""

        await self.message.edit(embed=embed, view=self)

        if players >= MAX_PLAYERS:
            print("🔥 인원 다 참 → 자동 종료")
            await self.auto_close()

    async def auto_close(self):
        print("❌ auto_close 실행됨")

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
        await interaction.response.send_message(invite.url, ephemeral=True)

    @discord.ui.button(label="모집종료", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            await interaction.response.send_message("모집자만 종료 가능", ephemeral=True)
            return

        print("🛑 수동 종료 버튼 클릭")
        await self.auto_close()
        await interaction.response.defer()


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)}개 명령어 동기화 완료")
    except Exception as e:
        print(e)

    print("🤖 봇 준비 완료")


@bot.tree.command(name="구인", description="배그 구인")
@app_commands.describe(message="하고 싶은 말")
async def recruit(interaction: discord.Interaction, message: str):

    if interaction.channel.id != CHANNEL_ID:
        await interaction.response.send_message("구인 채널에서만 사용 가능합니다.", ephemeral=True)
        return

    if not interaction.user.voice:
        await interaction.response.send_message("음성채널 먼저 들어가세요", ephemeral=True)
        return

    voice_channel = interaction.user.voice.channel

    players, spectators = count_members(voice_channel)
    remain = MAX_PLAYERS - players

    embed = discord.Embed(
        title="🎮 PUBG 구인",
        description=f"""
👤 모집자 : {interaction.user.mention}
🔊 채널 : {voice_channel.name}

👥 플레이어 : {players} / {MAX_PLAYERS}
📺 관전자 : {spectators}

{make_bar(players)}

🪑 남은 자리 : {remain}

💬 {message}
""",
        color=get_color(remain)
    )

    view = Recruit(voice_channel, interaction.user, message)

    await interaction.response.send_message(embed=embed, view=view)
    msg = await interaction.original_response()

    view.message = msg

    active_recruits[voice_channel.id] = {
        "message_id": msg.id,
        "host_id": interaction.user.id,
        "message_content": message  # ✅ 추가
    }

    print(f"✅ 구인 등록됨 | 채널: {voice_channel.name} | 메시지ID: {msg.id}")


@bot.event
async def on_voice_state_update(member, before, after):
    print(f"🎧 음성 상태 변경 감지: {member.display_name}")

    channels = []
    if before.channel:
        channels.append(before.channel)
    if after.channel:
        channels.append(after.channel)

    for channel in channels:

        if channel.id not in active_recruits:
            continue

        print(f"📢 구인 추적 중 채널 감지: {channel.name}")

        data = active_recruits[channel.id]

        text_channel = channel.guild.get_channel(CHANNEL_ID)

        if text_channel is None:
            print("❌ 텍스트 채널 못 찾음")
            return

        try:
            msg = await text_channel.fetch_message(data["message_id"])
            print("✅ 메시지 가져오기 성공")
        except Exception as e:
            print("❌ 메시지 가져오기 실패:", e)
            continue

        view = Recruit(
            channel,
            member.guild.get_member(data["host_id"]),
            data["message_content"]  # ✅ 수정
        )
        view.message = msg

        # 모집자 나갔는지 체크
        if view.host not in channel.members:
            print("🚨 모집자 나감 → 자동 종료")
            await view.auto_close()
            return

        await view.update_embed()


bot.run(TOKEN)
