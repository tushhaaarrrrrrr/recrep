import discord
from discord import app_commands
from discord.ext import commands
from services.db_service import DBService
from utils.helpers import upload_attachments, validate_text_field
from utils.views import ApprovalView
from utils.form_embeds import build_submission_embed
from utils.logger import get_logger
from config.forms import display_id as make_display_id

logger = get_logger(__name__)

class EvictionCog(commands.Cog):
    """Commands for submitting eviction reports."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="report_eviction",
        description="Submit an eviction report when a player is evicted due to inactivity or rule violation"
    )
    @app_commands.describe(
        ingame_owner="Minecraft username of the plot owner being evicted",
        items_stored="Were items moved to town storage? `yes` or `no`",
        inactivity_period="How long the player has been inactive (e.g., `3 months`, `45 days`)",
        screenshot1="Screenshot evidence (at least one required)",
        screenshot2="Additional screenshot (optional)",
        screenshot3="Additional screenshot (optional)",
        screenshot4="Additional screenshot (optional)",
        screenshot5="Additional screenshot (optional)"
    )
    async def eviction_submit(
        self,
        interaction: discord.Interaction,
        ingame_owner: str,
        items_stored: str,
        inactivity_period: str,
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
                validate_text_field(ingame_owner, 'In-game Owner', 64),
                validate_text_field(inactivity_period, 'Inactivity Period', 64),
                validate_text_field(items_stored, 'Items Stored', 8),
            ]):
                await interaction.followup.send(f'❌ {err}', ephemeral=True)
                return
            if items_stored.strip().lower() not in {'yes', 'no'}:
                await interaction.followup.send('❌ **Items Stored** must be `yes` or `no`.', ephemeral=True)
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
                'ingame_owner': ingame_owner,
                'items_stored': items_stored.lower() == 'yes',
                'inactivity_period': inactivity_period,
                'screenshot_urls': ','.join(screenshot_urls)
            }

            form_id = await DBService.insert_eviction(data)
            logger.info(f"Eviction report #{form_id} submitted by {interaction.user.id}")

            form_data = {
                'ingame_owner': ingame_owner,
                'items_stored': items_stored.lower() == 'yes',
                'inactivity_period': inactivity_period,
                'screenshot_urls': data['screenshot_urls']
            }

            display_id = make_display_id("eviction_report", form_id)

            confirm_msg = await interaction.followup.send(f"✅ Eviction report `{display_id}` submitted - pending approval.")

            config = await DBService.get_guild_config(interaction.guild_id)
            if config and config.get('approval_channel_id'):
                approval_channel = self.bot.get_channel(config['approval_channel_id'])
                if approval_channel:
                    embed = build_submission_embed('eviction_report', form_data, form_id=form_id, submitter_name=interaction.user.display_name)

                    view = ApprovalView(
                        table='eviction_report',
                        form_id=form_id,
                        form_type='eviction_report',
                        submitter_id=interaction.user.id,
                        guild_id=interaction.guild_id,
                        channel_config_key='eviction_channel_id',
                        thread_prefix="Evictions",
                        confirmation_msg_id=confirm_msg.id,
                        confirmation_channel_id=interaction.channel_id,
                        form_data=form_data
                    )
                    msg = await approval_channel.send(embed=embed, view=view)
                    await DBService.set_approval_message_id('eviction_report', form_id, msg.id)

                    # Persist confirmation message
                    await DBService.execute(
                        "UPDATE eviction_report SET confirmation_msg_id = $1, confirmation_channel_id = $2 WHERE id = $3",
                        confirm_msg.id, interaction.channel_id, form_id
                    )

        except Exception as e:
            logger.exception("Error in eviction_submit")
            await interaction.followup.send(
                "❌ An error occurred while submitting the eviction report. Please try again later.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(EvictionCog(bot))