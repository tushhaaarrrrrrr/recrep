import discord
from discord import app_commands
from discord.ext import commands
from services.db_service import DBService
from utils.form_embeds import build_submission_embed
from utils.logger import get_logger
from config.forms import FORM_TABLE_PREFIX, FormStatus

logger = get_logger(__name__)


class FormEditCog(commands.Cog):
    """Allows submitters to edit their pending or held forms."""

    def __init__(self, bot):
        self.bot = bot

    VALID_TABLES = [
        'recruitment', 'progress_report', 'purchase_invoice', 'mall_shop', 'supplier',
        'demolition_report', 'demolition_request', 'eviction_report',
        'scroll_completion'
    ]

    TABLE_PREFIX = FORM_TABLE_PREFIX

    ALLOWED_FIELDS = {
        'recruitment': {
            'ingame_username': 'In-game Username',
            'discord_username': 'Discord Username',
            'age': 'Age',
            'nickname': 'Nickname',
            'plots': 'Plots'
        },
        'progress_report': {
            'project_name': 'Project Name',
            'time_spent': 'Time Spent',
            'note': 'Note',
            'helper_mentions': 'Helper'
        },
        'purchase_invoice': {
            'purchasee_nickname': 'Buyer Nickname',
            'purchasee_ingame': 'Buyer In-game',
            'purchase_type': 'Purchase Type',
            'amount_deposited': 'Amount Deposited',
            'num_plots': 'Number of Plots',
            'total_plots': 'Total Plots',
            'banner_color': 'Banner Color',
            'shop_number': 'Shop Number',
            'house_number': 'House Number'
        },
        'mall_shop': {
            'ingame_name': 'In-game Name',
            'discord_nickname': 'Discord Nickname',
            'amount_of_shops': 'Amount of Shops',
            'total_amount': 'Total Amount',
            'payment_frequency': 'Payment Frequency',
            'paid_periods': 'Paid Periods',
            'banner_color': 'Banner Color',
            'shop_number': 'Shop Number',
            'notes': 'Notes'
        },
        'supplier': {
            'supplied_item': 'Supplied Item',
            'quantity': 'Quantity',
            'difficulty_to_obtain': 'Difficulty to Obtain',
            'time_spent': 'Time Spent'
        },
        'demolition_report': {
            'ingame_username': 'Player',
            'removed': 'Removed',
            'stashed_items': 'Items Stashed'
        },
        'demolition_request': {
            'ingame_username': 'Player',
            'reason': 'Reason'
        },
        'eviction_report': {
            'ingame_owner': 'Owner',
            'items_stored': 'Items Stored',
            'inactivity_period': 'Inactivity Period'
        },
        'scroll_completion': {
            'scroll_type': 'Scroll Type',
            'items_stored': 'Items Stored'
        }
    }

    @app_commands.command(name="form", description="Edit a pending or held form")
    @app_commands.describe(
        form_id="Form ID with prefix (e.g., rec_1, rep_2, inv_3)",
        field="Field to edit (see list of valid fields)",
        value="New value for the field"
    )
    async def form_edit(
        self,
        interaction: discord.Interaction,
        form_id: str,
        field: str,
        value: str
    ):
        """Edit a specific field of a pending or held form."""
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return

        if '_' not in form_id:
            await interaction.followup.send(
                "❌ Invalid form ID format. Use format like `rec_1`, `rep_2`, `inv_3`, etc.",
                ephemeral=True
            )
            return
        prefix, num_part = form_id.split('_', 1)
        try:
            numeric_id = int(num_part)
        except ValueError:
            await interaction.followup.send(
                "❌ Invalid numeric ID in form ID.",
                ephemeral=True
            )
            return

        table = None
        for t, p in self.TABLE_PREFIX.items():
            if p == prefix:
                table = t
                break
        if not table:
            await interaction.followup.send(
                f"❌ Unknown prefix `{prefix}`. Valid prefixes: {', '.join(self.TABLE_PREFIX.values())}",
                ephemeral=True
            )
            return

        form_info = await DBService.get_form_by_id(table, numeric_id)
        if not form_info:
            await interaction.followup.send("❌ Form not found.", ephemeral=True)
            return
        status, submitter_id = form_info
        if interaction.user.id != submitter_id:
            await interaction.followup.send("❌ You can only edit your own forms.", ephemeral=True)
            return
        if status not in (FormStatus.PENDING, FormStatus.HOLD):
            await interaction.followup.send("❌ This form cannot be edited because it is already approved or denied.", ephemeral=True)
            return

        allowed = self.ALLOWED_FIELDS.get(table, {})
        if field not in allowed:
            valid_fields = ", ".join(allowed.keys())
            await interaction.followup.send(
                f"❌ Invalid field for this form type.\nValid fields: `{valid_fields}`",
                ephemeral=True
            )
            return

        original_value = value
        if field in ('stashed_items', 'items_stored'):
            if value.lower() not in ('yes', 'no'):
                await interaction.followup.send("❌ Value must be `yes` or `no`.", ephemeral=True)
                return
            value = value.lower() == 'yes'
        elif field in ('plots', 'num_plots', 'total_plots', 'shop_number', 'house_number', 'amount_of_shops', 'paid_periods'):
            try:
                value = int(value)
            except ValueError:
                await interaction.followup.send("❌ Value must be a number.", ephemeral=True)
                return
        elif field in ('amount_deposited', 'total_amount'):
            try:
                value = float(value)
            except ValueError:
                await interaction.followup.send("❌ Value must be a number.", ephemeral=True)
                return
        elif field == 'payment_frequency':
            value = value.strip().lower()
            if value not in ('daily', 'weekly', 'monthly', 'yearly'):
                await interaction.followup.send(
                    "❌ Payment frequency must be `daily`, `weekly`, `monthly`, or `yearly`.",
                    ephemeral=True
                )
                return

        await DBService.update_form_field(table, numeric_id, field, value)
        logger.info(f"User {interaction.user.id} edited {table}#{numeric_id}: {field}={value}")

        await self._refresh_approval_embed(interaction.guild, table, numeric_id)

        await interaction.followup.send(
            f"✅ **Form `{form_id}` updated.** `{field}` changed from `{original_value}` to `{value}`.",
            ephemeral=True
        )

    async def _refresh_approval_embed(self, guild: discord.Guild, table: str, form_id: int):
        config = await DBService.get_guild_config(guild.id)
        if not config or not config.get('approval_channel_id'):
            logger.warning(f"No approval channel configured for guild {guild.id}")
            return

        approval_channel = guild.get_channel(config['approval_channel_id'])
        if not approval_channel:
            logger.warning(f"Approval channel not found for guild {guild.id}")
            return

        message_id = await DBService.get_approval_message_id(table, form_id)
        if not message_id:
            logger.warning(f"No approval message ID stored for {table}#{form_id}")
            return

        try:
            message = await approval_channel.fetch_message(message_id)
        except discord.NotFound:
            logger.warning(f"Approval message {message_id} not found (may have been deleted)")
            return

        form_data = await DBService.get_full_form_data(table, form_id)
        if not form_data:
            logger.error(f"Form data missing for {table}#{form_id}")
            return

        embed = self._build_embed(table, form_data, form_id)
        await message.edit(embed=embed)

    def _build_embed(self, table: str, form_data: dict, form_id: int) -> discord.Embed:
        embed = build_submission_embed(
            table,
            form_data,
            form_id=form_id,
            submitter_name=f"<@{form_data['submitted_by']}>" if form_data.get('submitted_by') else 'Unknown',
        )
        return embed


async def setup(bot):
    await bot.add_cog(FormEditCog(bot))