import discord
from discord.ext import commands, tasks
import datetime
import os

intents = discord.Intents.default()
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

TURKEY_CHANNEL_ID = 1486631386533199872
EXCLUDED_ROLE_IDS = [1486571017806811228, 1486560941368803389]  # Asyl + spieSS
INACTIVITY_TIME = 1.5 * 60 * 60  # 1.5 Stunden in Sekunden

last_active = {}

def is_speaking(member):
    vs = member.voice
    if vs is None:
        return False
    return not vs.self_mute and not vs.mute and not vs.self_deaf and not vs.deaf

@bot.event
async def on_ready():
    print(f"✅ Bot ist online: {bot.user}")
    check_inactivity.start()

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    now = datetime.datetime.utcnow()

    if after.channel and after.channel.id != TURKEY_CHANNEL_ID:
        if member.id not in last_active:
            last_active[member.id] = now

        was_muted = before.self_mute or before.mute or before.self_deaf or before.deaf
        is_muted = after.self_mute or after.mute or after.self_deaf or after.deaf
        if was_muted and not is_muted:
            last_active[member.id] = now

    if after.channel is None:
        last_active.pop(member.id, None)

@tasks.loop(minutes=5)
async def check_inactivity():
    now = datetime.datetime.utcnow()
    turkey_channel = bot.get_channel(TURKEY_CHANNEL_ID)

    if not turkey_channel:
        return

    for guild in bot.guilds:
        for vc in guild.voice_channels:
            if vc.id == TURKEY_CHANNEL_ID:
                continue
            for member in vc.members:
                if member.bot:
                    continue
                if any(role.id in EXCLUDED_ROLE_IDS for role in member.roles):
                    continue

                if member.id not in last_active:
                    last_active[member.id] = now
                    continue

                if is_speaking(member):
                    last_active[member.id] = now
                    continue

                inaktiv_seit = (now - last_active[member.id]).total_seconds()
                if inaktiv_seit > INACTIVITY_TIME:
                    try:
                        await member.move_to(turkey_channel)
                        print(f"→ {member.name} wurde in die Türkei geschoben (inaktiv seit {inaktiv_seit/60:.0f} min)")
                    except Exception as e:
                        print(f"Fehler beim Verschieben von {member.name}: {e}")

bot.run(os.getenv("DISCORD_TOKEN"))
