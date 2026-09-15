import discord
from discord.ext import commands, tasks
import datetime
import os
import threading
from flask import Flask
from dotenv import load_dotenv

# ================== .ENV LADEN ==================
load_dotenv("/opt/discordbot/.env")
# ================================================


# ================== KLEINER STATUS-WEBSERVER ==================
app = Flask(__name__)

@app.route('/')
@app.route('/ping')
def ping():
    return "AFK Bot is alive!", 200

def run_webserver():
    app.run(host='0.0.0.0', port=8080)

threading.Thread(target=run_webserver, daemon=True).start()
# ============================================================


# ================== DISCORD BOT SETUP ==================
intents = discord.Intents.default()
intents.voice_states = True
intents.members = True
intents.invites = True
# intents.message_content = True   # falls du später Commands brauchst

bot = commands.Bot(command_prefix="!", intents=intents)
# =======================================================


# ================== EINSTELLUNGEN ==================
TURKEY_CHANNEL_ID = 1486631386533199872

EXCLUDED_ROLE_IDS = [
    1486571017806811228,
    1486560941368803389
]

INACTIVITY_TIME = 45 * 60

# WICHTIG:
# Hier die echte ID deiner BWI-Rolle eintragen.
BWI_ROLE_ID = 1486613262953877645
# ==================================================


# ================== AFK DATEN ==================
last_active = {}
# ================================================


# ================== INVITE CACHE ==================
# Struktur:
#
# invite_cache[guild_id][invite_code] = Anzahl der Nutzungen
#
# Beispiel:
# invite_cache[1234]["abc123"] = 7

invite_cache = {}
# ==================================================


# ================== AFK FUNKTION ==================
def is_speaking(member):
    vs = member.voice

    if vs is None:
        return False

    return (
        not vs.self_mute
        and not vs.mute
        and not vs.self_deaf
        and not vs.deaf
    )
# ==================================================


# ================== BOT READY ==================
@bot.event
async def on_ready():
    print(f"✅ Bot ist online: {bot.user}")

    # AFK-Task nur starten, wenn er noch nicht läuft.
    # Wichtig bei Discord-Reconnects.
    if not check_inactivity.is_running():
        check_inactivity.start()

    # Aktuelle Invite-Zähler aller Server laden
    for guild in bot.guilds:
        try:
            invites = await guild.invites()

            invite_cache[guild.id] = {
                invite.code: invite.uses or 0
                for invite in invites
            }

            print(
                f"🔗 Invite-Cache geladen: "
                f"{guild.name} ({len(invites)} Invites)"
            )

        except discord.Forbidden:
            print(
                f"❌ Invite-Cache für {guild.name} konnte nicht geladen werden: "
                f"fehlende Berechtigung."
            )

        except discord.HTTPException as e:
            print(
                f"❌ Fehler beim Laden der Invites für {guild.name}: {e}"
            )
# ================================================


# ================== NEUER INVITE ==================
@bot.event
async def on_invite_create(invite):
    if invite.guild is None:
        return

    if invite.guild.id not in invite_cache:
        invite_cache[invite.guild.id] = {}

    invite_cache[invite.guild.id][invite.code] = invite.uses or 0

    print(
        f"🔗 Neuer Invite registriert: {invite.code} "
        f"auf {invite.guild.name}"
    )
# ==================================================


# ================== INVITE GELÖSCHT ==================
@bot.event
async def on_invite_delete(invite):
    if invite.guild is None:
        return

    guild_cache = invite_cache.get(invite.guild.id)

    if guild_cache is not None:
        guild_cache.pop(invite.code, None)

    print(
        f"🗑️ Invite entfernt: {invite.code} "
        f"auf {invite.guild.name}"
    )
# ======================================================


