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

class ScrollCog(commands.Cog):
    """Commands for submitting scroll completion reports."""

    _VALID_SCROLL_TYPES = ['common', 'special', 'epic', 'mythic', 'legendary', 'mystery', 'spawn_egg']

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="report_scroll",
        description="Submit a scroll completion report"
    )
    @app_commands.describe(
        scroll_type="Type of scroll completed: common, special, epic, mythic, legendary, mystery, spawn_egg",
        items_stored="Were the rewards stored in town storage? (`yes` or `no`)",
        screenshot1="Screenshot evidence (at least one required)",
        screenshot2="Additional screenshot (optional)",
        screenshot3="Additional screenshot (optional)",
        screenshot4="Additional screenshot (optional)",
        screenshot5="Additional screenshot (optional)"
    )
    async def scroll_submit(
        self,
        interaction: discord.Interaction,
        scroll_type: str,
        items_stored: str,
        screenshot1: discord.Attachment,
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
                validate_text_field(scroll_type, 'Scroll Type', 32),
                validate_text_field(items_stored, 'Items Stored', 8),
            ]):
                await interaction.followup.send(f'❌ {err}', ephemeral=True)
                return
            if items_stored.strip().lower() not in {'yes', 'no'}:
                await interaction.followup.send('❌ **Items Stored** must be `yes` or `no`.', ephemeral=True)
                return
            scroll_type_lower = scroll_type.lower()
            if scroll_type_lower not in self._VALID_SCROLL_TYPES:
                valid_list = ", ".join(self._VALID_SCROLL_TYPES)
                await interaction.followup.send(
                    f"❌ Invalid scroll type.\nValid options: `{valid_list}`",
                    ephemeral=True
                )
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
                'scroll_type': scroll_type_lower,
                'items_stored': items_stored.lower() == 'yes',
                'screenshot_urls': ','.join(screenshot_urls)
            }

            form_id = await DBService.insert_scroll(data)
            logger.info(f"Scroll completion report #{form_id} submitted by {interaction.user.id}")

            form_data = {
                'scroll_type': scroll_type_lower,
                'items_stored': items_stored.lower() == 'yes',
                'screenshot_urls': data['screenshot_urls']
            }

            display_id = make_display_id("scroll_completion", form_id)

            confirm_msg = await interaction.followup.send(f"✅ Scroll report `{display_id}` submitted – pending approval.")

            config = await DBService.get_guild_config(interaction.guild_id)
            if config and config.get('approval_channel_id'):
                approval_channel = self.bot.get_channel(config['approval_channel_id'])
                if approval_channel:
                    embed = build_submission_embed('scroll_completion', form_data, form_id=form_id, submitter_name=interaction.user.display_name)

                    view = ApprovalView(
                        table='scroll_completion',
                        form_id=form_id,
                        form_type='scroll_completion',
                        submitter_id=interaction.user.id,
                        guild_id=interaction.guild_id,
                        channel_config_key='scroll_channel_id',
                        thread_prefix="Scrolls",
                        confirmation_msg_id=confirm_msg.id,
                        confirmation_channel_id=interaction.channel_id,
                        form_data=form_data
                    )
                    msg = await approval_channel.send(embed=embed, view=view)
                    await DBService.set_approval_message_id('scroll_completion', form_id, msg.id)

                    # Persist confirmation message IDs
                    await DBService.execute(
                        "UPDATE scroll_completion SET confirmation_msg_id = $1, confirmation_channel_id = $2 WHERE id = $3",
                        confirm_msg.id, interaction.channel_id, form_id
                    )

        except Exception as e:
            logger.exception("Error in scroll_submit")
            await interaction.followup.send(
                "❌ An error occurred while submitting the scroll report. Please try again later.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ScrollCog(bot))