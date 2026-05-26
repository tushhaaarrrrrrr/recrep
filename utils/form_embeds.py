from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence

import discord

from config.forms import FORM_TABLE_PREFIX, FORM_THREAD_LABEL, display_id


def _split_urls(urls: str | Sequence[str] | None) -> list[str]:
    if not urls:
        return []
    if isinstance(urls, str):
        return [part.strip() for part in urls.split(",") if part.strip()]
    return [str(url).strip() for url in urls if str(url).strip()]


def _first_image(urls: str | Sequence[str] | None) -> tuple[str | None, int]:
    items = _split_urls(urls)
    return (items[0] if items else None, max(len(items) - 1, 0))


def _truncate(value: object, limit: int = 1000) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _coalesce(*values: object, default: str = "?") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _bool_text(value: object) -> str:
    return "Yes" if bool(value) else "No"


def _base_embed(title: str, color: discord.Color, form_id: int | None = None) -> discord.Embed:
    embed = discord.Embed(title=title, color=color, timestamp=datetime.now(timezone.utc))
    if form_id is not None:
        embed.set_footer(text=f"Form ID: {display_id('unknown', form_id)}")
    return embed


def _add_images(embed: discord.Embed, form_data: dict) -> None:
    image_url, extra = _first_image(form_data.get("screenshot_urls"))
    if image_url:
        embed.set_image(url=image_url)
        if extra:
            embed.add_field(name="Additional Screenshots", value=f"{extra} more", inline=False)


