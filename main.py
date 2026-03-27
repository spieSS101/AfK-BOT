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
INACTIVITY_TIME = 2 * 60 * 60  # 2 Stunden

last_activity = {}

@bot.event
async def on_ready():
    print(f"✅ Bot ist online: {bot.user}")
    check_inactivity.start()

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
    if after.channel and after.channel.id != TURKEY_CHANNEL_ID:
        last_activity[member.id] = datetime.datetime.utcnow()

@tasks.loop(minutes=10)
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
                
                last = last_activity.get(member.id)
                if last and (now - last).total_seconds() > INACTIVITY_TIME:
                    try:
                        await member.move_to(turkey_channel)
                        print(f"→ {member.name} wurde in die Türkei geschoben")
                    except:
                        pass

bot.run(os.getenv("DISCORD_TOKEN"))
