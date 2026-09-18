import discord
from discord.ext import commands, tasks
import datetime
import os
import asyncio
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


# Voice-Benachrichtigungen
VOICE_NOTIFICATION_CHANNEL_ID = 1506982204700360767
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

# BWI-Voice-Bereich (Discord-Kategorie)
BWI_VOICE_CATEGORY_ID = 1486612928584093706
BWI_NOTIFICATION_PREFIX = "BWI-Bereich beigetreten"


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


# ================== VOICE-BENACHRICHTIGUNGS-TIMER ==================
# Pro Benachrichtigung kann ein eigener 3-Minuten-Timer laufen.
voice_notification_timers = {
    BUNKER_VOICE_CHANNEL_ID: set(),
    JERKING_VOICE_CHANNEL_ID: set(),
}
# ===================================================================


# ================== PRIVATE BUNKER-DM ==================
# Eigener Task: unabhängig vom 60-Sekunden-Admin-Timer.
bunker_dm_task = None
bunker_dm_messages = []
# =======================================================


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
        bot.add_view(ClearNotificationView("bunker"))
        bot.add_view(ClearNotificationView("jerking"))
        bot.add_view(ClearNotificationView("bwi"))
        bot.add_view(BunkerDMView())
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


# ================== VOICE-BENACHRICHTIGUNGEN ==================
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


async def delete_voice_notifications(guild, notification_type):
    notification_channel = guild.get_channel(
        VOICE_NOTIFICATION_CHANNEL_ID
    )

    if notification_channel is None:
        print(
            f"❌ Benachrichtigungs-Channel mit ID "
            f"{VOICE_NOTIFICATION_CHANNEL_ID} wurde nicht gefunden."
        )
        return

    try:
        async for message in notification_channel.history(limit=None):
            if message.author.id != bot.user.id:
                continue

            should_delete = False

            if notification_type == "bunker":
                should_delete = message.content == BUNKER_MESSAGE

            elif notification_type == "jerking":
                should_delete = message.content == JERKING_MESSAGE

            elif notification_type == "bwi":
                should_delete = (
                    message.content.startswith("<@")
                    and message.content.endswith(
                        f" ist dem {BWI_NOTIFICATION_PREFIX}"
                    )
                )

            if should_delete:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass

    except discord.Forbidden:
        print(
            "❌ Bot kann die Voice-Benachrichtigungen "
            "nicht lesen oder löschen."
        )

    except discord.HTTPException as e:
        print(
            f"❌ Fehler beim Löschen der Voice-Benachrichtigungen: {e}"
        )


class ClearNotificationButton(discord.ui.Button):
    def __init__(self, notification_type):
        labels = {
            "bunker": "✓ Gesehen",
            "jerking": "✓ Gesehen",
            "bwi": "✓ Gesehen",
        }

        super().__init__(
            label=labels[notification_type],
            style=discord.ButtonStyle.secondary,
            custom_id=f"clear_voice_notifications:{notification_type}"
        )

        self.notification_type = notification_type

    async def callback(self, interaction: discord.Interaction):
        # Die beiden Minuten-Timer müssen beim manuellen Bestätigen
        # ebenfalls beendet werden, sonst käme die Meldung erneut.
        if self.notification_type == "bunker":
            cancel_voice_notification_timers(
                BUNKER_VOICE_CHANNEL_ID
            )

        elif self.notification_type == "jerking":
            cancel_voice_notification_timers(
                JERKING_VOICE_CHANNEL_ID
            )

        await interaction.response.defer()

        await delete_voice_notifications(
            interaction.guild,
            self.notification_type
        )


class ClearNotificationView(discord.ui.View):
    def __init__(self, notification_type):
        # timeout=None + feste custom_id = persistenter Button
        super().__init__(timeout=None)
        self.add_item(
            ClearNotificationButton(notification_type)
        )


async def send_voice_notification(
    guild,
    message_text,
    notification_type
):
    notification_channel = guild.get_channel(
        VOICE_NOTIFICATION_CHANNEL_ID
    )

    if notification_channel is None:
        print(
            f"❌ Benachrichtigungs-Channel mit ID "
            f"{VOICE_NOTIFICATION_CHANNEL_ID} wurde nicht gefunden."
        )
        return

    try:
        await notification_channel.send(
            message_text,
            view=ClearNotificationView(notification_type)
        )

    except discord.Forbidden:
        print(
            "❌ Bot kann keine Voice-Benachrichtigung senden."
        )

    except discord.HTTPException as e:
        print(
            f"❌ Fehler beim Senden der Voice-Benachrichtigung: {e}"
        )


async def repeat_voice_notification_after_delay(
    guild,
    voice_channel_id,
    message_text,
    notification_type
):
    try:
        while True:
            # Nach jeder Meldung 1 Minute warten.
            await asyncio.sleep(60)

            # Solange kein Spiess den zugehörigen Voice-Channel
            # betritt und den Task abbricht, erneut benachrichtigen.
            await send_voice_notification(
                guild,
                message_text,
                notification_type
            )

    except asyncio.CancelledError:
        return