def _footer(embed: discord.Embed, approved_by: str | None = None) -> None:
    if approved_by:
        embed.set_footer(text=f"Approved by {approved_by} · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    else:
        embed.set_footer(text=f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")


def _append_common_header(embed: discord.Embed, form_id: int, submitter_name: str, approved_by: str | None = None) -> None:
    embed.add_field(name="Submitted by", value=submitter_name, inline=True)
    if approved_by:
        embed.add_field(name="Approved by", value=approved_by, inline=True)
    embed.add_field(name="Form ID", value=display_id("unknown", form_id), inline=True)


def build_submission_embed(table: str, form_data: dict, *, form_id: int, submitter_name: str) -> discord.Embed:
    title_map = {
        "recruitment": "Recruitment Log",
        "progress_report": "Progress Report",
        "purchase_invoice": "Purchase Invoice",
        "mall_shop": "Mall Shop Record",
        "supplier": "Supplier Report",
        "demolition_report": "Demolition Report",
        "demolition_request": "Demolition Request",
        "eviction_report": "Eviction Report",
        "scroll_completion": "Scroll Completion",
    }
    embed = discord.Embed(
        title=title_map.get(table, table.replace("_", " ").title()),
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    _append_common_header(embed, form_id, submitter_name)

    if table == "recruitment":
        embed.add_field(name="New Player", value=f"{_coalesce(form_data.get('nickname'))} ({_coalesce(form_data.get('ingame_username'))})", inline=True)
        embed.add_field(name="Plots", value=str(form_data.get("plots", 0)), inline=True)
        if form_data.get("discord_username"):
            embed.add_field(name="Discord", value=_truncate(form_data.get("discord_username")), inline=True)
        if form_data.get("age"):
            embed.add_field(name="Age", value=_truncate(form_data.get("age")), inline=True)
    elif table == "progress_report":
        embed.add_field(name="Project", value=_truncate(form_data.get("project_name")), inline=True)
        embed.add_field(name="Time Spent", value=_truncate(form_data.get("time_spent")), inline=True)
        if form_data.get("helper_mentions"):
            embed.add_field(name="Helper", value=_truncate(form_data.get("helper_mentions")), inline=True)
        if form_data.get("note"):
            embed.add_field(name="Note", value=_truncate(form_data.get("note")), inline=False)
    elif table == "purchase_invoice":
        embed.add_field(name="Buyer", value=f"{_coalesce(form_data.get('purchasee_nickname'))} ({_coalesce(form_data.get('purchasee_ingame'))})", inline=True)
        embed.add_field(name="Type", value=_truncate(form_data.get("purchase_type")), inline=True)
        embed.add_field(name="Amount", value=f"{form_data.get('amount_deposited', 0)} coins", inline=True)
        if form_data.get("seller_display"):
            embed.add_field(name="Seller", value=_truncate(form_data.get("seller_display")), inline=True)
        if form_data.get("num_plots"):
            embed.add_field(name="Plots", value=f"{form_data.get('num_plots')} (total: {form_data.get('total_plots', 0)})", inline=True)
        if form_data.get("banner_color"):
            embed.add_field(name="Mall Shop", value=f"Color {form_data.get('banner_color')} · #{form_data.get('shop_number')}", inline=True)
        if form_data.get("house_number") and form_data.get("purchase_type") == "spawn_house":
            embed.add_field(name="Spawn House", value=f"House #{form_data.get('house_number')}", inline=True)
    elif table == "mall_shop":
        embed.add_field(name="Owner", value=_truncate(form_data.get("ingame_name")), inline=True)
        embed.add_field(name="Shops", value=str(form_data.get("amount_of_shops", 0)), inline=True)
        embed.add_field(name="Total", value=f"{form_data.get('total_amount', 0)} coins", inline=True)
        embed.add_field(name="Cycle", value=_truncate(form_data.get("payment_frequency")), inline=True)
        embed.add_field(name="Periods Paid", value=str(form_data.get("paid_periods", 1)), inline=True)
        if form_data.get("banner_color"):
            embed.add_field(name="Banner Color", value=_truncate(form_data.get("banner_color")), inline=True)
        if form_data.get("shop_number"):
            embed.add_field(name="Shop Number", value=_truncate(form_data.get("shop_number")), inline=True)
        if form_data.get("notes"):
            embed.add_field(name="Notes", value=_truncate(form_data.get("notes")), inline=False)
    elif table == "supplier":
        embed.add_field(name="Supplied Item", value=_truncate(form_data.get("supplied_item")), inline=True)
        embed.add_field(name="Quantity", value=str(form_data.get("quantity", 0)), inline=True)
        embed.add_field(name="Difficulty", value=_truncate(form_data.get("difficulty_to_obtain")), inline=True)
        embed.add_field(name="Time Spent", value=_truncate(form_data.get("time_spent")), inline=True)
    elif table == "demolition_report":
        embed.add_field(name="Player", value=_truncate(form_data.get("ingame_username")), inline=True)
        embed.add_field(name="Removed", value=_truncate(form_data.get("removed")), inline=True)
        embed.add_field(name="Items Stashed", value=_bool_text(form_data.get("stashed_items")), inline=True)
    elif table == "demolition_request":
        embed.add_field(name="Target Player", value=_truncate(form_data.get("ingame_username")), inline=True)
        embed.add_field(name="Reason", value=_truncate(form_data.get("reason")), inline=False)
    elif table == "eviction_report":
        embed.add_field(name="Owner", value=_truncate(form_data.get("ingame_owner")), inline=True)
        embed.add_field(name="Items Stored", value=_bool_text(form_data.get("items_stored")), inline=True)
        embed.add_field(name="Inactivity Period", value=_truncate(form_data.get("inactivity_period")), inline=True)
    elif table == "scroll_completion":
        embed.add_field(name="Scroll Type", value=_truncate(form_data.get("scroll_type")).capitalize() if form_data.get("scroll_type") else "?", inline=True)
        embed.add_field(name="Items Stored", value=_bool_text(form_data.get("items_stored")), inline=True)

    _add_images(embed, form_data)
    embed.set_footer(text=f"Form ID: {display_id(table, form_id)}")
    return embed


def build_approval_embed(table: str, form_data: dict, *, form_id: int, submitter_name: str, approver_name: str, approved_at: datetime | None = None) -> discord.Embed:
    title_map = {
        "recruitment": "Recruitment Approved",
        "progress_report": "Progress Report Approved",
        "purchase_invoice": "Purchase Invoice Approved",
        "mall_shop": "Mall Shop Approved",
        "supplier": "Supplier Report Approved",
        "demolition_report": "Demolition Report Approved",
        "demolition_request": "Demolition Request Approved",
        "eviction_report": "Eviction Report Approved",
        "scroll_completion": "Scroll Completion Approved",
    }
    embed = discord.Embed(
        title=title_map.get(table, table.replace("_", " ").title()),
        color=discord.Color.green(),
        timestamp=approved_at or datetime.now(timezone.utc),
    )
    embed.add_field(name="Submitted by", value=submitter_name, inline=True)
    embed.add_field(name="Approved by", value=approver_name, inline=True)
    embed.add_field(name="Form ID", value=display_id(table, form_id), inline=True)

    if table == "recruitment":
        embed.add_field(name="New Player", value=f"{_coalesce(form_data.get('nickname'))} ({_coalesce(form_data.get('ingame_username'))})", inline=True)
        embed.add_field(name="Plots", value=str(form_data.get("plots", 0)), inline=True)
        if form_data.get("discord_username"):
            embed.add_field(name="Discord", value=_truncate(form_data.get("discord_username")), inline=True)
        if form_data.get("age"):
            embed.add_field(name="Age", value=_truncate(form_data.get("age")), inline=True)
    elif table == "progress_report":
        embed.add_field(name="Project", value=_truncate(form_data.get("project_name")), inline=True)
        embed.add_field(name="Time Spent", value=_truncate(form_data.get("time_spent")), inline=True)
        if form_data.get("helper_mentions"):
            embed.add_field(name="Helper", value=_truncate(form_data.get("helper_mentions")), inline=True)
        if form_data.get("note"):
            embed.add_field(name="Note", value=_truncate(form_data.get("note")), inline=False)
    elif table == "purchase_invoice":
        embed.add_field(name="Buyer", value=f"{_coalesce(form_data.get('purchasee_nickname'))} ({_coalesce(form_data.get('purchasee_ingame'))})", inline=True)
        embed.add_field(name="Type", value=_truncate(form_data.get("purchase_type")), inline=True)
        embed.add_field(name="Amount", value=f"{form_data.get('amount_deposited', 0)} coins", inline=True)
        if form_data.get("seller_display"):
            embed.add_field(name="Seller", value=_truncate(form_data.get("seller_display")), inline=True)
        if form_data.get("num_plots"):
            embed.add_field(name="Plots", value=f"{form_data.get('num_plots')} (total: {form_data.get('total_plots', 0)})", inline=True)
        if form_data.get("banner_color"):
            embed.add_field(name="Mall Shop", value=f"Color {form_data.get('banner_color')} · #{form_data.get('shop_number')}", inline=True)
        if form_data.get("house_number") and form_data.get("purchase_type") == "spawn_house":
            embed.add_field(name="Spawn House", value=f"House #{form_data.get('house_number')}", inline=True)
    elif table == "mall_shop":
        embed.add_field(name="Owner", value=_truncate(form_data.get("ingame_name")), inline=True)
        embed.add_field(name="Shops", value=str(form_data.get("amount_of_shops", 0)), inline=True)
        embed.add_field(name="Total", value=f"{form_data.get('total_amount', 0)} coins", inline=True)
        embed.add_field(name="Cycle", value=_truncate(form_data.get("payment_frequency")), inline=True)
        embed.add_field(name="Periods Paid", value=str(form_data.get("paid_periods", 1)), inline=True)
        if form_data.get("banner_color"):
            embed.add_field(name="Banner Color", value=_truncate(form_data.get("banner_color")), inline=True)
        if form_data.get("shop_number"):
            embed.add_field(name="Shop Number", value=_truncate(form_data.get("shop_number")), inline=True)
        if form_data.get("notes"):
            embed.add_field(name="Notes", value=_truncate(form_data.get("notes")), inline=False)
        if form_data.get("paid_until"):
            embed.add_field(name="Coverage Ends", value=_truncate(form_data.get("paid_until")), inline=True)
    elif table == "supplier":
        embed.add_field(name="Supplied Item", value=_truncate(form_data.get("supplied_item")), inline=True)
        embed.add_field(name="Quantity", value=str(form_data.get("quantity", 0)), inline=True)
        embed.add_field(name="Difficulty", value=_truncate(form_data.get("difficulty_to_obtain")), inline=True)
        embed.add_field(name="Time Spent", value=_truncate(form_data.get("time_spent")), inline=True)
    elif table == "demolition_report":
        embed.add_field(name="Player", value=_truncate(form_data.get("ingame_username")), inline=True)
        embed.add_field(name="Removed", value=_truncate(form_data.get("removed")), inline=True)
        embed.add_field(name="Items Stashed", value=_bool_text(form_data.get("stashed_items")), inline=True)
    elif table == "demolition_request":
        embed.add_field(name="Target Player", value=_truncate(form_data.get("ingame_username")), inline=True)
        embed.add_field(name="Reason", value=_truncate(form_data.get("reason")), inline=False)
    elif table == "eviction_report":
        embed.add_field(name="Owner", value=_truncate(form_data.get("ingame_owner")), inline=True)
        embed.add_field(name="Items Stored", value=_bool_text(form_data.get("items_stored")), inline=True)
        embed.add_field(name="Inactivity Period", value=_truncate(form_data.get("inactivity_period")), inline=True)
    elif table == "scroll_completion":
        scroll_type = _truncate(form_data.get("scroll_type"))
        embed.add_field(name="Scroll Type", value=scroll_type.capitalize() if scroll_type else "?", inline=True)
        embed.add_field(name="Items Stored", value=_bool_text(form_data.get("items_stored")), inline=True)

    _add_images(embed, form_data)
    footer_time = (approved_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")
    embed.set_footer(text=f"Approved by {approver_name} · {footer_time}")
    return embed


def build_summary(table: str, form_data: dict, form_id: int | None = None) -> str:
    prefix = FORM_TABLE_PREFIX.get(table, "unk")
    if table == "recruitment":
        return f"Recruited {form_data.get('nickname', '?')} ({form_data.get('ingame_username', '?')}) - {form_data.get('plots', 0)} plots"
    if table == "progress_report":
        note = form_data.get("note")
        text = f"Project '{form_data.get('project_name', '?')}' - {form_data.get('time_spent', '?')}"
        if note:
            text += f" · Note: {_truncate(note, 80)}"
        return text
    if table == "purchase_invoice":
        purchase_type = form_data.get("purchase_type", "?")
        text = f"Sale to {form_data.get('purchasee_nickname', '?')} for {form_data.get('amount_deposited', 0)} coins"
        if purchase_type == "spawn_house" and form_data.get("house_number"):
            text += f" (Spawn House #{form_data['house_number']})"
        return text
    if table == "mall_shop":
        return f"Mall shop rent for {form_data.get('ingame_name', '?')} - {form_data.get('amount_of_shops', 0)} shops / {form_data.get('total_amount', 0)} coins"
    if table == "supplier":
        return f"Supplier report for {form_data.get('supplied_item', '?')} - Qty {form_data.get('quantity', 0)} · {form_data.get('difficulty_to_obtain', '?')}"
    if table == "demolition_report":
        return f"Demolished {form_data.get('ingame_username', '?')} - {form_data.get('removed', '?')}"
    if table == "demolition_request":
        return f"Request to demolish {form_data.get('ingame_username', '?')} - Reason: {_truncate(form_data.get('reason', '?'), 50)}"
    if table == "eviction_report":
        return f"Evicted {form_data.get('ingame_owner', '?')} - Inactive {form_data.get('inactivity_period', '?')}"
    if table == "scroll_completion":
        return f"Scroll type: {form_data.get('scroll_type', '?')}"
    return f"Form ID {form_id if form_id is not None else prefix}"
