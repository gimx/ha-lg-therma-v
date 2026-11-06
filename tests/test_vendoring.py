"""Guards that the integration uses its vendored library and nothing else."""

import ast
from pathlib import Path

INTEGRATION = Path(__file__).parent.parent / "custom_components" / "lg_therma_v"


def test_the_library_is_imported_from_the_vendored_copy() -> None:
    """Test no module imports the library as a top-level package.

    A top-level import works wherever the library happens to be installed, such
    as a developer's machine, and fails on a Home Assistant that only has the
    vendored copy.
    """
    for path in INTEGRATION.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                assert not (node.module or "").startswith("lg_therma_v_modbus"), (
                    f"{path.name} imports {node.module} absolutely"
                )
            if isinstance(node, ast.Import):
                assert not any(
                    alias.name.startswith("lg_therma_v_modbus") for alias in node.names
                ), f"{path.name} imports the library absolutely"


def test_the_vendored_copy_is_complete() -> None:
    """Test the library's package is in the integration."""
    assert (INTEGRATION / "lg_therma_v_modbus" / "__init__.py").is_file()
