import discord
from discord import app_commands
from discord.ext import commands
from services.db_service import DBService
from utils.logger import get_logger
import re

logger = get_logger(__name__)


class LookupView(discord.ui.View):
    """Pagination view for lookup results."""

    def __init__(self, results: list, title: str, per_page: int = 10):
        super().__init__(timeout=180)
        self.results = results
        self.title = title
        self.per_page = per_page
        self.current_page = 0
        self.max_page = (len(results) - 1) // per_page if results else 0
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_page

    def build_embed(self) -> discord.Embed:
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_items = self.results[start:end]

        embed = discord.Embed(
            title=self.title,
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        if not page_items:
            embed.description = "No results found."
        else:
            for item in page_items:
                embed.add_field(
                    name=f"{item['form_type']} `{item['display_id']}` ({item['status']})",
                    value=item['description'],
                    inline=False
                )

        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_page + 1} • Total: {len(self.results)}")
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, disabled=True)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class LookupCog(commands.Cog):
    """Commands to look up recruitments and invoices."""

    _TABLE_PREFIX = {
        'recruitment': 'rec',
        'purchase_invoice': 'inv'
    }

    def __init__(self, bot):
        self.bot = bot

    async def _is_authorized(self, interaction: discord.Interaction) -> bool:
        has_admin = await DBService.user_has_role(interaction.user.id, 'admin')
        has_comayor = await DBService.user_has_role(interaction.user.id, 'comayor')
        if has_admin or has_comayor:
            return True
        return interaction.user.guild_permissions.manage_guild

    @app_commands.command(
        name="lookup_recruitment",
        description="Search recruitments by in‑game name or Discord username"
    )
    @app_commands.describe(
        query="In‑game name or Discord username/mention to search for"
    )
    async def lookup_recruitment(self, interaction: discord.Interaction, query: str):
        """Look up recruitment forms matching the given name or Discord mention."""
        await interaction.response.defer(ephemeral=True)

        if not await self._is_authorized(interaction):
            await interaction.followup.send(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        # Extract user ID if query is a mention
        user_id = None
        mention_match = re.search(r'<@!?(\d+)>', query)
        if mention_match:
            user_id = int(mention_match.group(1))
            # If we have a user ID, search by that ID in discord_username field
            # We'll match on the raw ID or the mention format
            search_term = str(user_id)
        else:
            search_term = query.strip()

        # Build SQL condition
        # Search in ingame_username or discord_username (case-insensitive)
        condition = """
            (ingame_username ILIKE $1 OR discord_username ILIKE $1)
        """
        pattern = f"%{search_term}%"

        rows = await DBService.fetch(
            f"""
            SELECT id, submitted_by, submitted_at, status, ingame_username, discord_username, nickname, plots
            FROM recruitment
            WHERE {condition}
            ORDER BY submitted_at DESC
            LIMIT 50
            """,
            pattern
        )

        if not rows:
            await interaction.followup.send(
                f"No recruitments found matching '{query}'.",
                ephemeral=True
            )
            return

        results = []
        for row in rows:
            prefix = self._TABLE_PREFIX['recruitment']
            display_id = f"{prefix}_{row['id']}"
            submitted_at = row['submitted_at'].strftime('%Y-%m-%d')
            desc_lines = [
                f"**Player:** {row['nickname']} ({row['ingame_username']})",
                f"**Plots:** {row['plots']}",
                f"**Submitted:** {submitted_at}",
            ]
            if row['discord_username']:
                desc_lines.append(f"**Discord:** {row['discord_username']}")
            results.append({
                'form_type': 'Recruitment',
                'display_id': display_id,
                'status': row['status'],
                'description': '\n'.join(desc_lines)
            })

        view = LookupView(results, f"Recruitment search results for '{query}'")
        embed = view.build_embed()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(
        name="lookup_invoice",
        description="Search purchase invoices by buyer's in‑game name"
    )
    @app_commands.describe(
        ingame_name="Buyer's Minecraft username (partial match supported)"
    )
    async def lookup_invoice(self, interaction: discord.Interaction, ingame_name: str):
        """Look up purchase invoices matching the given buyer in‑game name."""
        await interaction.response.defer(ephemeral=True)

        if not await self._is_authorized(interaction):
            await interaction.followup.send(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        pattern = f"%{ingame_name.strip()}%"
        rows = await DBService.fetch(
            """
            SELECT id, submitted_by, submitted_at, status, purchasee_nickname, purchasee_ingame,
                   purchase_type, amount_deposited, num_plots, total_plots, banner_color, shop_number
            FROM purchase_invoice
            WHERE purchasee_ingame ILIKE $1
            ORDER BY submitted_at DESC
            LIMIT 50
            """,
            pattern
        )

        if not rows:
            await interaction.followup.send(
                f"No invoices found for buyer '{ingame_name}'.",
                ephemeral=True
            )
            return

        results = []
        for row in rows:
            prefix = self._TABLE_PREFIX['purchase_invoice']
            display_id = f"{prefix}_{row['id']}"
            submitted_at = row['submitted_at'].strftime('%Y-%m-%d')
            desc_lines = [
                f"**Buyer:** {row['purchasee_nickname']} ({row['purchasee_ingame']})",
                f"**Type:** {row['purchase_type']}",
                f"**Amount:** {row['amount_deposited']} coins",
                f"**Submitted:** {submitted_at}",
            ]
            if row['num_plots']:
                desc_lines.append(f"**Plots:** {row['num_plots']} (total: {row['total_plots']})")
            if row['banner_color']:
                desc_lines.append(f"**Mall Shop:** {row['banner_color']} #{row['shop_number']}")
            results.append({
                'form_type': 'Invoice',
                'display_id': display_id,
                'status': row['status'],
                'description': '\n'.join(desc_lines)
            })

        view = LookupView(results, f"Invoice search results for '{ingame_name}'")
        embed = view.build_embed()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(LookupCog(bot))