import discord
from discord import app_commands
from discord.ext import commands, tasks
from services.db_service import DBService
from services.s3_service import upload_image
from utils.views import ApprovalView
from utils.logger import get_logger

logger = get_logger(__name__)


class MallShopCog(commands.Cog):
    """Commands for submitting and tracking mall shop rent records."""

    _TABLE_PREFIX = {
        'mall_shop': 'msh'
    }

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

    @staticmethod
    def _alert_message(row: dict, overdue: bool = False) -> str:
        base = (
            f"{row['ingame_name']} has to pay for their {row['amount_of_shops']} shops today, "
            f"the total is {row['total_amount']}"
        )
        if overdue:
            days_overdue = 0
            try:
                next_due = row.get('next_due_date')
                if next_due:
                    days_overdue = max((discord.utils.utcnow().date() - next_due).days, 0)
            except Exception:
                days_overdue = 0
            if days_overdue >= 3:
                base += f" (overdue by {days_overdue} days)"
        return base

    async def _send_mall_shop_alerts(self):
        try:
            alerts = await DBService.get_mall_shop_alerts()
            if not alerts['due'] and not alerts['overdue']:
                return

            config = None
            if self.bot.guilds:
                config = await DBService.get_guild_config(self.bot.guilds[0].id)
            if not config:
                return

            channel_id = config.get('mall_shop_alert_channel_id')
            if not channel_id:
                return

            channel = self.bot.get_channel(channel_id)
            if not channel:
                return

            for row in alerts['due']:
                await channel.send(self._alert_message(row, overdue=False))
                await DBService.mark_mall_shop_alert_sent(row['id'], 'due')

            for row in alerts['overdue']:
                await channel.send(self._alert_message(row, overdue=True))
                await DBService.mark_mall_shop_alert_sent(row['id'], 'overdue')
        except Exception as e:
            logger.exception(f'Failed to send mall shop alerts: {e}')

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
            screenshots = [s for s in (screenshot1, screenshot2, screenshot3, screenshot4, screenshot5) if s]
            if not screenshots:
                await interaction.followup.send(
                    '❌ **At least one screenshot is required.** Please attach an image.',
                    ephemeral=True,
                )
                return

            if amount_of_shops <= 0:
                await interaction.followup.send(
                    '❌ **Amount of shops must be at least 1.**',
                    ephemeral=True,
                )
                return

            if paid_periods <= 0:
                await interaction.followup.send(
                    '❌ **Paid periods must be at least 1.**',
                    ephemeral=True,
                )
                return

            screenshot_urls = []
            for img in screenshots:
                img_bytes = await img.read()
                url = await upload_image(img_bytes, img.filename)
                screenshot_urls.append(url)

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

            display_id = f"{self._TABLE_PREFIX['mall_shop']}_{form_id}"
            confirm_msg = await interaction.followup.send(
                f"✅ Mall shop record `{display_id}` submitted and queued for review."
            )

            config = await DBService.get_guild_config(interaction.guild_id)
            channel_id = None
            if config:
                channel_id = config.get('mall_shop_channel_id') or config.get('approval_channel_id')
            if channel_id:
                approval_channel = self.bot.get_channel(channel_id)
                if approval_channel:
                    embed = discord.Embed(
                        title='Mall Shop Record',
                        color=discord.Color.teal(),
                        timestamp=discord.utils.utcnow(),
                    )
                    embed.add_field(name='Owner', value=ingame_name, inline=True)
                    embed.add_field(name='Shops', value=str(amount_of_shops), inline=True)
                    embed.add_field(name='Total', value=f'{total_amount} coins', inline=True)
                    embed.add_field(
                        name='Cycle',
                        value=DBService._mall_shop_frequency_label(payment_frequency.value, paid_periods),
                        inline=True,
                    )
                    embed.add_field(name='Periods Paid', value=str(paid_periods), inline=True)
                    if banner_color:
                        embed.add_field(name='Banner Color', value=banner_color, inline=True)
                    if shop_number:
                        embed.add_field(name='Shop Number', value=str(shop_number), inline=True)
                    if notes:
                        embed.add_field(name='Notes', value=notes[:1000], inline=False)
                    if screenshot_urls:
                        embed.set_image(url=screenshot_urls[0])
                        if len(screenshot_urls) > 1:
                            embed.add_field(name='Additional Screenshots', value=f'{len(screenshot_urls) - 1} more', inline=False)
                    embed.set_footer(text=f'Form ID: {display_id}')

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
                    await DBService.set_approval_message_id('mall_shop', form_id, msg.id)

                    await DBService.execute(
                        'UPDATE mall_shop SET confirmation_msg_id = $1, confirmation_channel_id = $2 WHERE id = $3',
                        confirm_msg.id, interaction.channel_id, form_id,
                    )

        except Exception as e:
            logger.exception(f'Error in mall_shop_submit: {e}')
            await interaction.followup.send(
                '❌ An error occurred while submitting the mall shop record. Please try again later.',
                ephemeral=True,
            )


async def setup(bot):
    await bot.add_cog(MallShopCog(bot))
