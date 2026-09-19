import discord
from discord.ext import commands, tasks
import datetime
import os
import asyncio
import random
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
    return "Bot is alive", 200

def run_webserver():
    app.run(host='0.0.0.0', port=8080)

threading.Thread(target=run_webserver, daemon=True).start()
# ============================================================


# ================== DISCORD BOT SETUP ==================
intents = discord.Intents.default()
intents.voice_states = True
intents.members = True
intents.invites = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
# =======================================================


# ================== EINSTELLUNGEN ==================

# AFK / Türkei
TURKEY_CHANNEL_ID = 1486631386533199872

EXCLUDED_ROLE_IDS = [
    1486571017806811228,
    1486560941368803389
]

INACTIVITY_TIME = 30 * 60


# BWI
BWI_ROLE_ID = 1486613262953877645


# Admin-Channel für Rollenvergabe
ADMIN_ROLE_CHANNEL_ID = 1549364249317351434


SPIESS_ROLE_ID = 1486560941368803389

BUNKER_VOICE_CHANNEL_ID = 1486574554900987986
JERKING_VOICE_CHANNEL_ID = 1529300838688882812

BUNKER_USER_ID = int(os.getenv("BUNKER_USER_ID", "0"))
JERKING_USER_ID = int(os.getenv("JERKING_USER_ID", "0"))

BUNKER_MESSAGE = "Bunkerzeit"
JERKING_MESSAGE = "Jerking Hours"

# Private Bunker-DM
GUILD_ID = 1486542167601184788

BUNKER_DM_INTERVAL = 30
BUNKER_TARGET_CHANNEL_ID = BUNKER_VOICE_CHANNEL_ID

# Private Erinnerung an JERKING_USER_ID, wenn ein Spiess in der Alten Mühle wartet.
JERKING_TARGET_CHANNEL_ID = JERKING_VOICE_CHANNEL_ID

# Jede Wiederholung bekommt einen neuen zufälligen Abstand:
# mindestens 3:47 Minuten, höchstens 5:00 Minuten.
JERKING_REMINDER_MIN_INTERVAL = 3 * 60 + 47
JERKING_REMINDER_MAX_INTERVAL = 5 * 60

def get_random_jerking_reminder_interval():
    return random.randint(
        JERKING_REMINDER_MIN_INTERVAL,
        JERKING_REMINDER_MAX_INTERVAL
    )

ADJEKTIVE = [
    "arschiger", "idiotischer", "stinkender", "vergammelter", "verfaulter",
    "hässlicher", "dreckiger", "ranziger", "räudiger", "ekelhafter",
    "widerlicher", "bescheuerter", "bekloppter", "dämlicher", "hirnloser",
    "geistloser", "zurückgebliebener", "nutzloser", "erbärmlicher",
    "peinlicher", "lächerlicher", "armseliger", "verwirrter", "inkompetenter",
    "missratener", "ungewaschener", "versiffter", "verschimmelter",
    "verkrusteter", "aufgequollener", "fettiger", "schmieriger", "muffiger",
    "gammeliger", "sabbernder", "furzender", "eierloser", "lappenartiger",
    "hodenköpfiger",
]

NOMEN = [
    "Affe", "Elefant", "Pinguin", "Fisch", "Schwanz", "Idiot", "Holzkopf",
    "Lappen", "Vollpfosten", "Hohlkopf", "Trottel", "Clown", "Knecht",
    "Lauch", "Esel", "Ochse", "Gorilla", "Pavian", "Orang-Utan", "Nacktmull",
    "Waschbär", "Wombat", "Seegurke", "Karpfen", "Thunfisch",
    "Gartenzwerg", "Mülleimer", "Klodeckel", "Toilettenbesen", "Abfluss",
    "Türstopper", "Bierdeckel", "Kartoffelsack", "Müllsack", "Duschvorhang",
    "Teppich", "Aschenbecher", "Klobürste", "Sockenhalter", "Hodenkobold",
    "Arschgeige", "Furzkanone", "Kotzbrocken", "Rotzlöffel", "Hackfresse",
    "Kackspaten", "Eierkopf", "Dödel", "Arschkopf",
]

jerking_target_dm_task = None
jerking_target_dm_messages = []

# BWI-Voice-Bereich (Discord-Kategorie)
BWI_VOICE_CATEGORY_ID = 1486612928584093706
BWI_NOTIFICATION_PREFIX = "BWI-Bereich beigetreten"

BWI_VOICE_CHANNEL_IDS = {
    1486936046393495582: "Zockerstube",
    1486613172126355546: "Workingstation",
    1486613053582868520: "Kaminecke",
}

# Private DMs für alle Accounts mit der Spiess-Rolle.
# Gespeichert pro Empfänger und Benachrichtigungsgruppe.
private_dm_messages = {
    "bunker": {},
    "jerking": {},
    "bwi": {},
}

# BWI: pro Spiess-Empfänger und beobachtetem User genau eine aktuelle DM.
bwi_user_dm_messages = {}


# ============================================================
# ROLLEN FÜR DAS ADMIN-MENÜ
#
# Wenn du später eine weitere Rolle hinzufügen möchtest,
# musst du NUR hier einen weiteren Eintrag ergänzen.
#
# Beispiel:
#
# {
#     "label": "Neue Rolle",
#     "role_id": 123456789012345678
# },
#
# ============================================================

ADMIN_ASSIGNABLE_ROLES = [
    {"label": "BWI", "role_id": 1486613262953877645},
    {"label": "Vanilla", "role_id": 1486551681490747483},
    {"label": "Asyl", "role_id": 1486571017806811228},
    {"label": "Abschiebeamt", "role_id": 1486552799834673194},
    {"label": "Ratsmitglied", "role_id": 1486552582397759499},
    {"label": "Jobcenter", "role_id": 1486553099475615856},
    {"label": "Sounds und Nickname", "role_id": 1486554277697556480},
]

# ============================================================


# ================== AFK DATEN ==================
last_active = {}
# ================================================


# ================== INVITE CACHE ==================
invite_cache = {}
# ==================================================




# ================== PRIVATE BUNKER/JERKING-DM LOOPS ==================
# BUNKER_USER_ID / JERKING_USER_ID joint den jeweiligen Voice-Channel:
# sofortige DM an alle Spiess-Accounts und danach jede Minute erneut,
# bis ein Spiess joint oder "Jetzt nicht" gedrückt wird.
PRIVATE_VOICE_DM_INTERVAL = 60

private_voice_dm_tasks = {
    "bunker": None,
    "jerking": None,
}