# ================== BWI VERERBUNG ==================
@bot.event
async def on_member_join(member):
    # Bots bekommen niemals automatisch BWI
    if member.bot:
        return

    guild = member.guild

    try:
        # Aktuelle Invites nach dem Join abrufen
        current_invites = await guild.invites()

    except discord.Forbidden:
        print(
            f"❌ Invite-Erkennung bei {member} nicht möglich: "
            f"Bot hat keine ausreichenden Rechte."
        )
        return

    except discord.HTTPException as e:
        print(
            f"❌ Discord-Fehler beim Abrufen der Invites "
            f"für {member}: {e}"
        )
        return

    old_invites = invite_cache.get(guild.id, {})

    # Hier sammeln wir alle Invites,
    # deren Nutzungszahl gestiegen ist.
    changed_invites = []

    for invite in current_invites:
        old_uses = old_invites.get(invite.code, 0)
        new_uses = invite.uses or 0

        if new_uses > old_uses:
            changed_invites.append(invite)

    # Cache SOFORT auf den neuen Stand bringen
    invite_cache[guild.id] = {
        invite.code: invite.uses or 0
        for invite in current_invites
    }

    # Kein Invite konnte erkannt werden
    if len(changed_invites) == 0:
        print(
            f"ℹ️ Join erkannt: {member} – "
            f"verwendeter Invite konnte nicht bestimmt werden."
        )
        return

    # Mehrere Invites haben sich gleichzeitig verändert.
    #
    # Aus Sicherheitsgründen vergeben wir dann KEINE BWI-Rolle,
    # statt möglicherweise dem falschen User BWI zu geben.
    if len(changed_invites) > 1:
        print(
            f"⚠️ Join von {member}: "
            f"mehrere veränderte Invites erkannt. "
            f"BWI wird aus Sicherheitsgründen nicht vergeben."
        )
        return

    used_invite = changed_invites[0]

    # Wer hat diesen Invite erstellt?
    inviter = used_invite.inviter

    if inviter is None:
        print(
            f"ℹ️ Invite {used_invite.code} wurde benutzt, "
            f"aber der Ersteller konnte nicht erkannt werden."
        )
        return

    # Discord-Member-Objekt des Einladenden holen
    inviter_member = guild.get_member(inviter.id)

    # Fallback, falls Member nicht im Cache gefunden wurde
    if inviter_member is None:
        try:
            inviter_member = await guild.fetch_member(inviter.id)

        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            print(
                f"ℹ️ Einladender {inviter} konnte auf dem Server "
                f"nicht gefunden werden."
            )
            return

    # BWI-Rolle suchen
    bwi_role = guild.get_role(BWI_ROLE_ID)

    if bwi_role is None:
        print(
            f"❌ BWI-Rolle mit ID {BWI_ROLE_ID} "
            f"wurde nicht gefunden."
        )
        return

    # Hat der EINLADENDE aktuell BWI?
    if bwi_role not in inviter_member.roles:
        print(
            f"ℹ️ {member} wurde von {inviter_member} eingeladen. "
            f"{inviter_member} besitzt jedoch kein BWI → "
            f"keine Rolle vergeben."
        )
        return

    # Falls der neue User wider Erwarten bereits BWI besitzt,
    # nichts doppelt machen.
    if bwi_role in member.roles:
        print(
            f"ℹ️ {member} besitzt BWI bereits."
        )
        return

    # BWI an den neuen User KOPIEREN.
    #
    # WICHTIG:
    # Dem Einladenden wird hierbei NICHTS weggenommen.
    try:
        await member.add_roles(
            bwi_role,
            reason=(
                f"BWI automatisch übernommen über Invite "
                f"von {inviter_member}"
            )
        )

        print(
            f"✅ BWI übernommen: "
            f"{inviter_member} → {member} "
            f"(Invite: {used_invite.code})"
        )

    except discord.Forbidden:
        print(
            f"❌ BWI konnte {member} nicht gegeben werden. "
            f"Prüfe Rollenreihenfolge und 'Rollen verwalten'."
        )

    except discord.HTTPException as e:
        print(
            f"❌ Discord-Fehler beim Vergeben von BWI "
            f"an {member}: {e}"
        )
# ==================================================


# ================== VOICE STATE ==================
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    now = datetime.datetime.now(datetime.UTC)

    if after.channel and after.channel.id != TURKEY_CHANNEL_ID:

        if member.id not in last_active:
            last_active[member.id] = now

        was_muted = (
            before.self_mute
            or before.mute
            or before.self_deaf
            or before.deaf
        )

        is_muted = (
            after.self_mute
            or after.mute
            or after.self_deaf
            or after.deaf
        )

        if was_muted and not is_muted:
            last_active[member.id] = now

    if after.channel is None:
        last_active.pop(member.id, None)
# ==================================================


# ================== AFK CHECK ==================
@tasks.loop(minutes=5)
async def check_inactivity():
    now = datetime.datetime.now(datetime.UTC)

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

                if any(
                    role.id in EXCLUDED_ROLE_IDS
                    for role in member.roles
                ):
                    continue

                if member.id not in last_active:
                    last_active[member.id] = now
                    continue

                if is_speaking(member):
                    last_active[member.id] = now
                    continue

                inaktiv_seit = (
                    now - last_active[member.id]
                ).total_seconds()

                if inaktiv_seit > INACTIVITY_TIME:

                    try:
                        await member.move_to(turkey_channel)

                        print(
                            f"→ {member.name} wurde in die Türkei geschoben "
                            f"(inaktiv seit {inaktiv_seit/60:.0f} min)"
                        )

                    except Exception as e:
                        print(
                            f"Fehler beim Verschieben "
                            f"von {member.name}: {e}"
                        )
# ==================================================


# ================== BOT START ==================
bot.run(os.getenv("DISCORD_TOKEN"))
# ================================================
