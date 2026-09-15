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

bot = commands.Bot(command_prefix="!", intents=intents)
# =======================================================


# ================== EINSTELLUNGEN ==================

# AFK / Türkei
TURKEY_CHANNEL_ID = 1486631386533199872

EXCLUDED_ROLE_IDS = [
    1486571017806811228,
    1486560941368803389
]

INACTIVITY_TIME = 45 * 60


# BWI
BWI_ROLE_ID = 1486613262953877645


# Admin-Channel für Rollenvergabe
ADMIN_ROLE_CHANNEL_ID = 1549364249317351434


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
    {"label": "Asyl", "role_id": 1486571017806811228},
    {"label": "Vanilla", "role_id": 1486551681490747483},
    {"label": "Jobcenter", "role_id": 1486553099475615856},
    {"label": "Ratsmitglied", "role_id": 1486552582397759499},
    {"label": "Abschiebeamt", "role_id": 1486552799834673194},
    {"label": "Sounds und Nickname", "role_id": 1486554277697556480},
]

# ============================================================


# ================== AFK DATEN ==================
last_active = {}
# ================================================


# ================== INVITE CACHE ==================
invite_cache = {}
# ==================================================


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


# ================== VOICE STATE ==================
@bot.event
async def on_voice_state_update(
    member,
    before,
    after
):

    if member.bot:
        return

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
