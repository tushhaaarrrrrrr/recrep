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

class InvoiceCog(commands.Cog):
    """Commands for submitting purchase invoices (plots, mall shops, or spawn houses)."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="invoice",
        description="Submit a purchase invoice for plot sales or spawn houses"
    )
    @app_commands.describe(
        buyer_nickname="Discord nickname of the buyer",
        buyer_ingame="Minecraft username of the buyer",
        purchase_type="Type of purchase: `premium`, `normal`, `staff`, or `spawn_house`",
        amount_deposited="Amount of coins deposited to the town bank",
        num_plots="Number of plots sold (for plot purchases)",
        total_plots="Buyer's total plots after this purchase",
        banner_color="Banner color of the mall shop (for mall shop purchases)",
        shop_number="Shop number in the mall (for mall shop purchases)",
        house_number="House number (for spawn house purchases)",
        screenshot1="Screenshot evidence (at least one required)",
        screenshot2="Additional screenshot (optional)",
        screenshot3="Additional screenshot (optional)",
        screenshot4="Additional screenshot (optional)",
        screenshot5="Additional screenshot (optional)"
    )
    async def invoice_submit(
        self,
        interaction: discord.Interaction,
        buyer_nickname: str,
        buyer_ingame: str,
        purchase_type: str,
        amount_deposited: float,
        screenshot1: discord.Attachment = None,
        screenshot2: discord.Attachment = None,
        screenshot3: discord.Attachment = None,
        screenshot4: discord.Attachment = None,
        screenshot5: discord.Attachment = None,
        num_plots: int = None,
        total_plots: int = None,
        banner_color: str = None,
        shop_number: int = None,
        house_number: int = None
    ):
        try:
            await interaction.response.defer()
        except (discord.NotFound, discord.HTTPException):
            return

        try:
            for err in filter(None, [
                validate_text_field(buyer_nickname, 'Buyer Nickname', 64),
                validate_text_field(buyer_ingame, 'Buyer In-game', 64),
                validate_text_field(banner_color, 'Banner Color', 32) if banner_color else None,
                validate_text_field(str(shop_number), 'Shop Number', 16) if shop_number is not None else None,
                validate_numeric_field(amount_deposited, 'Amount Deposited', minimum=0),
            ]):
                await interaction.followup.send(f'❌ {err}', ephemeral=True)
                return
            if purchase_type.strip().lower() not in {'premium', 'normal', 'staff', 'spawn_house', 'mall_shop'}:
                await interaction.followup.send('❌ Invalid purchase type.', ephemeral=True)
                return
            if purchase_type.strip().lower() == 'mall_shop':
                await interaction.followup.send(
                    '❌ Mall shop records now use `/mall_shop`. Please use that command instead.',
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
                'seller_display': interaction.user.display_name,
                'purchasee_nickname': buyer_nickname,
                'purchasee_ingame': buyer_ingame,
                'purchase_type': purchase_type,
                'num_plots': num_plots,
                'total_plots': total_plots,
                'banner_color': banner_color,
                'shop_number': shop_number,
                'house_number': house_number,
                'amount_deposited': amount_deposited,
                'screenshot_urls': ','.join(screenshot_urls)
            }

            form_id = await DBService.insert_invoice(data)
            logger.info(f"Invoice #{form_id} submitted by {interaction.user.id}")

            form_data = {
                'seller_display': interaction.user.display_name,
                'purchasee_nickname': buyer_nickname,
                'purchasee_ingame': buyer_ingame,
                'amount_deposited': amount_deposited,
                'purchase_type': purchase_type,
                'num_plots': num_plots,
                'total_plots': total_plots,
                'banner_color': banner_color,
                'shop_number': shop_number,
                'house_number': house_number,
                'screenshot_urls': data['screenshot_urls']
            }

            display_id = make_display_id("purchase_invoice", form_id)

            confirm_msg = await interaction.followup.send(f"✅ Invoice `{display_id}` submitted - pending approval.")

            config = await DBService.get_guild_config(interaction.guild_id)
            if config and config.get('approval_channel_id'):
                approval_channel = self.bot.get_channel(config['approval_channel_id'])
                if approval_channel:
                    embed = build_submission_embed('purchase_invoice', form_data, form_id=form_id, submitter_name=interaction.user.display_name)

                    view = ApprovalView(
                        table='purchase_invoice',
                        form_id=form_id,
                        form_type='purchase_invoice',
                        submitter_id=interaction.user.id,
                        guild_id=interaction.guild_id,
                        channel_config_key='invoice_channel_id',
                        thread_prefix="Invoices",
                        confirmation_msg_id=confirm_msg.id,
                        confirmation_channel_id=interaction.channel_id,
                        form_data=form_data
                    )
                    msg = await approval_channel.send(embed=embed, view=view)
                    await DBService.set_approval_message_id('purchase_invoice', form_id, msg.id)

                    # Persist confirmation message IDs
                    await DBService.execute(
                        "UPDATE purchase_invoice SET confirmation_msg_id = $1, confirmation_channel_id = $2 WHERE id = $3",
                        confirm_msg.id, interaction.channel_id, form_id
                    )

        except Exception as e:
            logger.exception("Error in invoice_submit")
            await interaction.followup.send(
                "❌ An error occurred while submitting the invoice. Please try again later.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(InvoiceCog(bot))