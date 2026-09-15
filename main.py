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
    {
        "label": "BWI",
        "role_id": 1486613262953877645
    },
    {
        "label": "Vanilla",
        "role_id": 1486551681490747483
    },
    {
        "label": "Abschiebeamt",
        "role_id": 1486552799834673194
    },
    {
        "label": "Asyl",
        "role_id": 1486571017806811228
    },
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

class RoleSelect(discord.ui.Select):

    def __init__(self, target_member):

        self.target_member = target_member

        options = []

        for role_data in ADMIN_ASSIGNABLE_ROLES:
            options.append(
                discord.SelectOption(
                    label=role_data["label"],
                    value=str(role_data["role_id"])
                )
            )

        super().__init__(
            placeholder="Rolle(n) auswählen...",
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        # Nur Administratoren dürfen das Menü benutzen
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Du darfst dieses Menü nicht benutzen.",
                ephemeral=True
            )
            return

        # Auswahl speichern
        self.view.selected_role_ids = [
            int(role_id)
            for role_id in self.values
        ]

        # Auswahl wurde gespeichert; keine zusätzliche Nachricht erzeugen.
        # Dadurch bleibt nur der ursprüngliche Bestätigen-Button sichtbar.
        await interaction.response.defer()


class ConfirmRolesButton(discord.ui.Button):

    def __init__(self):
        super().__init__(
            label="Bestätigen",
            style=discord.ButtonStyle.success,
            emoji="✅"
        )

    async def callback(self, interaction: discord.Interaction):

        # Nur Administratoren dürfen bestätigen
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Du darfst diese Rollen nicht vergeben.",
                ephemeral=True
            )
            return

        view = self.view

        if not view.selected_role_ids:
            await interaction.response.send_message(
                "❌ Bitte zuerst mindestens eine Rolle auswählen.",
                ephemeral=True
            )
            return

        member = interaction.guild.get_member(
            view.target_member_id
        )

        if member is None:
            try:
                member = await interaction.guild.fetch_member(
                    view.target_member_id
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

        roles_to_add = []

        for role_id in view.selected_role_ids:

            role = interaction.guild.get_role(role_id)

            if role is not None and role not in member.roles:
                roles_to_add.append(role)

        if not roles_to_add:
            await interaction.response.send_message(
                "ℹ️ Der Benutzer besitzt die ausgewählten Rollen bereits.",
                ephemeral=True
            )
            return

        try:
            await member.add_roles(
                *roles_to_add,
                reason=(
                    f"Admin-Rollenvergabe durch "
                    f"{interaction.user}"
                )
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Der Bot darf mindestens eine dieser Rollen "
                "nicht vergeben. Prüfe die Rollenreihenfolge.",
                ephemeral=True
            )
            return

        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ Discord-Fehler beim Vergeben der Rollen.",
                ephemeral=True
            )
            return

        role_names = ", ".join(
            role.name
            for role in roles_to_add
        )

        # Ursprüngliche Nachricht aktualisieren
        await interaction.response.edit_message(
            content=(
                f"✅ Rollen für {member.mention} vergeben:\n"
                f"**{role_names}**"
            ),
            view=None
        )


class MemberRoleView(discord.ui.View):

    def __init__(self, target_member):
        # 24 Stunden Zeit für die Rollenvergabe
        super().__init__(timeout=86400)

        self.target_member_id = target_member.id
        self.selected_role_ids = []

        self.add_item(
            RoleSelect(target_member)
        )

        self.add_item(
            ConfirmRolesButton()
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
    # 1. ADMIN-NACHRICHT FÜR ROLLENVERGABE
    # ==================================================

    admin_channel = guild.get_channel(
        ADMIN_ROLE_CHANNEL_ID
    )

    if admin_channel is not None:

        try:

            await admin_channel.send(
                content=(
                    f"👤 **Neuer Benutzer:** {member.mention}\n"
                    f"`{member}`\n\n"
                    f"Welche Rolle(n) soll der Benutzer erhalten?"
                ),
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
    # 2. BWI INVITE-VERERBUNG
    # ==================================================

    try:

        current_invites = await guild.invites()

    except discord.Forbidden:

        print(
            f"❌ Invite-Erkennung bei {member} "
            f"nicht möglich."
        )
        return

    except discord.HTTPException as e:

        print(
            f"❌ Discord-Fehler beim Abrufen "
            f"der Invites für {member}: {e}"
        )
        return


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
    invite_cache[guild.id] = {
        invite.code: invite.uses or 0
        for invite in current_invites
    }


    if len(changed_invites) == 0:

        print(
            f"ℹ️ Join erkannt: {member} – "
            f"Invite konnte nicht bestimmt werden."
        )
        return


    if len(changed_invites) > 1:

        print(
            f"⚠️ Join von {member}: "
            f"mehrere veränderte Invites erkannt."
        )
        return


    used_invite = changed_invites[0]

    inviter = used_invite.inviter


    if inviter is None:

        print(
            f"ℹ️ Invite {used_invite.code} "
            f"hat keinen erkennbaren Ersteller."
        )
        return


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

            print(
                f"ℹ️ Einladender {inviter} "
                f"konnte nicht gefunden werden."
            )
            return


    bwi_role = guild.get_role(
        BWI_ROLE_ID
    )


    if bwi_role is None:

        print(
            f"❌ BWI-Rolle mit ID "
            f"{BWI_ROLE_ID} wurde nicht gefunden."
        )
        return


    if bwi_role not in inviter_member.roles:

        print(
            f"ℹ️ {member} wurde von "
            f"{inviter_member} eingeladen. "
            f"Kein BWI vorhanden."
        )
        return


    if bwi_role in member.roles:

        print(
            f"ℹ️ {member} besitzt BWI bereits."
        )
        return


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