# Private Erinnerung an BUNKER_USER_ID, wenn ein Spiess im Bunker wartet.
bunker_dm_task = None
bunker_dm_messages = []
# =====================================================================


# ============================================================
# ADMIN ROLLEN-MENÜ
# ============================================================

def get_managed_role_ids():
    return {
        role_data["role_id"]
        for role_data in ADMIN_ASSIGNABLE_ROLES
    }


def get_managed_role_names(member):
    names = []

    for role_data in ADMIN_ASSIGNABLE_ROLES:
        if any(role.id == role_data["role_id"] for role in member.roles):
            names.append(role_data["label"])

    return names


def build_admin_role_message(member):
    role_names = get_managed_role_names(member)
    roles_text = ", ".join(role_names) if role_names else "Keine"

    return (
        f"👤 **Neuer Benutzer:** {member.mention}\n"
        f"`{member}`\n"
        f"**Aktuelle Rollen:** {roles_text}\n\n"
        f"Welche Rolle(n) soll der Benutzer erhalten?"
    )


class RoleSelect(discord.ui.Select):

    def __init__(self, target_member):

        self.target_member = target_member
        current_role_ids = {
            role.id
            for role in target_member.roles
        }

        options = []

        for role_data in ADMIN_ASSIGNABLE_ROLES:
            options.append(
                discord.SelectOption(
                    label=role_data["label"],
                    value=str(role_data["role_id"]),
                    default=role_data["role_id"] in current_role_ids
                )
            )

        super().__init__(
            placeholder="Rolle(n) verwalten...",
            min_values=0,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Du darfst dieses Menü nicht benutzen.",
                ephemeral=True
            )
            return

        member = interaction.guild.get_member(
            self.view.target_member_id
        )

        if member is None:
            try:
                member = await interaction.guild.fetch_member(
                    self.view.target_member_id
                )
            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException
            ):
                await interaction.response.send_message(
                    "❌ Der Benutzer konnte nicht mehr gefunden werden.",
                    ephemeral=True
                )
                return

        selected_role_ids = {
            int(role_id)
            for role_id in self.values
        }

        managed_role_ids = get_managed_role_ids()

        current_managed_role_ids = {
            role.id
            for role in member.roles
            if role.id in managed_role_ids
        }

        role_ids_to_add = selected_role_ids - current_managed_role_ids
        role_ids_to_remove = current_managed_role_ids - selected_role_ids

        roles_to_add = [
            interaction.guild.get_role(role_id)
            for role_id in role_ids_to_add
        ]
        roles_to_add = [
            role for role in roles_to_add
            if role is not None
        ]

        roles_to_remove = [
            interaction.guild.get_role(role_id)
            for role_id in role_ids_to_remove
        ]
        roles_to_remove = [
            role for role in roles_to_remove
            if role is not None
        ]

        try:
            if roles_to_add:
                await member.add_roles(
                    *roles_to_add,
                    reason=f"Admin-Rollenverwaltung durch {interaction.user}"
                )

            if roles_to_remove:
                await member.remove_roles(
                    *roles_to_remove,
                    reason=f"Admin-Rollenverwaltung durch {interaction.user}"
                )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Der Bot darf mindestens eine dieser Rollen nicht verwalten. "
                "Prüfe die Rollenreihenfolge.",
                ephemeral=True
            )
            return

        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ Discord-Fehler beim Ändern der Rollen.",
                ephemeral=True
            )
            return

        # Member neu laden, damit Anzeige und Häkchen sicher aktuell sind.
        try:
            member = await interaction.guild.fetch_member(member.id)
        except discord.HTTPException:
            pass

        # Nur dieselbe ursprüngliche Nachricht aktualisieren:
        # keine Erfolgs-/Auswahl-Benachrichtigung und das Dropdown bleibt erhalten.
        await interaction.response.edit_message(
            content=build_admin_role_message(member),
            view=MemberRoleView(member)
        )


class MemberRoleView(discord.ui.View):

    def __init__(self, target_member):
        # 24 Stunden Zeit für die Rollenverwaltung
        super().__init__(timeout=86400)

        self.target_member_id = target_member.id

        self.add_item(
            RoleSelect(target_member)
        )


# ============================================================


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

    if not check_inactivity.is_running():
        check_inactivity.start()

    # Persistente Bestätigen-Buttons registrieren.
    # Dadurch funktionieren bereits gesendete Buttons auch nach einem Bot-Neustart.
    if not getattr(bot, "_notification_views_registered", False):
        bot.add_view(PrivateVoiceDMView("bunker", BUNKER_VOICE_CHANNEL_ID))
        bot.add_view(PrivateVoiceDMView("jerking", JERKING_VOICE_CHANNEL_ID))
        bot.add_view(BWIPrivateDMView(BWI_VOICE_CHANNEL_IDS[1486613172126355546], 1486613172126355546))
        bot.add_view(BunkerTargetDMView("first"))
        bot.add_view(BunkerTargetDMView("reminder"))
        bot.add_view(JerkingTargetDMView("first"))
        bot.add_view(JerkingTargetDMView("reminder"))
        bot.add_view(DeleteAllDMView())
        bot._notification_views_registered = True

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
                f"❌ Invite-Cache für {guild.name} "
                f"konnte nicht geladen werden."
            )

        except discord.HTTPException as e:

            print(
                f"❌ Fehler beim Laden der Invites "
                f"für {guild.name}: {e}"
            )
# ================================================


# ================== NEUER INVITE ==================
@bot.event
async def on_invite_create(invite):

    if invite.guild is None:
        return

    if invite.guild.id not in invite_cache:
        invite_cache[invite.guild.id] = {}

    invite_cache[invite.guild.id][invite.code] = (
        invite.uses or 0
    )

    print(
        f"🔗 Neuer Invite registriert: "
        f"{invite.code} auf {invite.guild.name}"
    )
# ==================================================


# ================== INVITE GELÖSCHT ==================
@bot.event
async def on_invite_delete(invite):

    if invite.guild is None:
        return

    guild_cache = invite_cache.get(
        invite.guild.id
    )

    if guild_cache is not None:
        guild_cache.pop(
            invite.code,
            None
        )

    print(
        f"🗑️ Invite entfernt: "
        f"{invite.code} auf {invite.guild.name}"
    )
# ======================================================


