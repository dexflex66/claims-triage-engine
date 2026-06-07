"""Connector registry by country/payer."""
from __future__ import annotations

from connectors.india_preauth import IndiaPreauthConnector
from connectors.us_278_837 import US278837Connector


def get_connector(country: str, payer_id: str):
    c = (country or "").upper()
    p = (payer_id or "").upper()
    if c == "US":
        return US278837Connector()
    if c == "IN":
        return IndiaPreauthConnector()
    raise ValueError(f"No connector configured for country={country} payer={payer_id}")
