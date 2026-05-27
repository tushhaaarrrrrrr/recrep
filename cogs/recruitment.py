import discord
from discord import app_commands
from discord.ext import commands
from services.db_service import DBService
from utils.helpers import upload_attachments, validate_text_field, validate_numeric_field
from utils.views import ApprovalView
from utils.form_embeds import build_submission_embed
from utils.logger import get_logger
from config.forms import display_id as make_display_id

logger = get_logger(__name__)

class RecruitmentCog(commands.Cog):
    """Commands for submitting recruitment logs."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="recruitment",
        description="Log a new player recruitment into the town"
    )
    @app_commands.describe(
        ingame_username="Minecraft username of the new player",
        nickname="Discord nickname of the new player",
        discord_username="Discord username (optional, e.g., `@player`)",
        age="Player's age (optional)",
        plots="Number of plots given (default: 2)",
        screenshot1="Screenshot evidence (optional)",
        screenshot2="Additional screenshot (optional)",
        screenshot3="Additional screenshot (optional)",
        screenshot4="Additional screenshot (optional)",
        screenshot5="Additional screenshot (optional)"
    )
    async def recruitment_add(
        self,
        interaction: discord.Interaction,
        ingame_username: str,
        nickname: str,
        discord_username: str = None,
        age: str = None,
        plots: int = 2,
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
                validate_text_field(nickname, 'Nickname', 32),
                validate_text_field(discord_username, 'Discord Username', 100) if discord_username else None,
                validate_text_field(age, 'Age', 32) if age else None,
                validate_numeric_field(plots, 'Plots', minimum=0, maximum=1000),
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
                required=False,
            )
            if screenshot_urls is None:
                return

            data = {
                'submitted_by': interaction.user.id,
                'submitter_display': interaction.user.display_name,
                'ingame_username': ingame_username,
                'discord_username': discord_username,
                'age': age,
                'nickname': nickname,
                'recruiter_display': interaction.user.display_name,
                'plots': plots,
                'screenshot_urls': ','.join(screenshot_urls) if screenshot_urls else None
            }

            form_id = await DBService.insert_recruitment(data)
            logger.info(f"Recruitment form #{form_id} submitted by {interaction.user.id}")

            form_data = {
                'ingame_username': ingame_username,
                'nickname': nickname,
                'plots': plots,
                'discord_username': discord_username,
                'age': age,
                'screenshot_urls': data['screenshot_urls']
            }

            display_id = make_display_id("recruitment", form_id)

            confirm_msg = await interaction.followup.send(f"✅ Recruitment `{display_id}` logged - pending approval.")

            config = await DBService.get_guild_config(interaction.guild_id)
            if config and config.get('approval_channel_id'):
                approval_channel = self.bot.get_channel(config['approval_channel_id'])
                if approval_channel:
                    embed = build_submission_embed('recruitment', form_data, form_id=form_id, submitter_name=interaction.user.display_name)

                    view = ApprovalView(
                        table='recruitment',
                        form_id=form_id,
                        form_type='recruitment',
                        submitter_id=interaction.user.id,
                        guild_id=interaction.guild_id,
                        channel_config_key='recruitment_channel_id',
                        thread_prefix="Recruitments",
                        confirmation_msg_id=confirm_msg.id,
                        confirmation_channel_id=interaction.channel_id,
                        form_data=form_data
                    )
                    msg = await approval_channel.send(embed=embed, view=view)
                    await DBService.set_approval_message_id('recruitment', form_id, msg.id)

                    # Persist confirmation message IDs
                    await DBService.execute(
                        "UPDATE recruitment SET confirmation_msg_id = $1, confirmation_channel_id = $2 WHERE id = $3",
                        confirm_msg.id, interaction.channel_id, form_id
                    )

        except Exception as e:
            logger.exception("Error in recruitment_add")
            await interaction.followup.send("❌ Submission failed. Please try again or contact an admin if it keeps happening.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(RecruitmentCog(bot))