# ================== MEMBER JOIN ==================
@bot.event
async def on_member_join(member):

    if member.bot:
        return

    guild = member.guild

    # ==================================================
    # 1. ZUERST BWI INVITE-VERERBUNG PRÜFEN
    # ==================================================

    try:
        current_invites = await guild.invites()

    except discord.Forbidden:
        print(
            f"❌ Invite-Erkennung bei {member} "
            f"nicht möglich."
        )
        current_invites = []

    except discord.HTTPException as e:
        print(
            f"❌ Discord-Fehler beim Abrufen "
            f"der Invites für {member}: {e}"
        )
        current_invites = []

    old_invites = invite_cache.get(
        guild.id,
        {}
    )

    changed_invites = []

    for invite in current_invites:

        old_uses = old_invites.get(
            invite.code,
            0
        )

        new_uses = invite.uses or 0

        if new_uses > old_uses:
            changed_invites.append(invite)

    # Cache sofort aktualisieren
    if current_invites:
        invite_cache[guild.id] = {
            invite.code: invite.uses or 0
            for invite in current_invites
        }

    if len(changed_invites) == 0:

        print(
            f"ℹ️ Join erkannt: {member} – "
            f"Invite konnte nicht bestimmt werden."
        )

    elif len(changed_invites) > 1:

        print(
            f"⚠️ Join von {member}: "
            f"mehrere veränderte Invites erkannt."
        )

    else:

        used_invite = changed_invites[0]
        inviter = used_invite.inviter

        if inviter is None:

            print(
                f"ℹ️ Invite {used_invite.code} "
                f"hat keinen erkennbaren Ersteller."
            )

        else:

            inviter_member = guild.get_member(
                inviter.id
            )

            if inviter_member is None:

                try:
                    inviter_member = await guild.fetch_member(
                        inviter.id
                    )

                except (
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException
                ):
                    inviter_member = None

                    print(
                        f"ℹ️ Einladender {inviter} "
                        f"konnte nicht gefunden werden."
                    )

            if inviter_member is not None:

                bwi_role = guild.get_role(
                    BWI_ROLE_ID
                )

                if bwi_role is None:

                    print(
                        f"❌ BWI-Rolle mit ID "
                        f"{BWI_ROLE_ID} wurde nicht gefunden."
                    )

                elif bwi_role not in inviter_member.roles:

                    print(
                        f"ℹ️ {member} wurde von "
                        f"{inviter_member} eingeladen. "
                        f"Kein BWI vorhanden."
                    )

                elif bwi_role in member.roles:

                    print(
                        f"ℹ️ {member} besitzt BWI bereits."
                    )

                else:

                    try:
                        await member.add_roles(
                            bwi_role,
                            reason=(
                                f"BWI automatisch übernommen "
                                f"über Invite von {inviter_member}"
                            )
                        )

                        print(
                            f"✅ BWI übernommen: "
                            f"{inviter_member} → {member} "
                            f"(Invite: {used_invite.code})"
                        )

                    except discord.Forbidden:

                        print(
                            f"❌ BWI konnte {member} "
                            f"nicht gegeben werden."
                        )

                    except discord.HTTPException as e:

                        print(
                            f"❌ Discord-Fehler beim "
                            f"Vergeben von BWI an {member}: {e}"
                        )

    # ==================================================
    # 2. DANACH ADMIN-NACHRICHT MIT AKTUELLEN ROLLEN
    # ==================================================

    # Member nach möglicher BWI-Vergabe frisch laden,
    # damit Text und Dropdown-Häkchen den neuen Stand sehen.
    try:
        member = await guild.fetch_member(member.id)
    except discord.HTTPException:
        pass

    admin_channel = guild.get_channel(
        ADMIN_ROLE_CHANNEL_ID
    )

    if admin_channel is not None:

        try:

            await admin_channel.send(
                content=build_admin_role_message(member),
                view=MemberRoleView(member)
            )

        except discord.Forbidden:

            print(
                "❌ Bot kann keine Nachricht in den "
                "Admin-Rollen-Channel senden."
            )

        except discord.HTTPException as e:

            print(
                f"❌ Fehler beim Erstellen des "
                f"Admin-Rollen-Menüs: {e}"
            )

# ==================================================


# ================== VOICE-HILFSFUNKTIONEN ==================
def channel_has_spiess(voice_channel):
    return any(
        any(role.id == SPIESS_ROLE_ID for role in channel_member.roles)
        for channel_member in voice_channel.members
        if not channel_member.bot
    )


def member_is_spiess(member):
    return any(
        role.id == SPIESS_ROLE_ID
        for role in member.roles
    )


def is_bwi_voice_channel(channel):
    return (
        channel is not None
        and channel.category_id == BWI_VOICE_CATEGORY_ID
    )
# ============================================================

# ================== PRIVATE VOICE-DM FUNKTIONEN ==================
async def get_spiess_members(guild):
    return [
        m for m in guild.members
        if not m.bot and member_is_spiess(m)
    ]


async def delete_private_dm_group(notification_type):
    """
    Globales Aufräumen für alle Spiess-Accounts:
    Drückt EIN Spiess auf "Jetzt nicht" / "Nicht jetzt",
    werden alle noch gespeicherten privaten DMs dieser Gruppe
    bei ALLEN Spiess-Accounts gelöscht.
    """
    messages = []

    # Alle gespeicherten DMs dieser Gruppe von allen Empfängern einsammeln.
    group_messages = private_dm_messages.setdefault(notification_type, {})
    for recipient_messages in group_messages.values():
        messages.extend(recipient_messages)

    # Die komplette Gruppe zurücksetzen.
    private_dm_messages[notification_type] = {}

    # Bei BWI zusätzlich alle User->DM-Zuordnungen aller Spiess-Accounts entfernen.
    if notification_type == "bwi":
        messages.extend(bwi_user_dm_messages.values())
        bwi_user_dm_messages.clear()

    # Doppelte Message-Objekte vermeiden und alle DMs löschen.
    seen = set()
    for message in messages:
        if message is None or message.id in seen:
            continue
        seen.add(message.id)
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


def private_voice_dm_loop_is_running(notification_type):
    task = private_voice_dm_tasks.get(notification_type)
    return task is not None and not task.done()


def cancel_private_voice_dm_loop(notification_type):
    task = private_voice_dm_tasks.get(notification_type)
    private_voice_dm_tasks[notification_type] = None

    if (
        task is not None
        and not task.done()
        and task is not asyncio.current_task()
    ):
        task.cancel()


