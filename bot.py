import os

import discord
from discord import app_commands
from discord.ext import commands


TOKEN = os.getenv("TOKEN")

MAX_PLAYERS = 4
CHANNEL_ID = 1477735324582154342  # 기존 배그 구인 채널 고정

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
            continue

        if "[📺관전중]" in member.display_name:
            spectators += 1
        else:
            players += 1

    return players, spectators


def get_color(remain):
    if remain <= 0:
        return 0xFF0000
    if remain == 1:
        return 0xFFCC00
    return 0x00FF00


def get_recruit_color(players, max_players):
    if max_players is None:
        return 0x00FF00

    remain = max_players - players
    return get_color(remain)


def build_description(host, voice_channel, players, spectators, message_content, max_players=None):
    lines = [
        f"👤 모집자 : {host.mention}",
        f"🔊 채널 : {voice_channel.name}",
        "",
    ]

    if max_players is None:
        lines.append(f"👥 참여 인원 : {players}명")
        lines.append(f"📺 관전자 : {spectators}")
    else:
        remain = max_players - players
        lines.append(f"👥 참여 인원 : {players} / {max_players}")
        lines.append(f"📺 관전자 : {spectators}")
        lines.append("")
        lines.append(f"🪑 남은 자리 : {remain}")

    lines.extend(["", f"💬 {message_content}"])
    return "\n".join(lines)


class RecruitView(discord.ui.View):
    def __init__(self, channel, host, game_name, message_content, max_players=None):
        super().__init__(timeout=None)
        self.channel = channel
        self.host = host
        self.game_name = game_name
        self.message_content = message_content
        self.max_players = max_players
        self.message = None

    async def update_embed(self):
        print("📌 update_embed 실행됨")

        players, spectators = count_members(self.channel)

        embed = self.message.embeds[0]
        embed.title = f"🎮 {self.game_name} 모집중!!"
        embed.color = get_recruit_color(players, self.max_players)
        embed.description = build_description(
            self.host,
            self.channel,
            players,
            spectators,
            self.message_content,
            self.max_players,
        )

        await self.message.edit(embed=embed, view=self)

        if self.max_players is not None and players >= self.max_players:
            print("🔥 인원 다 참 → 자동 종료")
            await self.auto_close()

    async def auto_close(self):
        print("❌ auto_close 실행됨")

        embed = self.message.embeds[0]
        embed.title = f"🎮 {self.game_name} 모집 종료"
        embed.color = 0xFF0000

        for item in self.children:
            item.disabled = True

        await self.message.edit(embed=embed, view=self)

        if self.channel.id in active_recruits:
            del active_recruits[self.channel.id]

    @discord.ui.button(label="참가하기", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.voice and interaction.user.voice.channel == self.channel:
            await interaction.response.send_message("이미 해당 음성채널에 참여 중입니다.", ephemeral=True)
            return

        permissions = self.channel.permissions_for(interaction.guild.me)
        can_move = permissions.move_members and permissions.connect

        if interaction.user.voice and can_move:
            try:
                await interaction.user.move_to(self.channel)
                await interaction.response.send_message(
                    f"{self.channel.mention} 음성채널로 이동했습니다.",
                    ephemeral=True,
                )
                return
            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass

        invite = await self.channel.create_invite(max_age=300, max_uses=1)
        await interaction.response.send_message(
            f"바로 이동 권한이 없어 초대 링크를 드릴게요: {invite.url}",
            ephemeral=True,
        )

    @discord.ui.button(label="모집종료", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            await interaction.response.send_message("모집자만 종료 가능", ephemeral=True)
            return

        print("🛑 수동 종료 버튼 클릭")
        await interaction.response.defer()
        await self.auto_close()


class GeneralRecruitModal(discord.ui.Modal, title="종겜 구인"):
    game_name = discord.ui.TextInput(
        label="게임 이름",
        placeholder="예: 롤, 발로란트, 마크",
        max_length=100,
    )
    message_content = discord.ui.TextInput(
        label="하고 싶은 말",
        placeholder="예: 2판만 가볍게 하실 분",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("음성채널 먼저 들어가세요", ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel
        message_text = str(self.message_content).strip() or " "

        await create_recruit_post(
            interaction=interaction,
            text_channel=interaction.channel,
            voice_channel=voice_channel,
            host=interaction.user,
            game_name=str(self.game_name).strip(),
            message_content=message_text,
            mention_here=False,
            max_players=None,
        )


async def create_recruit_post(
    interaction: discord.Interaction,
    text_channel: discord.TextChannel,
    voice_channel: discord.VoiceChannel,
    host: discord.Member,
    game_name: str,
    message_content: str,
    mention_here: bool,
    max_players=None,
):
    players, spectators = count_members(voice_channel)

    embed = discord.Embed(
        title=f"🎮 {game_name} 모집중!!",
        description=build_description(
            host,
            voice_channel,
            players,
            spectators,
            message_content,
            max_players,
        ),
        color=get_recruit_color(players, max_players),
    )

    view = RecruitView(
        voice_channel,
        host,
        game_name,
        message_content,
        max_players=max_players,
    )
    content = "@here" if mention_here else None

    await interaction.response.send_message(content=content, embed=embed, view=view)
    msg = await interaction.original_response()
    view.message = msg

    active_recruits[voice_channel.id] = {
        "message_id": msg.id,
        "host_id": host.id,
        "text_channel_id": text_channel.id,
        "game_name": game_name,
        "message_content": message_content,
        "max_players": max_players,
    }

    print(f"✅ 구인 등록됨 | 채널: {voice_channel.name} | 메시지ID: {msg.id}")


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

    await create_recruit_post(
        interaction=interaction,
        text_channel=interaction.channel,
        voice_channel=voice_channel,
        host=interaction.user,
        game_name="PUBG",
        message_content=message,
        mention_here=True,
        max_players=MAX_PLAYERS,
    )


@bot.tree.command(name="종겜구인", description="원하는 게임으로 구인 글 작성")
async def general_recruit(interaction: discord.Interaction):
    await interaction.response.send_modal(GeneralRecruitModal())


@bot.event
async def on_voice_state_update(member, before, after):
    print(f"🎧 음성 상태 변경 감지: {member.display_name}")

    channels = []
    if before.channel:
        channels.append(before.channel)
    if after.channel and after.channel not in channels:
        channels.append(after.channel)

    for channel in channels:
        if channel.id not in active_recruits:
            continue

        print(f"📢 구인 추적 중 채널 감지: {channel.name}")

        data = active_recruits[channel.id]
        text_channel = channel.guild.get_channel(data["text_channel_id"])

        if text_channel is None:
            print("❌ 텍스트 채널 못 찾음")
            continue

        try:
            msg = await text_channel.fetch_message(data["message_id"])
            print("✅ 메시지 가져오기 성공")
        except Exception as e:
            print("❌ 메시지 가져오기 실패:", e)
            continue

        host_member = member.guild.get_member(data["host_id"])
        if host_member is None:
            print("🚨 모집자 정보를 찾을 수 없음 → 자동 종료")
            view = RecruitView(
                channel,
                member,
                data["game_name"],
                data["message_content"],
                max_players=data.get("max_players"),
            )
            view.message = msg
            await view.auto_close()
            continue

        view = RecruitView(
            channel,
            host_member,
            data["game_name"],
            data["message_content"],
            max_players=data.get("max_players"),
        )
        view.message = msg

        if view.host not in channel.members:
            print("🚨 모집자 나감 → 자동 종료")
            await view.auto_close()
            continue

        await view.update_embed()


bot.run(TOKEN)
