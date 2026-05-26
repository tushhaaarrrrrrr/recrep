import discord
from discord import app_commands
from discord.ext import commands
from services.db_service import DBService
from utils.helpers import upload_attachments, validate_text_field
from utils.views import ApprovalView
from utils.form_embeds import build_submission_embed
from utils.logger import get_logger
from config.forms import FORM_TABLE_PREFIX, FormStatus, display_id as make_display_id

logger = get_logger(__name__)

class DemolitionCog(commands.Cog):
    """Commands for submitting demolition reports and admin demolition requests."""


    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="report_demolition",
        description="Submit a demolition report after removing a player's plots"
    )
    @app_commands.describe(
        ingame_username="Minecraft username of the player whose plots were demolished",
        removed="Status: `yes` (removed) or `tbd`",
        stashed_items="Were items moved to town storage? `yes` or `no`",
        screenshot1="Screenshot evidence (at least one required)",
        screenshot2="Additional screenshot (optional)",
        screenshot3="Additional screenshot (optional)",
        screenshot4="Additional screenshot (optional)",
        screenshot5="Additional screenshot (optional)"
    )
    async def demolition_submit(
        self,
        interaction: discord.Interaction,
        ingame_username: str,
        removed: str,
        stashed_items: str,
        screenshot1: discord.Attachment = None,
        screenshot2: discord.Attachment = None,
        screenshot3: discord.Attachment = None,
        screenshot4: discord.Attachment = None,
        screenshot5: discord.Attachment = None
    ):
        try:
            await interaction.response.defer()
        except (discord.NotFound, discord.HTTPException):
            return

        try:
            for err in filter(None, [
                validate_text_field(ingame_username, 'In-game Username', 32),
                validate_text_field(removed, 'Removed', 32),
                validate_text_field(stashed_items, 'Town Storage Status', 16),
            ]):
                await interaction.followup.send(f'❌ {err}', ephemeral=True)
                return
            if removed.strip().lower() not in {'yes', 'no', 'tbd'}:
                await interaction.followup.send('❌ **Removed** must be `yes`, `no`, or `tbd`.', ephemeral=True)
                return
            if stashed_items.strip().lower() not in {'yes', 'no'}:
                await interaction.followup.send('❌ **Items Stashed** must be `yes` or `no`.', ephemeral=True)
                return
            screenshot_urls = await upload_attachments(
                interaction,
                screenshot1,
                screenshot2,
                screenshot3,
                screenshot4,
                screenshot5,
            )
            if screenshot_urls is None:
                return

            data = {
                'submitted_by': interaction.user.id,
                'submitter_display': interaction.user.display_name,
                'ingame_username': ingame_username,
                'removed': removed,
                'stashed_items': stashed_items.lower() == 'yes',
                'screenshot_urls': ','.join(screenshot_urls)
            }

            form_id = await DBService.insert_demolition(data)
            logger.info(f"Demolition report #{form_id} submitted by {interaction.user.id}")

            form_data = {
                'ingame_username': ingame_username,
                'removed': removed,
                'stashed_items': stashed_items.lower() == 'yes',
                'screenshot_urls': data['screenshot_urls']
            }

            display_id = make_display_id("demolition_report", form_id)

            confirm_msg = await interaction.followup.send(f"✅ Demolition report `{display_id}` submitted - pending approval.")

            config = await DBService.get_guild_config(interaction.guild_id)
            if config and config.get('approval_channel_id'):
                approval_channel = self.bot.get_channel(config['approval_channel_id'])
                if approval_channel:
                    embed = build_submission_embed('demolition_report', form_data, form_id=form_id, submitter_name=interaction.user.display_name)

                    view = ApprovalView(
                        table='demolition_report',
                        form_id=form_id,
                        form_type='demolition_report',
                        submitter_id=interaction.user.id,
                        guild_id=interaction.guild_id,
                        channel_config_key='demolition_channel_id',
                        thread_prefix="Demolitions",
                        confirmation_msg_id=confirm_msg.id,
                        confirmation_channel_id=interaction.channel_id,
                        form_data=form_data
                    )
                    msg = await approval_channel.send(embed=embed, view=view)
                    await DBService.set_approval_message_id('demolition_report', form_id, msg.id)

                    # Persist confirmation message IDs so they can be cleaned up later
                    await DBService.execute(
                        "UPDATE demolition_report SET confirmation_msg_id = $1, confirmation_channel_id = $2 WHERE id = $3",
                        confirm_msg.id, interaction.channel_id, form_id
                    )

        except Exception as e:
            logger.exception("Error in demolition_submit")
            await interaction.followup.send(
                "❌ An error occurred while submitting the report. Please try again later.",
                ephemeral=True
            )

    @app_commands.command(
        name="request_demolition",
        description="[Admin] Request demolition of a player's plots"
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        ingame_username="Minecraft username of the player whose plots should be demolished",
        reason="Reason for the demolition request (e.g., inactivity, violation)",
        screenshot1="Screenshot evidence (at least one required)",
        screenshot2="Additional screenshot (optional)",
        screenshot3="Additional screenshot (optional)",
        screenshot4="Additional screenshot (optional)",
        screenshot5="Additional screenshot (optional)"
    )
    async def demolition_request(
        self,
        interaction: discord.Interaction,
        ingame_username: str,
        reason: str,
        screenshot1: discord.Attachment = None,
        screenshot2: discord.Attachment = None,
        screenshot3: discord.Attachment = None,
        screenshot4: discord.Attachment = None,
        screenshot5: discord.Attachment = None
    ):
        try:
            await interaction.response.defer()
        except (discord.NotFound, discord.HTTPException):
            return

        try:
            for err in filter(None, [
                validate_text_field(ingame_username, 'In-game Username', 32),
                validate_text_field(removed, 'Removed', 32),
                validate_text_field(stashed_items, 'Town Storage Status', 16),
            ]):
                await interaction.followup.send(f'❌ {err}', ephemeral=True)
                return
            if removed.strip().lower() not in {'yes', 'no', 'tbd'}:
                await interaction.followup.send('❌ **Removed** must be `yes`, `no`, or `tbd`.', ephemeral=True)
                return
            if stashed_items.strip().lower() not in {'yes', 'no'}:
                await interaction.followup.send('❌ **Items Stashed** must be `yes` or `no`.', ephemeral=True)
                return
            screenshot_urls = await upload_attachments(
                interaction,
                screenshot1,
                screenshot2,
                screenshot3,
                screenshot4,
                screenshot5,
            )
            if screenshot_urls is None:
                return

            data = {
                'submitted_by': interaction.user.id,
                'submitter_display': interaction.user.display_name,
                'ingame_username': ingame_username,
                'reason': reason,
                'screenshot_urls': ','.join(screenshot_urls),
                'status': FormStatus.PENDING
            }

            form_id = await DBService.insert_demolition_request(data)
            logger.info(f"Demolition request #{form_id} submitted by admin {interaction.user.id}")

            form_data = {
                'ingame_username': ingame_username,
                'reason': reason,
                'screenshot_urls': data['screenshot_urls']
            }

            display_id = make_display_id('demolition_request', form_id)

            confirm_msg = await interaction.followup.send(f"📢 Demolition request `{display_id}` submitted - pending admin review.")

            config = await DBService.get_guild_config(interaction.guild_id)
            if config and config.get('approval_channel_id'):
                approval_channel = self.bot.get_channel(config['approval_channel_id'])
                if approval_channel:
                    embed = build_submission_embed('demolition_request', form_data, form_id=form_id, submitter_name=interaction.user.display_name)
                    view = ApprovalView(
                        table='demolition_request',
                        form_id=form_id,
                        form_type='demolition_request',
                        submitter_id=interaction.user.id,
                        guild_id=interaction.guild_id,
                        channel_config_key='demolition_channel_id',
                        thread_prefix="Demolition Requests",
                        confirmation_msg_id=confirm_msg.id,
                        confirmation_channel_id=interaction.channel_id,
                        form_data=form_data
                    )
                    msg = await approval_channel.send(embed=embed, view=view)
                    await DBService.set_approval_message_id('demolition_request', form_id, msg.id)

                    # Persist confirmation message IDs
                    await DBService.execute(
                        "UPDATE demolition_request SET confirmation_msg_id = $1, confirmation_channel_id = $2 WHERE id = $3",
                        confirm_msg.id, interaction.channel_id, form_id
                    )

        except Exception as e:
            logger.exception("Error in demolition_request")
            await interaction.followup.send(
                "❌ An error occurred while submitting the request. Please try again later.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(DemolitionCog(bot))