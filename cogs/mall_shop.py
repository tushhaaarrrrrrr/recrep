import discord
from discord import app_commands
from discord.ext import commands, tasks
from services.db_service import DBService
from utils.helpers import upload_attachments, validate_text_field, validate_numeric_field
from utils.views import ApprovalView
from utils.form_embeds import build_submission_embed, format_amount
from utils.logger import get_logger
from config.forms import display_id as make_display_id

logger = get_logger(__name__)


class MallShopCog(commands.Cog):
    """Commands for submitting and tracking mall shop rent records."""

    _PAYMENT_CHOICES = [
        app_commands.Choice(name='Daily', value='daily'),
        app_commands.Choice(name='Weekly', value='weekly'),
        app_commands.Choice(name='Monthly', value='monthly'),
        app_commands.Choice(name='Yearly', value='yearly'),
    ]

    def __init__(self, bot):
        self.bot = bot
        self.mall_shop_alerts.start()

    def cog_unload(self):
        self.mall_shop_alerts.cancel()

    @tasks.loop(hours=6)
    async def mall_shop_alerts(self):
        await self._send_mall_shop_alerts()

    @mall_shop_alerts.before_loop
    async def before_mall_shop_alerts(self):
        await self.bot.wait_until_ready()
        await self._send_mall_shop_alerts()

    @staticmethod
    def _build_alert_embed(row: dict, overdue: bool = False) -> discord.Embed:
        name = row.get('ingame_name', 'Unknown owner')
        shops = row.get('amount_of_shops', 0)
        total = row.get('total_amount', 0)
        due_date = row.get('next_due_date')
        days_overdue = 0
        if overdue and due_date:
            try:
                days_overdue = max((discord.utils.utcnow().date() - due_date).days, 0)
            except Exception:
                days_overdue = 0

        title = "⚠️ Rent Overdue" if overdue else "🔔 Rent Due"
        color = discord.Color.red() if overdue else discord.Color.gold()
        embed = discord.Embed(title=title, color=color, timestamp=discord.utils.utcnow())
        embed.add_field(name="Owner", value=name, inline=True)
        embed.add_field(name="Shops", value=format_amount(shops), inline=True)
        embed.add_field(name="Total", value=f"{format_amount(total)} coins", inline=True)
        if due_date:
            embed.add_field(name="Due Date", value=str(due_date), inline=True)
        if overdue:
            embed.add_field(
                name="Overdue",
                value=f"{days_overdue} day{'s' if days_overdue != 1 else ''}",
                inline=True,
            )
        else:
            embed.add_field(name="Status", value="Payment due now", inline=True)
        return embed

    async def _send_mall_shop_alerts(self):
        try:
            alerts = await DBService.get_mall_shop_alerts()
            if not alerts['due'] and not alerts['overdue']:
                return

            guild_configs = await DBService.get_all_guild_configs()
            for config in guild_configs:
                channel_id = config.get('mall_shop_alert_channel_id')
                if not channel_id:
                    continue

                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue

                for row in alerts['due']:
                    try:
                        await channel.send(embed=self._build_alert_embed(row, overdue=False))
                        await DBService.mark_mall_shop_alert_sent(row['id'], 'due')
                    except Exception:
                        logger.exception("Failed to send due mall shop alert for %s", row.get('id'))

                for row in alerts['overdue']:
                    try:
                        await channel.send(embed=self._build_alert_embed(row, overdue=True))
                        await DBService.mark_mall_shop_alert_sent(row['id'], 'overdue')
                    except Exception:
                        logger.exception("Failed to send overdue mall shop alert for %s", row.get('id'))
        except Exception:
            logger.exception("Failed to send mall shop alerts")
    @app_commands.command(
        name='mall_shop',
        description='Record a mall shop payment, lease coverage, or rent extension'
    )
    @app_commands.choices(payment_frequency=_PAYMENT_CHOICES)
    @app_commands.describe(
        ingame_name='Minecraft username of the mall shop owner',
        amount_of_shops='Number of shops covered by this payment',
        total_amount='Total amount paid for the shops',
        payment_frequency='Choose how often rent comes due',
        paid_periods='How many rent periods are covered',
        banner_color='Optional banner color used for the shop',
        shop_number='Optional shop number or identifier',
        notes='Optional staff notes or special instructions',
        screenshot1='Screenshot evidence (at least one required)',
        screenshot2='Additional screenshot (optional)',
        screenshot3='Additional screenshot (optional)',
        screenshot4='Additional screenshot (optional)',
        screenshot5='Additional screenshot (optional)'
    )
    async def mall_shop_submit(
        self,
        interaction: discord.Interaction,
        ingame_name: str,
        amount_of_shops: int,
        total_amount: float,
        payment_frequency: app_commands.Choice[str],
        paid_periods: int = 1,
        banner_color: str = None,
        shop_number: str = None,
        notes: str = None,
        screenshot1: discord.Attachment = None,
        screenshot2: discord.Attachment = None,
        screenshot3: discord.Attachment = None,
        screenshot4: discord.Attachment = None,
        screenshot5: discord.Attachment = None,
    ):
        try:
            await interaction.response.defer()
        except (discord.NotFound, discord.HTTPException):
            return

        try:
            for err in filter(None, [
                validate_text_field(ingame_name, 'In-game Name', 64),
                validate_text_field(banner_color, 'Banner Color', 32) if banner_color else None,
                validate_text_field(shop_number, 'Shop Number', 32) if shop_number else None,
                validate_text_field(notes, 'Notes', 1000) if notes else None,
                validate_numeric_field(amount_of_shops, 'Amount of Shops', minimum=1, maximum=1000),
                validate_numeric_field(total_amount, 'Total Amount', minimum=0),
                validate_numeric_field(paid_periods, 'Paid Periods', minimum=1, maximum=120),
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
                'ingame_name': ingame_name,
                'discord_nickname': interaction.user.display_name,
                'amount_of_shops': amount_of_shops,
                'total_amount': total_amount,
                'payment_frequency': payment_frequency.value,
                'paid_periods': paid_periods,
                'banner_color': banner_color,
                'shop_number': shop_number,
                'notes': notes,
                'screenshot_urls': ','.join(screenshot_urls),
            }

            form_id = await DBService.insert_mall_shop(data)
            logger.info(f'Mall shop form #{form_id} submitted by {interaction.user.id}')

            form_data = {
                'ingame_name': ingame_name,
                'discord_nickname': interaction.user.display_name,
                'amount_of_shops': amount_of_shops,
                'total_amount': total_amount,
                'payment_frequency': payment_frequency.value,
                'paid_periods': paid_periods,
                'banner_color': banner_color,
                'shop_number': shop_number,
                'notes': notes,
                'screenshot_urls': data['screenshot_urls'],
            }

            display_id = make_display_id('mall_shop', form_id)
            confirm_msg = await interaction.followup.send(f"✅ Submitted · {display_id}\nYour mall shop record is pending review.")

            config = await DBService.get_guild_config(interaction.guild_id)
            channel_id = None
            if config:
                channel_id = config.get('mall_shop_channel_id') or config.get('approval_channel_id')
            if channel_id:
                approval_channel = self.bot.get_channel(channel_id)
                if approval_channel:
                    embed = build_submission_embed('mall_shop', form_data, form_id=form_id, submitter_name=interaction.user.display_name)

                    view = ApprovalView(
                        table='mall_shop',
                        form_id=form_id,
                        form_type='mall_shop',
                        submitter_id=interaction.user.id,
                        guild_id=interaction.guild_id,
                        channel_config_key='mall_shop_channel_id',
                        thread_prefix='Mall Shops',
                        confirmation_msg_id=confirm_msg.id,
                        confirmation_channel_id=interaction.channel_id,
                        form_data=form_data,
                    )
                    msg = await approval_channel.send(embed=embed, view=view)
                    await DBService.set_form_message_ids('mall_shop', form_id, msg.id, confirm_msg.id, interaction.channel_id)

        except Exception as e:
            logger.exception("Error in mall_shop_submit")
            await interaction.followup.send(
                '❌ Submission failed. Please try again or contact an admin if it keeps happening.',
                ephemeral=True,
            )


async def setup(bot):
    await bot.add_cog(MallShopCog(bot))
