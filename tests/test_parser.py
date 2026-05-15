"""
Tests for the .dig parser.

Run from repo root:
    uv run pytest
or for verbose output:
    uv run pytest -v
"""

from pathlib import Path

import pytest

from dlc.parser.dig_parser import parse_dig_file
from dlc.parser.models import Circuit

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "sample_circuits" / "tier1_minimal"


def _load(name: str) -> Circuit:
    """Helper: parse a sample by filename (without path)."""
    return parse_dig_file(str(SAMPLES_DIR / name))


# -------------------------------------------------------------------
# Per-file structural tests
# -------------------------------------------------------------------

def test_single_and():
    c = _load("single_and.dig")
    assert len(c.components) == 5
    assert len(c.wires) == 8
    assert len(c.inputs()) == 2
    assert len(c.outputs()) == 1
    assert len(c.tunnels()) == 0

    input_labels = {inp.label for inp in c.inputs()}
    assert input_labels == {"A", "B"}

    output_labels = {out.label for out in c.outputs()}
    assert output_labels == {"Y"}

    gates = [comp for comp in c.components if comp.element_name == "And"]
    assert len(gates) == 1


def test_half_adder():
    c = _load("half_adder.dig")
    assert len(c.components) == 6
    assert len(c.wires) == 14
    assert len(c.inputs()) == 2
    assert len(c.outputs()) == 2

    assert {inp.label for inp in c.inputs()} == {"A", "B"}
    assert {out.label for out in c.outputs()} == {"Sum", "Carry"}

    gate_types = sorted(
        c.element_name for c in c.components
        if c.element_name in {"And", "Or", "XOr", "Not"}
    )
    assert gate_types == ["And", "XOr"]


def test_full_adder():
    c = _load("full_adder.dig")
    assert len(c.components) == 10
    assert len(c.wires) == 28
    assert len(c.inputs()) == 3
    assert len(c.outputs()) == 2

    assert {inp.label for inp in c.inputs()} == {"A", "B", "Cin"}
    assert {out.label for out in c.outputs()} == {"Sum", "Cout"}


def test_mux_2to1():
    c = _load("mux_2to1.dig")
    assert len(c.components) == 5
    assert len(c.wires) == 7
    assert len(c.inputs()) == 3
    assert len(c.outputs()) == 1

    assert {inp.label for inp in c.inputs()} == {"In0", "In1", "Sel"}

    mux = [comp for comp in c.components if comp.element_name == "Multiplexer"]
    assert len(mux) == 1


def test_splitter():
    c = _load("splitter_test.dig")
    assert len(c.components) == 6
    assert len(c.wires) == 12
    assert len(c.inputs()) == 1
    assert len(c.outputs()) == 4

    bus = c.inputs()[0]
    assert bus.label == "Bus"
    assert bus.bit_width() == 4

    splitter = next(comp for comp in c.components if comp.element_name == "Splitter")
    assert splitter.attributes.get("Input Splitting") == "4"
    assert splitter.attributes.get("Output Splitting") == "1,1,1,1"


def test_tunnel():
    c = _load("tunnel_test.dig")
    assert len(c.components) == 5
    assert len(c.wires) == 3
    assert len(c.inputs()) == 1
    assert len(c.outputs()) == 1
    assert len(c.tunnels()) == 2

    tunnel_nets = {t.attributes.get("NetName") for t in c.tunnels()}
    assert tunnel_nets == {"net1"}


def test_comparator():
    c = _load("comparator_4bit.dig")
    assert len(c.components) == 6
    assert len(c.wires) == 11
    assert len(c.inputs()) == 2
    assert len(c.outputs()) == 3

    assert {inp.label for inp in c.inputs()} == {"A", "B"}
    assert {out.label for out in c.outputs()} == {"Greater", "Equal", "Less"}

    for inp in c.inputs():
        assert inp.bit_width() == 4

    comp_el = next(c for c in c.components if c.element_name == "Comparator")
    assert comp_el.attributes.get("Bits") == 4


def test_register():
    c = _load("register_test.dig")
    assert len(c.components) == 5
    assert len(c.wires) == 5
    assert len(c.inputs()) == 1
    assert len(c.outputs()) == 1

    reg = next(c for c in c.components if c.element_name == "Register")
    assert reg.attributes.get("Bits") == 4

    clocks = [c for c in c.components if c.element_name == "Clock"]
    assert len(clocks) == 1


# -------------------------------------------------------------------
# Invariant tests
# -------------------------------------------------------------------

def test_all_samples_parse_without_error():
    """No sample file should ever raise an exception during parsing."""
    for dig_path in SAMPLES_DIR.glob("*.dig"):
        circuit = parse_dig_file(str(dig_path))
        # Each parse must produce a non-empty Circuit.
        assert isinstance(circuit, Circuit)
        assert len(circuit.components) > 0


def test_all_samples_have_format_version():
    """Every .dig file in our samples should have <version>2</version>."""
    for dig_path in SAMPLES_DIR.glob("*.dig"):
        c = parse_dig_file(str(dig_path))
        assert c.format_version == 2, f"{dig_path.name} has version {c.format_version}"


def test_source_path_recorded():
    """The Circuit should remember where it was loaded from."""
    c = _load("single_and.dig")
    assert c.source_path is not None
    assert "single_and.dig" in c.source_path


# -------------------------------------------------------------------
# Error-handling tests
# -------------------------------------------------------------------

def test_missing_file_raises():
    with pytest.raises(OSError):
        parse_dig_file("data/sample_circuits/tier1_minimal/does_not_exist.dig")


def test_malformed_xml_raises(tmp_path):
    """Truly broken XML should raise, not silently produce an empty Circuit."""
    bad = tmp_path / "broken.dig"
    bad.write_text("<circuit><not closed properly")
    with pytest.raises(Exception):
        parse_dig_file(str(bad))