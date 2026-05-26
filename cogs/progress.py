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

class ProgressCog(commands.Cog):
    """Commands for submitting progress reports on building projects."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="report_progress",
        description="Submit a progress report for a building project"
    )
    @app_commands.describe(
        project_name="Name of the project (e.g., 'Town Hall', 'Mob Farm')",
        time_spent="Time spent on the project (e.g., '2 hours', '30 minutes')",
        note="Optional note for extra context, blockers, or updates",
        helper="Optional: mention a user who helped (they will also receive reputation)",
        screenshot1="Screenshot evidence (at least one required)",
        screenshot2="Additional screenshot (optional)",
        screenshot3="Additional screenshot (optional)",
        screenshot4="Additional screenshot (optional)",
        screenshot5="Additional screenshot (optional)"
    )
    async def progress_submit(
        self,
        interaction: discord.Interaction,
        project_name: str,
        time_spent: str,
        note: str = None,
        helper: str = None,
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
                validate_text_field(project_name, 'Project Name', 120),
                validate_text_field(time_spent, 'Time Spent', 40),
                validate_text_field(note, 'Note', 1000) if note else None,
                validate_text_field(helper, 'Helper', 120) if helper else None,
            ]):
                await interaction.followup.send(f'❌ {err}', ephemeral=True)
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
                'helper_mentions': helper,
                'project_name': project_name,
                'time_spent': time_spent,
                'note': note,
                'screenshot_urls': ','.join(screenshot_urls)
            }

            form_id = await DBService.insert_progress(data)
            logger.info(f"Progress report #{form_id} submitted by {interaction.user.id}")

            form_data = {
                'project_name': project_name,
                'time_spent': time_spent,
                'note': note,
                'helper_mentions': helper,
                'screenshot_urls': data['screenshot_urls']
            }

            display_id = make_display_id("progress_report", form_id)

            confirm_msg = await interaction.followup.send(f"✅ Submitted · {display_id}\nYour progress report is pending review.")

            config = await DBService.get_guild_config(interaction.guild_id)
            if config and config.get('approval_channel_id'):
                approval_channel = self.bot.get_channel(config['approval_channel_id'])
                if approval_channel:
                    embed = build_submission_embed('progress_report', form_data, form_id=form_id, submitter_name=interaction.user.display_name)

                    view = ApprovalView(
                        table='progress_report',
                        form_id=form_id,
                        form_type='progress_report',
                        submitter_id=interaction.user.id,
                        guild_id=interaction.guild_id,
                        channel_config_key='progress_channel_id',
                        thread_prefix="Progress Reports",
                        confirmation_msg_id=confirm_msg.id,
                        confirmation_channel_id=interaction.channel_id,
                        form_data=form_data
                    )
                    msg = await approval_channel.send(embed=embed, view=view)
                    await DBService.set_form_message_ids('progress_report', form_id, msg.id, confirm_msg.id, interaction.channel_id)

        except Exception as e:
            logger.exception("Error in progress_submit")
            await interaction.followup.send(
                "❌ We could not submit your progress report right now. Please try again shortly.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ProgressCog(bot))