async def repeat_private_voice_dm_loop(
    guild,
    notification_type,
    channel_id,
    message_text
):
    try:
        while True:
            await asyncio.sleep(PRIVATE_VOICE_DM_INTERVAL)

            channel = guild.get_channel(channel_id)
            if channel is None or channel_has_spiess(channel):
                return

            await send_private_channel_dm_to_spiess(
                guild,
                notification_type,
                channel_id,
                message_text
            )

    except asyncio.CancelledError:
        return

    finally:
        if private_voice_dm_tasks.get(notification_type) is asyncio.current_task():
            private_voice_dm_tasks[notification_type] = None


async def start_private_voice_dm_loop(
    guild,
    notification_type,
    channel_id,
    message_text
):
    # Pro Gruppe darf nur genau ein Wiederholungs-Loop laufen.
    if private_voice_dm_loop_is_running(notification_type):
        return

    channel = guild.get_channel(channel_id)
    if channel is None or channel_has_spiess(channel):
        return

    # Erste Nachricht sofort.
    await send_private_channel_dm_to_spiess(
        guild,
        notification_type,
        channel_id,
        message_text
    )

    # Danach jede Minute erneut, bis ein Spiess joint oder "Jetzt nicht" gedrückt wird.
    private_voice_dm_tasks[notification_type] = asyncio.create_task(
        repeat_private_voice_dm_loop(
            guild,
            notification_type,
            channel_id,
            message_text
        )
    )


class PrivateNotNowButton(discord.ui.Button):
    def __init__(self, notification_type):
        label = "Nicht jetzt" if notification_type == "bwi" else "Jetzt nicht"
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            custom_id=f"private_voice_dm:not_now:{notification_type}"
        )
        self.notification_type = notification_type

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Bei Bunker/Jerking beendet "Jetzt nicht" zusätzlich den kompletten
        # Wiederholungs-Loop. BWI besitzt keinen solchen Loop.
        if self.notification_type in ("bunker", "jerking"):
            cancel_private_voice_dm_loop(self.notification_type)

        # Global für alle Spiess-Accounts die zugehörigen DMs löschen.
        await delete_private_dm_group(self.notification_type)


class PrivateVoiceDMView(discord.ui.View):
    def __init__(self, notification_type, channel_id):
        super().__init__(timeout=None)

        if notification_type == "bunker":
            label = "Zum Bunker"
        else:
            label = "Let's Jerk"

        self.add_item(DeleteAllDMButton())
        self.add_item(
            discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{GUILD_ID}/{channel_id}"
            )
        )
        self.add_item(PrivateNotNowButton(notification_type))


class BWIPrivateDMView(discord.ui.View):
    def __init__(self, channel_name, channel_id):
        super().__init__(timeout=None)
        self.add_item(DeleteAllDMButton())
        self.add_item(
            discord.ui.Button(
                label="Zum Channel",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{GUILD_ID}/{channel_id}"
            )
        )
        self.add_item(PrivateNotNowButton("bwi"))


async def send_private_channel_dm_to_spiess(guild, notification_type, channel_id, message_text):
    """Bunker/Jerking: DM an jeden Spiess-Account."""
    for recipient in await get_spiess_members(guild):
        # Wer selbst gerade im Zielchannel sitzt, braucht keine Join-DM.
        if recipient.voice and recipient.voice.channel and recipient.voice.channel.id == channel_id:
            continue

        try:
            message = await recipient.send(
                message_text,
                view=PrivateVoiceDMView(notification_type, channel_id)
            )
            private_dm_messages.setdefault(notification_type, {}).setdefault(recipient.id, []).append(message)
        except discord.Forbidden:
            print(f"❌ Private {notification_type}-DM an {recipient} nicht möglich.")
        except discord.HTTPException as e:
            print(f"❌ Fehler bei privater {notification_type}-DM an {recipient}: {e}")


async def send_or_update_bwi_dm(guild, watched_member, voice_channel):
    """
    Pro Spiess-Empfänger + beobachtetem User existiert maximal eine aktive BWI-DM.
    Bei Wechsel innerhalb BWI wird genau diese Nachricht editiert.
    """
    channel_name = BWI_VOICE_CHANNEL_IDS.get(voice_channel.id, voice_channel.name)
    content = (
        f"{watched_member.mention} ist dem BWI Bereich beigetreten\n"
        f"und ist im Channel **{channel_name}**"
    )

    for recipient in await get_spiess_members(guild):
        if recipient.id == watched_member.id:
            continue

        key = (recipient.id, watched_member.id)
        old_message = bwi_user_dm_messages.get(key)
        view = BWIPrivateDMView(channel_name, voice_channel.id)

        if old_message is not None:
            try:
                await old_message.edit(content=content, view=view)
                continue
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                bwi_user_dm_messages.pop(key, None)

        try:
            message = await recipient.send(content, view=view)
            bwi_user_dm_messages[key] = message
            private_dm_messages.setdefault("bwi", {}).setdefault(recipient.id, []).append(message)
        except discord.Forbidden:
            print(f"❌ Private BWI-DM an {recipient} nicht möglich.")
        except discord.HTTPException as e:
            print(f"❌ Fehler bei privater BWI-DM an {recipient}: {e}")


async def clear_bwi_user_tracking(watched_member_id):
    # Wenn der User den BWI-Bereich komplett verlässt, wird nur das Update-Tracking
    # aufgehoben. Die alte DM bleibt stehen, bis der Spiess 'Nicht jetzt' drückt.
    for key in list(bwi_user_dm_messages):
        if key[1] == watched_member_id:
            bwi_user_dm_messages.pop(key, None)



# ================== PRIVATE DM AN BUNKER_USER_ID ==================
def bunker_target_is_in_channel(guild):
    channel = guild.get_channel(BUNKER_TARGET_CHANNEL_ID)
    return (
        channel is not None
        and any(m.id == BUNKER_USER_ID for m in channel.members)
    )


def spiess_is_waiting_in_bunker_target(guild):
    channel = guild.get_channel(BUNKER_TARGET_CHANNEL_ID)
    return (
        channel is not None
        and any(
            not m.bot and member_is_spiess(m)
            for m in channel.members
        )
    )


def bunker_target_dm_is_running():
    return bunker_dm_task is not None and not bunker_dm_task.done()


def cancel_bunker_target_dm_task():
    global bunker_dm_task
    task = bunker_dm_task
    bunker_dm_task = None
    if task is not None and not task.done() and task is not asyncio.current_task():
        task.cancel()


async def delete_bunker_target_dm_messages():
    global bunker_dm_messages
    messages = list(bunker_dm_messages)
    bunker_dm_messages.clear()

    for message in messages:
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


