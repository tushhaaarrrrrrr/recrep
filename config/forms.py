from __future__ import annotations

from dataclasses import dataclass

FORM_TABLE_PREFIX: dict[str, str] = {
    "recruitment": "rec",
    "progress_report": "rep",
    "purchase_invoice": "inv",
    "mall_shop": "msh",
    "supplier": "sup",
    "demolition_report": "dem",
    "demolition_request": "dmr",
    "eviction_report": "evc",
    "scroll_completion": "scr",
}

FORM_CHANNEL_KEY: dict[str, str] = {
    "recruitment": "recruitment_channel_id",
    "progress_report": "progress_channel_id",
    "purchase_invoice": "invoice_channel_id",
    "mall_shop": "mall_shop_channel_id",
    "supplier": "supplier_channel_id",
    "demolition_report": "demolition_channel_id",
    "demolition_request": "demolition_channel_id",
    "eviction_report": "eviction_channel_id",
    "scroll_completion": "scroll_channel_id",
}

FORM_THREAD_LABEL: dict[str, str] = {
    "recruitment": "Recruitments",
    "progress_report": "Progress Reports",
    "purchase_invoice": "Invoices",
    "mall_shop": "Mall Shops",
    "supplier": "Suppliers",
    "demolition_report": "Demolitions",
    "demolition_request": "Demolition Requests",
    "eviction_report": "Evictions",
    "scroll_completion": "Scrolls",
}


class FormStatus:
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    HOLD = "hold"


def display_id(table: str, form_id: int) -> str:
    return f"{FORM_TABLE_PREFIX.get(table, 'unk')}_{form_id}"


def is_active_status(status: str | None) -> bool:
    return status in {FormStatus.PENDING, FormStatus.HOLD}


ALLOWED_STATUS = {
    FormStatus.PENDING,
    FormStatus.APPROVED,
    FormStatus.DENIED,
    FormStatus.HOLD,
}
