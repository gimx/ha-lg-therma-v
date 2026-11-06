"""Snapshot tests for the entities of every LG Therma V platform."""

from unittest.mock import patch

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from custom_components.lg_therma_v import PLATFORMS


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("platform", PLATFORMS)
async def test_platform_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: None,
    snapshot: SnapshotAssertion,
    platform: Platform,
) -> None:
    """Test every entity of a platform against its snapshot."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.lg_therma_v.PLATFORMS", [platform]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
