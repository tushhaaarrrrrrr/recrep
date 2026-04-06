import discord
from discord import app_commands
from discord.ext import commands
from services.db_service import DBService
from utils.views import ApprovalView
from utils.logger import get_logger

logger = get_logger(__name__)

class ApprovalCog(commands.Cog):
    """Administrative commands for managing pending forms."""

    _FORM_TABLES = [
        'recruitment',
        'progress_report',
        'purchase_invoice',
        'demolition_report',
        'demolition_request',
        'eviction_report',
        'scroll_completion'
    ]

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        logger.info("ApprovalCog loaded - views are attached per form.")

    @app_commands.command(
        name="list_pending",
        description="List all forms waiting for approval"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def list_pending(self, interaction: discord.Interaction):
        config = await DBService.get_guild_config(interaction.guild_id)
        if not config or not config.get('approval_channel_id'):
            await interaction.response.send_message(
                "❌ **Approval channel not configured.**\nUse `/set_approval_channel` first.",
                ephemeral=True
            )
            return

        pending = []
        for table in self._FORM_TABLES:
            rows = await DBService.fetch(
                f"SELECT id, submitted_by, submitted_at FROM {table} WHERE status = 'pending'"
            )
            for row in rows:
                pending.append((table, row['id'], row['submitted_by'], row['submitted_at']))

        if not pending:
            await interaction.response.send_message(
                "✅ **No pending forms** - the approval queue is empty.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📋 Pending Approval Forms",
            description=f"**Total:** {len(pending)}",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )

        for table, fid, submitter_id, submitted_at in pending[:25]:
            submitter = interaction.guild.get_member(submitter_id)
            submitter_name = submitter.display_name if submitter else f"User {submitter_id}"
            embed.add_field(
                name=f"🔹 {table.replace('_', ' ').title()} · ID `{fid}`",
                value=f"**Submitted by:** {submitter_name}\n**At:** {submitted_at.strftime('%Y-%m-%d %H:%M')} UTC",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="resend_pending",
        description="Resend a pending form to the approval channel (if the original was lost)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def resend_pending(
        self,
        interaction: discord.Interaction,
        table: str,
        form_id: int
    ):
        if table not in self._FORM_TABLES:
            await interaction.response.send_message(
                f"❌ **Invalid table name.**\nValid options: {', '.join(self._FORM_TABLES)}",
                ephemeral=True
            )
            return

        row = await DBService.fetchrow(
            f"SELECT * FROM {table} WHERE id = $1 AND status = 'pending'",
            form_id
        )
        if not row:
            await interaction.response.send_message(
                f"❌ **Form not found** - no pending form with ID `{form_id}` in `{table}`.",
                ephemeral=True
            )
            return

        config = await DBService.get_guild_config(interaction.guild_id)
        if not config or not config.get('approval_channel_id'):
            await interaction.response.send_message(
                "❌ **Approval channel not configured.** Use `/set_approval_channel` first.",
                ephemeral=True
            )
            return

        approval_channel = self.bot.get_channel(config['approval_channel_id'])
        if not approval_channel:
            await interaction.response.send_message(
                "❌ **Approval channel not found** - the channel may have been deleted.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📄 Resubmitted: {table.replace('_', ' ').title()}",
            description=f"**Form ID:** `{form_id}`",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="👤 Submitted by",
            value=f"<@{row['submitted_by']}>",
            inline=True
        )
        embed.add_field(
            name="⏰ Submitted at",
            value=row['submitted_at'].strftime("%Y-%m-%d %H:%M UTC"),
            inline=True
        )
        if row.get('screenshot_urls'):
            embed.set_image(url=row['screenshot_urls'].split(',')[0])

        view = ApprovalView(
            table=table,
            form_id=form_id,
            form_type=table,
            submitter_id=row['submitted_by'],
            guild_id=interaction.guild_id,
            channel_config_key=f"{table}_channel_id",
            thread_prefix=table.replace('_', ' ').title()
        )

        msg = await approval_channel.send(embed=embed, view=view)
        await DBService.set_approval_message_id(table, form_id, msg.id)
        await interaction.response.send_message(
            f"✅ **Form `#{form_id}` from `{table}` resent to {approval_channel.mention}.**",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(ApprovalCog(bot))