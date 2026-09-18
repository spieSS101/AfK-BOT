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

# Private Erinnerung an JERKING_USER_ID, wenn ein Spiess im Führerbunker wartet.
JERKING_TARGET_CHANNEL_ID = BUNKER_VOICE_CHANNEL_ID
JERKING_REMINDER_INTERVAL = 5 * 60

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
    "Waschbär", "Wombat", "Seegurke", "Kröte", "Karpfen", "Thunfisch",
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
        bot.add_view(PrivateVoiceDMView("bunker", BUNKER_VOICE_CHANNEL_ID))
        bot.add_view(PrivateVoiceDMView("jerking", JERKING_VOICE_CHANNEL_ID))
        bot.add_view(BWIPrivateDMView(BWI_VOICE_CHANNEL_IDS[1486613172126355546], 1486613172126355546))
        bot.add_view(JerkingTargetDMView("first"))
        bot.add_view(JerkingTargetDMView("reminder"))
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
        # Global für alle Spiess-Accounts:
        # Nur die jeweilige Gruppe löschen; keine User aus Voice-Channels werfen
        # und zukünftige Benachrichtigungen nicht deaktivieren.
        await delete_private_dm_group(self.notification_type)


class PrivateVoiceDMView(discord.ui.View):
    def __init__(self, notification_type, channel_id):
        super().__init__(timeout=None)

        if notification_type == "bunker":
            label = "Zum Bunker"
        else:
            label = "Let's Jerk"

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
        "Wie kannst du spieSS so lange warten lassen, du "
        f"{random.choice(ADJEKTIVE)} {random.choice(NOMEN)}💔"
    )


async def jerking_target_reminder_loop(guild):
    global jerking_target_dm_task

    try:
        # Die erste Nachricht wurde bereits beim Join des Spiess gesendet.
        # Exakt fünf Minuten bis zur ersten randomisierten Erinnerung warten.
        await asyncio.sleep(JERKING_REMINDER_INTERVAL)

        while True:
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

            await asyncio.sleep(JERKING_REMINDER_INTERVAL)

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
        # PRIVATE ERINNERUNG AN JERKING_USER_ID
        # Ziel ist bewusst der Führerbunker/BUNKER_VOICE_CHANNEL_ID.
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
                await send_private_channel_dm_to_spiess(
                    member.guild, "bunker", BUNKER_VOICE_CHANNEL_ID, BUNKER_MESSAGE
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
                await send_private_channel_dm_to_spiess(
                    member.guild, "jerking", JERKING_VOICE_CHANNEL_ID, JERKING_MESSAGE
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

                # Ein Spiess ist jetzt selbst im Bunker:
                # private Bunker-DMs bei ALLEN Spiess-Accounts löschen.
                await delete_private_dm_group("bunker")

            elif after.channel.id == JERKING_VOICE_CHANNEL_ID:
                cancel_voice_notification_timers(
                    JERKING_VOICE_CHANNEL_ID
                )
                await delete_voice_notifications(
                    member.guild,
                    "jerking"
                )

                # Ein Spiess ist jetzt selbst im Jerking-Channel:
                # private Jerking-DMs bei ALLEN Spiess-Accounts löschen.
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
                # Admin-Meldungen UND private BWI-DMs bei allen Spiess-Accounts löschen.
                await delete_voice_notifications(member.guild, "bwi")
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
                    # Admin-Channel nur beim Eintritt von außerhalb.
                    if not was_in_bwi:
                        await send_voice_notification(
                            member.guild,
                            f"{member.mention} ist dem BWI-Bereich beigetreten",
                            "bwi"
                        )

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
        await delete_jerking_target_dm_messages()

    # Wenn der letzte Spiess den Führerbunker verlässt:
    # auch eventuell gespeicherte private Nachrichten an BUNKER_USER_ID löschen.
    left_bunker_private_target = (
        before.channel is not None
        and before.channel.id == BUNKER_VOICE_CHANNEL_ID
        and (after.channel is None or after.channel.id != BUNKER_VOICE_CHANNEL_ID)
        and member_is_spiess(member)
    )

    if left_bunker_private_target:
        bunker_channel = member.guild.get_channel(BUNKER_VOICE_CHANNEL_ID)
        if bunker_channel is not None and not channel_has_spiess(bunker_channel):
            # Bestehende private Spiess-Gruppenmeldungen ebenfalls aufräumen.
            await delete_private_dm_group("bunker")

            # Falls aus der älteren Bunker-Zieluser-Logik noch Nachrichten
            # in bunker_dm_messages gespeichert sind, diese ebenfalls löschen.
            messages = list(bunker_dm_messages)
            bunker_dm_messages.clear()
            for message in messages:
                try:
                    await message.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass

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
