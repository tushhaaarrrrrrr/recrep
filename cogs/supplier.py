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


class SupplierCog(commands.Cog):
    """Commands for submitting supplier activity reports."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name='supplier',
        description='Submit a supplier report for requested items or deliveries'
    )
    @app_commands.describe(
        supplied_item='What item was supplied',
        quantity='Quantity supplied',
        difficulty_to_obtain='How difficult it was to obtain the item',
        time_spent='Time spent sourcing or delivering the item',
        screenshot1='Screenshot evidence (at least one required)',
        screenshot2='Additional screenshot (optional)',
        screenshot3='Additional screenshot (optional)',
        screenshot4='Additional screenshot (optional)',
        screenshot5='Additional screenshot (optional)'
    )
    async def supplier_submit(
        self,
        interaction: discord.Interaction,
        supplied_item: str,
        quantity: int,
        difficulty_to_obtain: str,
        time_spent: str,
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
                validate_text_field(supplied_item, 'Supplied Item', 120),
                validate_text_field(difficulty_to_obtain, 'Difficulty to Obtain', 64),
                validate_text_field(time_spent, 'Time Spent', 40),
                validate_numeric_field(quantity, 'Quantity', minimum=1, maximum=100000),
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
                'supplied_item': supplied_item,
                'quantity': quantity,
                'difficulty_to_obtain': difficulty_to_obtain,
                'time_spent': time_spent,
                'screenshot_urls': ','.join(screenshot_urls),
            }

            form_id = await DBService.insert_supplier(data)
            display_id = make_display_id('supplier', form_id)
            logger.info(f"Supplier report #{form_id} submitted by {interaction.user.id}")

            form_data = {
                'supplied_item': supplied_item,
                'quantity': quantity,
                'difficulty_to_obtain': difficulty_to_obtain,
                'time_spent': time_spent,
                'screenshot_urls': data['screenshot_urls'],
            }

            confirm_msg = await interaction.followup.send(f"✅ Submitted · {display_id}\nYour supplier report is pending review.")

            config = await DBService.get_guild_config(interaction.guild_id)
            if config and (config.get('supplier_channel_id') or config.get('approval_channel_id')):
                channel_id = config.get('supplier_channel_id') or config.get('approval_channel_id')
                approval_channel = self.bot.get_channel(channel_id)
                if approval_channel:
                    embed = build_submission_embed('supplier', form_data, form_id=form_id, submitter_name=interaction.user.display_name)

                    view = ApprovalView(
                        table='supplier',
                        form_id=form_id,
                        form_type='supplier',
                        submitter_id=interaction.user.id,
                        guild_id=interaction.guild_id,
                        channel_config_key='supplier_channel_id',
                        thread_prefix='Suppliers',
                        confirmation_msg_id=confirm_msg.id,
                        confirmation_channel_id=interaction.channel_id,
                        form_data=form_data,
                    )
                    msg = await approval_channel.send(embed=embed, view=view)
                    await DBService.set_form_message_ids('supplier', form_id, msg.id, confirm_msg.id, interaction.channel_id)

        except Exception as e:
            logger.exception("Error in supplier_submit")
            await interaction.followup.send(
                '❌ We could not submit the supplier report right now. Please try again shortly.',
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(SupplierCog(bot))