def start_voice_notification_timer(
    guild,
    voice_channel_id,
    message_text,
    notification_type
):
    task = asyncio.create_task(
        repeat_voice_notification_after_delay(
            guild,
            voice_channel_id,
            message_text,
            notification_type
        )
    )

    voice_notification_timers.setdefault(
        voice_channel_id,
        set()
    ).add(task)

    task.add_done_callback(
        lambda finished_task: voice_notification_timers
        .get(voice_channel_id, set())
        .discard(finished_task)
    )


def cancel_voice_notification_timers(voice_channel_id):
    for task in list(
        voice_notification_timers.get(
            voice_channel_id,
            set()
        )
    ):
        task.cancel()

    voice_notification_timers.get(
        voice_channel_id,
        set()
    ).clear()
# ===============================================================


# ================== PRIVATE BUNKER-DM FUNKTIONEN ==================
def get_bunker_channel(guild):
    channel = guild.get_channel(BUNKER_VOICE_CHANNEL_ID)
    return channel if isinstance(channel, discord.VoiceChannel) else None


def bunker_has_spiess(guild):
    channel = get_bunker_channel(guild)
    return channel is not None and channel_has_spiess(channel)


def bunker_user_is_in_bunker(guild):
    channel = get_bunker_channel(guild)
    if channel is None:
        return False
    return any(member.id == BUNKER_USER_ID for member in channel.members)


def bunker_dm_is_running():
    return bunker_dm_task is not None and not bunker_dm_task.done()


def cancel_bunker_dm_task():
    global bunker_dm_task
    task = bunker_dm_task
    bunker_dm_task = None

    # Nicht den gerade laufenden Task gegen sich selbst canceln.
    if task is not None and not task.done() and task is not asyncio.current_task():
        task.cancel()


async def delete_bunker_dm_messages():
    global bunker_dm_messages

    messages = list(bunker_dm_messages)
    bunker_dm_messages.clear()

    for message in messages:
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


async def send_bunker_dm():
    user = bot.get_user(BUNKER_USER_ID)

    if user is None:
        try:
            user = await bot.fetch_user(BUNKER_USER_ID)
        except (discord.NotFound, discord.HTTPException):
            print("❌ BUNKER_USER_ID konnte nicht gefunden werden.")
            return False

    try:
        message = await user.send(
            BUNKER_MESSAGE,
            view=BunkerDMView()
        )
        bunker_dm_messages.append(message)
        return True

    except discord.Forbidden:
        print("❌ Bunker-DM konnte nicht gesendet werden (DMs möglicherweise deaktiviert).")
        return False

    except discord.HTTPException as e:
        print(f"❌ Fehler beim Senden der Bunker-DM: {e}")
        return False


async def repeat_bunker_dm(guild):
    global bunker_dm_task

    try:
        while True:
            # Sicherheitsprüfung vor jeder neuen Nachricht.
            if not bunker_has_spiess(guild) or bunker_user_is_in_bunker(guild):
                return

            sent = await send_bunker_dm()
            if not sent:
                return

            await asyncio.sleep(BUNKER_DM_INTERVAL)

    except asyncio.CancelledError:
        return

    finally:
        if bunker_dm_task is asyncio.current_task():
            bunker_dm_task = None


def start_bunker_dm_task(guild):
    global bunker_dm_task

    # Egal wie viele Spieße joinen: maximal EIN Task.
    if bunker_dm_is_running():
        return

    # Falls der Bunker-User schon drin ist, gibt es nichts zu melden.
    if bunker_user_is_in_bunker(guild):
        return

    bunker_dm_task = asyncio.create_task(
        repeat_bunker_dm(guild)
    )


async def disconnect_all_spiess_from_bunker(guild):
    channel = get_bunker_channel(guild)
    if channel is None:
        return

    spiess_members = [
        member
        for member in list(channel.members)
        if not member.bot and member_is_spiess(member)
    ]

    for member in spiess_members:
        try:
            await member.move_to(
                None,
                reason="Bunkerzeit: Nicht jetzt"
            )
        except discord.Forbidden:
            print(f"❌ {member} konnte nicht aus dem Führerbunker getrennt werden.")
        except discord.HTTPException as e:
            print(f"❌ Fehler beim Trennen von {member}: {e}")


class BunkerNotNowButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Nicht jetzt",
            style=discord.ButtonStyle.secondary,
            custom_id="bunker_dm:not_now"
        )

    async def callback(self, interaction: discord.Interaction):
        # Nur der konfigurierte Bunker-User darf die Aktion auslösen.
        if interaction.user.id != BUNKER_USER_ID:
            await interaction.response.send_message(
                "❌ Dieser Button ist nicht für dich.",
                ephemeral=True
            )
            return

        # Bei DMs ist interaction.guild None, deshalb den Server über die feste ID holen.
        guild = bot.get_guild(GUILD_ID)
        if guild is None:
            await interaction.response.send_message(
                "❌ Der Server konnte nicht gefunden werden.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        # Zuerst stoppen, damit während des Aufräumens keine neue DM entsteht.
        cancel_bunker_dm_task()

        # Danach alle Spieße aus dem Führerbunker trennen.
        await disconnect_all_spiess_from_bunker(guild)

        # Zum Schluss alle von dieser Funktion gespeicherten Bunkerzeit-DMs löschen.
        await delete_bunker_dm_messages()


class BunkerDMView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        # Link-Button: öffnet direkt den Führerbunker in Discord.
        self.add_item(
            discord.ui.Button(
                label="Zum Bunker",
                style=discord.ButtonStyle.link,
                url=(
                    f"https://discord.com/channels/"
                    f"{GUILD_ID}/{BUNKER_VOICE_CHANNEL_ID}"
                )
            )
        )

        self.add_item(BunkerNotNowButton())
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
    # VOICE-BENACHRICHTIGUNGEN
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
        # PRIVATE BUNKER-DM
        # --------------------------------------------------
        # Bunker-User betritt selbst den Führerbunker:
        # private 30-Sekunden-Schleife stoppen + bisherige DMs löschen.
        if (
            member.id == BUNKER_USER_ID
            and after.channel.id == BUNKER_VOICE_CHANNEL_ID
        ):
            cancel_bunker_dm_task()
            await delete_bunker_dm_messages()

        # --------------------------------------------------
        # BUNKER
        # --------------------------------------------------
        if (
            member.id == BUNKER_USER_ID
            and after.channel.id == BUNKER_VOICE_CHANNEL_ID
        ):
            if not channel_has_spiess(after.channel):
                await send_voice_notification(
                    member.guild,
                    BUNKER_MESSAGE,
                    "bunker"
                )
                start_voice_notification_timer(
                    member.guild,
                    BUNKER_VOICE_CHANNEL_ID,
                    BUNKER_MESSAGE,
                    "bunker"
                )

        # --------------------------------------------------
        # JERKING
        # --------------------------------------------------
        if (
            member.id == JERKING_USER_ID
            and after.channel.id == JERKING_VOICE_CHANNEL_ID
        ):
            if not channel_has_spiess(after.channel):
                await send_voice_notification(
                    member.guild,
                    JERKING_MESSAGE,
                    "jerking"
                )
                start_voice_notification_timer(
                    member.guild,
                    JERKING_VOICE_CHANNEL_ID,
                    JERKING_MESSAGE,
                    "jerking"
                )

        # Spiess betritt Bunker/Jerking:
        # Timer stoppen und nur die zugehörigen Meldungen löschen.
        if is_spiess:

            if after.channel.id == BUNKER_VOICE_CHANNEL_ID:
                cancel_voice_notification_timers(
                    BUNKER_VOICE_CHANNEL_ID
                )
                await delete_voice_notifications(
                    member.guild,
                    "bunker"
                )

                # Unabhängig davon private Bunker-DM starten.
                # start_bunker_dm_task verhindert doppelte Schleifen automatisch.
                start_bunker_dm_task(member.guild)

            elif after.channel.id == JERKING_VOICE_CHANNEL_ID:
                cancel_voice_notification_timers(
                    JERKING_VOICE_CHANNEL_ID
                )
                await delete_voice_notifications(
                    member.guild,
                    "jerking"
                )

        # --------------------------------------------------
        # BWI-BEREICH
        # Nur beim Eintritt von außerhalb in die BWI-Kategorie.
        # Wechsel zwischen zwei Voice-Channels derselben Kategorie
        # erzeugt keine zusätzliche Meldung.
        # --------------------------------------------------
        entered_bwi_area = (
            is_bwi_voice_channel(after.channel)
            and not is_bwi_voice_channel(before.channel)
        )

        if entered_bwi_area:

            if is_spiess:
                # Ein Spiess betritt den BWI-Bereich:
                # alle offenen BWI-Meldungen auf einmal löschen.
                await delete_voice_notifications(
                    member.guild,
                    "bwi"
                )

            else:
                # Keine Wiederholung / kein Minuten-Timer für BWI.
                await send_voice_notification(
                    member.guild,
                    f"{member.mention} ist dem BWI-Bereich beigetreten",
                    "bwi"
                )

    # --------------------------------------------------
    # LETZTER SPIESS VERLÄSST DEN FÜHRERBUNKER
    # --------------------------------------------------
    # Dann nur die private 30-Sekunden-Schleife stoppen.
    # Bereits gesendete DMs bleiben absichtlich bestehen.
    left_bunker = (
        before.channel is not None
        and before.channel.id == BUNKER_VOICE_CHANNEL_ID
        and (
            after.channel is None
            or after.channel.id != BUNKER_VOICE_CHANNEL_ID
        )
    )

    if left_bunker and member_is_spiess(member):
        bunker_channel = member.guild.get_channel(BUNKER_VOICE_CHANNEL_ID)

        if (
            bunker_channel is not None
            and not channel_has_spiess(bunker_channel)
        ):
            cancel_bunker_dm_task()

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


# ================== BOT START ==================
bot.run(
    os.getenv("DISCORD_TOKEN")
)
# ================================================