async def get_bunker_target_user():
    user = bot.get_user(BUNKER_USER_ID)
    if user is not None:
        return user

    try:
        return await bot.fetch_user(BUNKER_USER_ID)
    except (discord.NotFound, discord.HTTPException):
        print("❌ BUNKER_USER_ID konnte nicht gefunden werden.")
        return None


async def disconnect_all_spiess_from_bunker_target(guild):
    channel = guild.get_channel(BUNKER_TARGET_CHANNEL_ID)
    if channel is None:
        return

    for member in list(channel.members):
        if member.bot or not member_is_spiess(member):
            continue
        try:
            await member.move_to(
                None,
                reason="Bunker-Erinnerung: Nicht jetzt"
            )
        except discord.Forbidden:
            print(f"❌ {member} konnte nicht aus dem Bunker getrennt werden.")
        except discord.HTTPException as e:
            print(f"❌ Fehler beim Trennen von {member} aus dem Bunker: {e}")


class BunkerTargetNotNowButton(discord.ui.Button):
    def __init__(self, message_type):
        super().__init__(
            label="Nicht jetzt",
            style=discord.ButtonStyle.secondary,
            custom_id=f"bunker_target_dm:not_now:{message_type}"
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != BUNKER_USER_ID:
            await interaction.response.send_message(
                "❌ Dieser Button ist nicht für dich.",
                ephemeral=True
            )
            return

        guild = bot.get_guild(GUILD_ID)
        if guild is None:
            await interaction.response.send_message(
                "❌ Der Server konnte nicht gefunden werden.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        # Loop sofort stoppen, alle wartenden Spiess-Accounts aus dem
        # Bunker trennen und anschließend die Bunker-Erinnerungs-DMs löschen.
        cancel_bunker_target_dm_task()
        await disconnect_all_spiess_from_bunker_target(guild)
        await delete_bunker_target_dm_messages()


class BunkerTargetDMView(discord.ui.View):
    def __init__(self, message_type):
        super().__init__(timeout=None)

        link_label = "Zum Bunker" if message_type == "first" else "Zum Bunker"

        self.add_item(DeleteAllDMButton())
        self.add_item(
            discord.ui.Button(
                label=link_label,
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{GUILD_ID}/{BUNKER_TARGET_CHANNEL_ID}"
            )
        )
        self.add_item(BunkerTargetNotNowButton(message_type))


async def send_bunker_target_dm(content, message_type):
    user = await get_bunker_target_user()
    if user is None:
        return False

    try:
        message = await user.send(
            content,
            view=BunkerTargetDMView(message_type)
        )
        bunker_dm_messages.append(message)
        return True
    except discord.Forbidden:
        print("❌ DM an BUNKER_USER_ID nicht möglich (DMs möglicherweise deaktiviert).")
        return False
    except discord.HTTPException as e:
        print(f"❌ Fehler beim Senden der DM an BUNKER_USER_ID: {e}")
        return False


async def bunker_target_reminder_loop(guild):
    global bunker_dm_task

    try:
        while True:
            await asyncio.sleep(BUNKER_DM_INTERVAL)

            # Letzter Spiess weg -> nur Loop beenden, vorhandene DMs bleiben bestehen.
            if not spiess_is_waiting_in_bunker_target(guild):
                return

            # Zieluser ist inzwischen da -> Loop endet.
            # Das Voice-Event löscht zusätzlich die bisherigen Erinnerungs-DMs.
            if bunker_target_is_in_channel(guild):
                return

            sent = await send_bunker_target_dm(
                "Bunkerzeit",
                "reminder"
            )
            if not sent:
                return

    except asyncio.CancelledError:
        return

    finally:
        if bunker_dm_task is asyncio.current_task():
            bunker_dm_task = None


async def start_bunker_target_wait(guild):
    global bunker_dm_task

    # Nur ein Loop, auch wenn mehrere Spiess-Accounts den Bunker betreten.
    if bunker_target_dm_is_running():
        return

    # Ist BUNKER_USER_ID schon da, gibt es nichts zu erinnern.
    if bunker_target_is_in_channel(guild):
        return

    sent = await send_bunker_target_dm(
        "Bunkerzeit",
        "first"
    )
    if not sent:
        return

    bunker_dm_task = asyncio.create_task(
        bunker_target_reminder_loop(guild)
    )
# ==================================================================


# ================== PRIVATE DM AN JERKING_USER_ID ==================
def jerking_target_is_in_channel(guild):
    channel = guild.get_channel(JERKING_TARGET_CHANNEL_ID)
    return (
        channel is not None
        and any(m.id == JERKING_USER_ID for m in channel.members)
    )


def spiess_is_waiting_in_jerking_target(guild):
    channel = guild.get_channel(JERKING_TARGET_CHANNEL_ID)
    return (
        channel is not None
        and any(
            not m.bot and member_is_spiess(m)
            for m in channel.members
        )
    )


def jerking_target_dm_is_running():
    return jerking_target_dm_task is not None and not jerking_target_dm_task.done()


def cancel_jerking_target_dm_task():
    global jerking_target_dm_task
    task = jerking_target_dm_task
    jerking_target_dm_task = None
    if task is not None and not task.done() and task is not asyncio.current_task():
        task.cancel()


async def delete_jerking_target_dm_messages():
    global jerking_target_dm_messages
    messages = list(jerking_target_dm_messages)
    jerking_target_dm_messages.clear()

    for message in messages:
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


async def disconnect_all_spiess_from_jerking_target(guild):
    channel = guild.get_channel(JERKING_TARGET_CHANNEL_ID)
    if channel is None:
        return

    for member in list(channel.members):
        if member.bot or not member_is_spiess(member):
            continue
        try:
            await member.move_to(
                None,
                reason="Jerking-Erinnerung: Nicht jetzt"
            )
        except discord.Forbidden:
            print(f"❌ {member} konnte nicht aus dem Sprachchannel getrennt werden.")
        except discord.HTTPException as e:
            print(f"❌ Fehler beim Trennen von {member}: {e}")


class JerkingTargetNotNowButton(discord.ui.Button):
    def __init__(self, message_type):
        super().__init__(
            label="Nicht jetzt",
            style=discord.ButtonStyle.secondary,
            custom_id=f"jerking_target_dm:not_now:{message_type}"
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != JERKING_USER_ID:
            await interaction.response.send_message(
                "❌ Dieser Button ist nicht für dich.",
                ephemeral=True
            )
            return

        guild = bot.get_guild(GUILD_ID)
        if guild is None:
            await interaction.response.send_message(
                "❌ Der Server konnte nicht gefunden werden.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        # Loop sofort stoppen, dann wartende Spiess-Accounts trennen
        # und anschließend alle zu dieser Erinnerung gehörenden DMs löschen.
        cancel_jerking_target_dm_task()
        await disconnect_all_spiess_from_jerking_target(guild)
        await delete_jerking_target_dm_messages()


class JerkingTargetDMView(discord.ui.View):
    def __init__(self, message_type):
        super().__init__(timeout=None)

        link_label = "let's go" if message_type == "first" else "tut mir leid 😓"

        self.add_item(DeleteAllDMButton())
        self.add_item(
            discord.ui.Button(
                label=link_label,
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{GUILD_ID}/{JERKING_TARGET_CHANNEL_ID}"
            )
        )
        self.add_item(JerkingTargetNotNowButton(message_type))


async def get_jerking_target_user():
    user = bot.get_user(JERKING_USER_ID)
    if user is not None:
        return user

    try:
        return await bot.fetch_user(JERKING_USER_ID)
    except (discord.NotFound, discord.HTTPException):
        print("❌ JERKING_USER_ID konnte nicht gefunden werden.")
        return None


async def send_jerking_target_dm(content, message_type):
    user = await get_jerking_target_user()
    if user is None:
        return False

    try:
        message = await user.send(
            content,
            view=JerkingTargetDMView(message_type)
        )
        jerking_target_dm_messages.append(message)
        return True
    except discord.Forbidden:
        print("❌ DM an JERKING_USER_ID nicht möglich (DMs möglicherweise deaktiviert).")
        return False
    except discord.HTTPException as e:
        print(f"❌ Fehler beim Senden der DM an JERKING_USER_ID: {e}")
        return False


def build_random_jerking_reminder():
    return (
        "Wie kannst du den spieSS nur so lange warten lassen, du "
        f"{random.choice(ADJEKTIVE)} {random.choice(NOMEN)}💔"
    )


async def jerking_target_reminder_loop(guild):
    global jerking_target_dm_task

    try:
        # Die erste Nachricht wurde bereits beim Join des Spiess gesendet.
        # Vor JEDER Erinnerung einen neuen zufälligen Abstand zwischen
        # 3:47 Minuten und 5:00 Minuten wählen.
        while True:
            delay = get_random_jerking_reminder_interval()
            print(
                f"⏳ Nächste Jerking-Erinnerung in "
                f"{delay // 60}:{delay % 60:02d} Minuten.",
                flush=True
            )
            await asyncio.sleep(delay)

            # Sobald niemand mit Spiess mehr wartet oder der Zieluser da ist: Ende.
            if (
                not spiess_is_waiting_in_jerking_target(guild)
                or jerking_target_is_in_channel(guild)
            ):
                return

            sent = await send_jerking_target_dm(
                build_random_jerking_reminder(),
                "reminder"
            )
            if not sent:
                return

    except asyncio.CancelledError:
        return

    finally:
        if jerking_target_dm_task is asyncio.current_task():
            jerking_target_dm_task = None


async def start_jerking_target_wait(guild):
    global jerking_target_dm_task

    # Nur eine Schleife, auch wenn mehrere Spiess-Accounts den Channel betreten.
    if jerking_target_dm_is_running():
        return

    # Ist JERKING_USER_ID schon da, gibt es nichts zu erinnern.
    if jerking_target_is_in_channel(guild):
        return

    sent = await send_jerking_target_dm(
        "it's jerking time",
        "first"
    )
    if not sent:
        return

    jerking_target_dm_task = asyncio.create_task(
        jerking_target_reminder_loop(guild)
    )
# ==================================================================


# ================== VOICE STATE ==================
@bot.event
async def on_voice_state_update(
    member,
    before,
    after
):

    if member.bot:
        return

    # ==================================================
    # VOICE-EVENTS
    # ==================================================
    joined_channel = (
        after.channel is not None
        and (
            before.channel is None
            or before.channel.id != after.channel.id
        )
    )

    if joined_channel:

        is_spiess = member_is_spiess(member)

        # --------------------------------------------------
        # PRIVATE ERINNERUNG AN BUNKER_USER_ID
        # --------------------------------------------------
        if (
            is_spiess
            and after.channel.id == BUNKER_TARGET_CHANNEL_ID
            and member.id != BUNKER_USER_ID
        ):
            await start_bunker_target_wait(member.guild)

        # BUNKER_USER_ID kommt in den Zielchannel:
        # Loop stoppen und alle bisherigen Erinnerungs-DMs entfernen.
        if (
            member.id == BUNKER_USER_ID
            and after.channel.id == BUNKER_TARGET_CHANNEL_ID
        ):
            cancel_bunker_target_dm_task()
            await delete_bunker_target_dm_messages()

        # --------------------------------------------------
        # PRIVATE ERINNERUNG AN JERKING_USER_ID
        # Ziel ist bewusst die Alte Mühle/JERKING_VOICE_CHANNEL_ID.
        # --------------------------------------------------
        if (
            is_spiess
            and after.channel.id == JERKING_TARGET_CHANNEL_ID
            and member.id != JERKING_USER_ID
        ):
            await start_jerking_target_wait(member.guild)

        # JERKING_USER_ID kommt in den Zielchannel:
        # Loop stoppen und alle bisherigen Erinnerungs-DMs entfernen.
        if (
            member.id == JERKING_USER_ID
            and after.channel.id == JERKING_TARGET_CHANNEL_ID
        ):
            cancel_jerking_target_dm_task()
            await delete_jerking_target_dm_messages()

        # --------------------------------------------------
        # BUNKER
        # --------------------------------------------------
        if (
            member.id == BUNKER_USER_ID
            and after.channel.id == BUNKER_VOICE_CHANNEL_ID
        ):
            if not channel_has_spiess(after.channel):
                await start_private_voice_dm_loop(
                    member.guild,
                    "bunker",
                    BUNKER_VOICE_CHANNEL_ID,
                    BUNKER_MESSAGE
                )

        # --------------------------------------------------
        # JERKING
        # --------------------------------------------------
        if (
            member.id == JERKING_USER_ID
            and after.channel.id == JERKING_VOICE_CHANNEL_ID
        ):
            if not channel_has_spiess(after.channel):
                await start_private_voice_dm_loop(
                    member.guild,
                    "jerking",
                    JERKING_VOICE_CHANNEL_ID,
                    JERKING_MESSAGE
                )

        # Spiess betritt Bunker/Jerking:
        # Nur die zugehörigen privaten DMs aufräumen.
        if is_spiess:

            if after.channel.id == BUNKER_VOICE_CHANNEL_ID:

                # Ein Spiess ist jetzt selbst im Bunker:
                # Loop beenden und private Bunker-DMs bei ALLEN Spiess-Accounts löschen.
                cancel_private_voice_dm_loop("bunker")
                await delete_private_dm_group("bunker")

            elif after.channel.id == JERKING_VOICE_CHANNEL_ID:

                # Ein Spiess ist jetzt selbst in der Alten Mühle:
                # Loop beenden und private Jerking-DMs bei ALLEN Spiess-Accounts löschen.
                cancel_private_voice_dm_loop("jerking")
                await delete_private_dm_group("jerking")

        # --------------------------------------------------
        # BWI-BEREICH
        # --------------------------------------------------
        in_bwi_now = (
            is_bwi_voice_channel(after.channel)
            and after.channel.id in BWI_VOICE_CHANNEL_IDS
        )
        was_in_bwi = (
            is_bwi_voice_channel(before.channel)
            and before.channel.id in BWI_VOICE_CHANNEL_IDS
        )

        if in_bwi_now:
            if is_spiess:
                # Ein Spiess befindet sich jetzt im BWI-Bereich:
                # Private BWI-DMs bei allen Spiess-Accounts löschen.
                await delete_private_dm_group("bwi")
            else:
                # Nur melden, solange KEIN Spiess irgendwo im BWI-Bereich ist.
                spiess_in_bwi = any(
                    member_is_spiess(guild_member)
                    and guild_member.voice is not None
                    and guild_member.voice.channel is not None
                    and guild_member.voice.channel.id in BWI_VOICE_CHANNEL_IDS
                    for guild_member in member.guild.members
                    if not guild_member.bot
                )

                if not spiess_in_bwi:
                    # Privat: Eintritt = neue DM; interner Channelwechsel = vorhandene DM editieren.
                    await send_or_update_bwi_dm(member.guild, member, after.channel)

    # BWI-User verlässt den überwachten Bereich vollständig:
    if (
        before.channel is not None
        and before.channel.id in BWI_VOICE_CHANNEL_IDS
        and (after.channel is None or after.channel.id not in BWI_VOICE_CHANNEL_IDS)
        and not member_is_spiess(member)
    ):
        await clear_bwi_user_tracking(member.id)

    # Wenn ein Spiess den Zielchannel verlässt und danach kein Spiess mehr dort wartet,
    # Loop stoppen. Bereits gesendete DMs bleiben bestehen.
    left_jerking_target = (
        before.channel is not None
        and before.channel.id == JERKING_TARGET_CHANNEL_ID
        and (after.channel is None or after.channel.id != JERKING_TARGET_CHANNEL_ID)
        and member_is_spiess(member)
    )

    if left_jerking_target and not spiess_is_waiting_in_jerking_target(member.guild):
        cancel_jerking_target_dm_task()

    # Wenn der letzte Spiess den Führerbunker verlässt:
    # nur den BUNKER_USER_ID-Erinnerungsloop stoppen.
    # Bereits gesendete DMs bleiben bestehen.
    left_bunker_private_target = (
        before.channel is not None
        and before.channel.id == BUNKER_TARGET_CHANNEL_ID
        and (after.channel is None or after.channel.id != BUNKER_TARGET_CHANNEL_ID)
        and member_is_spiess(member)
    )

    if left_bunker_private_target and not spiess_is_waiting_in_bunker_target(member.guild):
        cancel_bunker_target_dm_task()

    now = datetime.datetime.now(
        datetime.UTC
    )


    if (
        after.channel
        and after.channel.id != TURKEY_CHANNEL_ID
    ):

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
        last_active.pop(
            member.id,
            None
        )
# ==================================================


# ================== AFK CHECK ==================
@tasks.loop(minutes=5)
async def check_inactivity():

    now = datetime.datetime.now(
        datetime.UTC
    )

    turkey_channel = bot.get_channel(
        TURKEY_CHANNEL_ID
    )


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

                    last_active[
                        member.id
                    ] = now

                    continue


                if is_speaking(member):

                    last_active[
                        member.id
                    ] = now

                    continue


                inaktiv_seit = (
                    now
                    - last_active[member.id]
                ).total_seconds()


                if (
                    inaktiv_seit
                    > INACTIVITY_TIME
                ):

                    try:

                        await member.move_to(
                            turkey_channel
                        )

                        print(
                            f"→ {member.name} wurde "
                            f"in die Türkei geschoben "
                            f"(inaktiv seit "
                            f"{inaktiv_seit/60:.0f} min)"
                        )

                    except Exception as e:

                        print(
                            f"Fehler beim Verschieben "
                            f"von {member.name}: {e}"
                        )
# ==================================================


# ================== DM-LÖSCHUNG ÜBER MÜLLEIMER ==================
# Der 🗑️-Button löscht ausschließlich Nachrichten dieses Bots.
# - normaler Nutzer: nur die Bot-Nachrichten in seinem DM
# - Spiess: Bot-Nachrichten in den DMs aller Spiess-Accounts
#
# Strategie:
# 1. Zuerst bekannte, noch im RAM gespeicherte Message-Objekte gezielt löschen.
# 2. Danach den DM-Verlauf als Fallback nach älteren Bot-Nachrichten durchsuchen.
# 3. Zwischen DELETEs bewusst 1 Sekunde warten, um Rate-Limits zu vermeiden.
# 4. Fortschritt sofort im systemd-Journal ausgeben.

DM_DELETE_DELAY = 1.0


async def user_is_spiess_by_id(user_id):
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        return False

    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return False

    return member_is_spiess(member)


async def get_all_spiess_users():
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        return []

    members = list(guild.members)

    try:
        fetched = [member async for member in guild.fetch_members(limit=None)]
        by_id = {member.id: member for member in members}
        by_id.update({member.id: member for member in fetched})
        members = list(by_id.values())
    except (discord.Forbidden, discord.HTTPException):
        pass

    return [
        member
        for member in members
        if not member.bot and member_is_spiess(member)
    ]


def get_tracked_dm_messages_for_user(user_id):
    """
    Sammelt alle aktuell im RAM bekannten Bot-DMs für genau diesen Empfänger.
    Doppelte Message-Objekte werden über ihre Message-ID entfernt.
    """
    messages = {}

    for group in private_dm_messages.values():
        for message in group.get(user_id, []):
            if message is not None:
                messages[message.id] = message

    for (recipient_id, _watched_member_id), message in bwi_user_dm_messages.items():
        if recipient_id == user_id and message is not None:
            messages[message.id] = message

    # Diese beiden Listen gehen an feste Zieluser.
    if user_id == JERKING_USER_ID:
        for message in jerking_target_dm_messages:
            if message is not None:
                messages[message.id] = message

    if user_id == BUNKER_USER_ID:
        for message in bunker_dm_messages:
            if message is not None:
                messages[message.id] = message

    return list(messages.values())


def clear_dm_tracking_for_user(user_id):
    """Entfernt nur die RAM-Referenzen, die zu diesem Empfänger gehören."""
    for group in private_dm_messages.values():
        group.pop(user_id, None)

    for key in list(bwi_user_dm_messages):
        if key[0] == user_id:
            bwi_user_dm_messages.pop(key, None)

    if user_id == JERKING_USER_ID:
        jerking_target_dm_messages.clear()

    if user_id == BUNKER_USER_ID:
        bunker_dm_messages.clear()


async def delete_bot_dm_messages_for_user(user):
    """
    Löscht ausschließlich Nachrichten dieses Bots im DM mit `user`.

    Zuerst werden bekannte Message-Objekte direkt gelöscht.
    Danach wird die History nach älteren, nicht mehr getrackten Bot-DMs durchsucht.
    """
    print(f"🧹 DM-Bereinigung gestartet: {user}", flush=True)

    deleted_ids = set()
    deleted_tracked = 0
    deleted_history = 0

    # ----------------------------------------------------------
    # 1. Bekannte / aktuell getrackte Nachrichten
    # ----------------------------------------------------------
    tracked_messages = get_tracked_dm_messages_for_user(user.id)

    print(
        f"📌 {user}: {len(tracked_messages)} gespeicherte Bot-Nachricht(en) gefunden.",
        flush=True
    )

    for index, tracked_message in enumerate(tracked_messages, start=1):
        try:
            await tracked_message.delete()
            deleted_ids.add(tracked_message.id)
            deleted_tracked += 1

            print(
                f"🗑️ {user}: gespeichert {index}/{len(tracked_messages)} gelöscht.",
                flush=True
            )

            await asyncio.sleep(DM_DELETE_DELAY)

        except discord.NotFound:
            # Schon weg = für den Fallback nicht erneut relevant.
            deleted_ids.add(tracked_message.id)

        except discord.Forbidden:
            print(
                f"❌ {user}: gespeicherte DM {tracked_message.id} darf nicht gelöscht werden.",
                flush=True
            )

        except discord.HTTPException as e:
            print(
                f"❌ {user}: Fehler bei gespeicherter DM {tracked_message.id}: {e}",
                flush=True
            )

    # Tracker jetzt aufräumen. Die History unten findet eventuell noch ältere DMs.
    clear_dm_tracking_for_user(user.id)

    # ----------------------------------------------------------
    # 2. History-Fallback für ältere Nachrichten
    # ----------------------------------------------------------
    try:
        dm = user.dm_channel
        if dm is None:
            dm = await user.create_dm()

        print(f"🔎 {user}: suche nach älteren Bot-Nachrichten ...", flush=True)

        async for old_message in dm.history(limit=None, oldest_first=False):
            if bot.user is None or old_message.author.id != bot.user.id:
                continue

            # Falls Discord eine eben gelöschte Nachricht noch kurz liefert:
            if old_message.id in deleted_ids:
                continue

            try:
                await old_message.delete()
                deleted_ids.add(old_message.id)
                deleted_history += 1

                print(
                    f"🗑️ {user}: alte Bot-Nachricht #{deleted_history} gelöscht.",
                    flush=True
                )

                await asyncio.sleep(DM_DELETE_DELAY)

            except discord.NotFound:
                deleted_ids.add(old_message.id)

            except discord.Forbidden:
                print(
                    f"❌ {user}: alte DM {old_message.id} darf nicht gelöscht werden.",
                    flush=True
                )

            except discord.HTTPException as e:
                print(
                    f"❌ {user}: Fehler bei alter DM {old_message.id}: {e}",
                    flush=True
                )

    except discord.Forbidden:
        print(
            f"❌ {user}: DM-Verlauf ist für den Bot nicht zugänglich.",
            flush=True
        )

    except discord.HTTPException as e:
        print(
            f"❌ {user}: DM-Verlauf konnte nicht geladen werden: {e}",
            flush=True
        )

    total = deleted_tracked + deleted_history

    print(
        f"✅ {user}: fertig — {total} Bot-Nachricht(en) gelöscht "
        f"({deleted_tracked} gespeichert, {deleted_history} aus Verlauf).",
        flush=True
    )

    return total


async def delete_dm_for_trigger_user(trigger_user, source="🗑️"):
    """
    Löschlogik für den 🗑️-Button.
    Spiess -> alle Spiess-DMs, sonst nur der eigene DM.
    """
    trigger_is_spiess = await user_is_spiess_by_id(trigger_user.id)

    if trigger_is_spiess:
        targets = await get_all_spiess_users()

        target_ids = {user.id for user in targets}
        if trigger_user.id not in target_ids:
            targets.append(trigger_user)

        print(
            f"🧹 {source} von Spiess {trigger_user}: "
            f"{len(targets)} Spiess-Account(s) werden bereinigt.",
            flush=True
        )
    else:
        targets = [trigger_user]
        print(
            f"🧹 {source} von {trigger_user}: nur dieser DM-Chat wird bereinigt.",
            flush=True
        )

    total_deleted = 0
    for target in targets:
        total_deleted += await delete_bot_dm_messages_for_user(target)

    print(
        f"🏁 DM-Löschung komplett fertig: {total_deleted} Bot-Nachricht(en) gelöscht.",
        flush=True
    )

    return total_deleted


class DeleteAllDMButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            emoji="🗑️",
            style=discord.ButtonStyle.danger,
            custom_id="private_dm:delete_all_bot_messages"
        )

    async def callback(self, interaction: discord.Interaction):
        # Nur in privaten Nachrichten verwenden.
        if interaction.guild is not None:
            await interaction.response.send_message(
                "❌ Dieser Button ist nur für private Nachrichten gedacht.",
                ephemeral=True
            )
            return

        # Sofort bestätigen, bevor die Nachricht mit diesem Button gelöscht wird.
        await interaction.response.defer()

        await delete_dm_for_trigger_user(
            interaction.user,
            source="🗑️"
        )


class DeleteAllDMView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DeleteAllDMButton())



# ============================================================


# ================== BOT START ==================
bot.run(
    os.getenv("DISCORD_TOKEN")
)
# ================================================
