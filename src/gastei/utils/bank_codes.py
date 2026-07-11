"""Mapping of BACEN (COMPE) bank codes to display names.

The 3-digit COMPE codes appear in the ``<BANKID>`` field of OFX files
exported by Brazilian banks. Curated list of the most common ones —
extend it as new banks show up in real-world statements. Lookup is
case-insensitive and ignores leading zeroes.
"""

from __future__ import annotations

# Source: https://www.bcb.gov.br/estabilidadefinanceira/relarb (COMPE register)
BANK_NAMES_BY_CODE: dict[str, str] = {
    "001": "Banco do Brasil",
    "033": "Santander",
    "041": "Banrisul",
    "070": "BRB",
    "077": "Inter",
    "104": "Caixa Econômica Federal",
    "208": "BTG Pactual",
    "212": "Banco Original",
    "237": "Bradesco",
    "260": "Nubank",
    "290": "PagBank",
    "323": "Mercado Pago",
    "336": "C6 Bank",
    "341": "Itaú",
    "356": "Banco Real",
    "380": "PicPay",
    "389": "Mercantil do Brasil",
    "422": "Banco Safra",
    "655": "Votorantim",
    "707": "Daycoval",
    "735": "Neon",
    "745": "Citibank",
    "756": "Sicoob",
    "748": "Sicredi",
}


def name_for_bank_code(code: str | int | None) -> str | None:
    """Resolve the bank display name from a COMPE code.

    Accepts ``260``, ``0260``, ``'260'`` and similar — strips leading
    zeroes and re-pads to 3 digits before looking up.
    """
    if code is None:
        return None
    normalized = str(code).strip().lstrip("0").zfill(3)
    return BANK_NAMES_BY_CODE.get(normalized)
