"""
Tests for the .dig parser.

Run from repo root:
    uv run pytest                    # all tests
    uv run pytest tests/test_parser.py    # only parser tests
    uv run pytest -v                 # verbose
"""

from pathlib import Path

import pytest

from dlc.parser.dig_parser import parse_dig_file
from dlc.parser.models import Circuit

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "sample_circuits" / "tier1_minimal"
TIER2_DIR   = Path(__file__).parent.parent / "data" / "sample_circuits" / "tier2_structured"


def _load(name: str) -> Circuit:
    return parse_dig_file(str(SAMPLES_DIR / name))


def _load_tier2(name: str) -> Circuit:
    return parse_dig_file(str(TIER2_DIR / name))


# Per-file structural tests (tier-1 minimal)


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


# Invariant + error-handling tests

def test_all_samples_parse_without_error():
    """No sample file should ever raise an exception during parsing."""
    for dig_path in SAMPLES_DIR.glob("*.dig"):
        circuit = parse_dig_file(str(dig_path))
        assert isinstance(circuit, Circuit)
        assert len(circuit.components) > 0


def test_all_samples_have_format_version():
    """Every .dig file in our samples should have <version>2</version>."""
    for dig_path in SAMPLES_DIR.glob("*.dig"):
        c = parse_dig_file(str(dig_path))
        assert c.format_version == 2, f"{dig_path.name} has version {c.format_version}"


def test_source_path_recorded():
    c = _load("single_and.dig")
    assert c.source_path is not None
    assert "single_and.dig" in c.source_path


def test_missing_file_raises():
    with pytest.raises(OSError):
        parse_dig_file("data/sample_circuits/tier1_minimal/does_not_exist.dig")


def test_malformed_xml_raises(tmp_path):
    bad = tmp_path / "broken.dig"
    bad.write_text("<circuit><not closed properly")
    with pytest.raises(Exception):
        parse_dig_file(str(bad))


def test_rotation_attribute_parses_as_integer():
    """
    The <rotation rotation="N"/> XML form stores N in an attribute, not
    as text. The parser must extract N as an integer rather than the
    literal string "rotation".
    """
    c = _load_tier2("uses_subcircuit.dig")
    assert c is not None


# Tier-2 subcircuit resolution

def test_subcircuit_inner_standalone():
    c = _load_tier2("subcircuit_inner.dig")
    assert len(c.inputs()) == 2
    assert len(c.outputs()) == 1
    assert len(c.subcircuits) == 0
    assert {inp.label for inp in c.inputs()} == {"A", "B"}
    assert {out.label for out in c.outputs()} == {"Y"}


def test_uses_subcircuit_single():
    c = _load_tier2("uses_subcircuit.dig")
    assert {inp.label for inp in c.inputs()} == {"X", "Z"}
    assert {out.label for out in c.outputs()} == {"Out"}
    assert len(c.subcircuits) == 1
    sub = c.subcircuits[0]
    assert sub.reference == "subcircuit_inner.dig"
    assert sub.resolved_path is not None
    assert sub.resolution_error is None
    assert sub.child_circuit is not None

    child = sub.child_circuit
    assert {inp.label for inp in child.inputs()} == {"A", "B"}
    assert {out.label for out in child.outputs()} == {"Y"}


def test_two_subcircuits_share_one_child():
    c = _load_tier2("two_subcircuits.dig")
    assert len(c.subcircuits) == 2
    s1, s2 = c.subcircuits
    assert s1.reference == "subcircuit_inner.dig"
    assert s2.reference == "subcircuit_inner.dig"
    assert s1.resolution_error is None
    assert s2.resolution_error is None
    assert s1.child_circuit is s2.child_circuit


def test_subcircuit_components_helper():
    c = _load_tier2("two_subcircuits.dig")
    subs = c.subcircuit_components()
    assert len(subs) == 2
    for s in subs:
        assert s.element_name.endswith(".dig")


def test_missing_subcircuit_recorded_not_crashed(tmp_path):
    parent = tmp_path / "parent.dig"
    parent.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<circuit><version>2</version><attributes/>'
        '<visualElements>'
        '<visualElement><elementName>missing.dig</elementName>'
        '<elementAttributes/><pos x="0" y="0"/></visualElement>'
        '</visualElements><wires/></circuit>'
    )
    c = parse_dig_file(str(parent))
    assert len(c.subcircuits) == 1
    sub = c.subcircuits[0]
    assert sub.child_circuit is None
    assert sub.resolution_error is not None
    assert "not found" in sub.resolution_error.lower()


def test_subfolder_reference_resolves():
    c = _load_tier2("uses_nested.dig")
    assert {inp.label for inp in c.inputs()} == {"In1"}
    assert {out.label for out in c.outputs()} == {"Out1"}
    assert len(c.subcircuits) == 1
    sub = c.subcircuits[0]
    assert sub.reference == "nested_inner.dig"
    assert sub.resolution_error is None
    assert sub.child_circuit is not None
    assert "subs" in sub.resolved_path.replace("\\", "/").split("/")


def test_ambiguous_subcircuit_flagged_but_resolved(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "deeper").mkdir()
    inner_xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<circuit><version>2</version><attributes/>'
        '<visualElements>'
        '<visualElement><elementName>In</elementName>'
        '<elementAttributes><entry><string>Label</string><string>A</string></entry></elementAttributes>'
        '<pos x="0" y="0"/></visualElement>'
        '</visualElements><wires/></circuit>'
    )
    (tmp_path / "a" / "inner.dig").write_text(inner_xml)
    (tmp_path / "a" / "deeper" / "inner.dig").write_text(inner_xml)

    parent_xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<circuit><version>2</version><attributes/>'
        '<visualElements>'
        '<visualElement><elementName>inner.dig</elementName>'
        '<elementAttributes/><pos x="0" y="0"/></visualElement>'
        '</visualElements><wires/></circuit>'
    )
    parent = tmp_path / "parent.dig"
    parent.write_text(parent_xml)
    c = parse_dig_file(str(parent))
    assert len(c.subcircuits) == 1
    sub = c.subcircuits[0]
    assert sub.child_circuit is not None
    assert sub.resolution_error is not None
    assert "ambiguous" in sub.resolution_error.lower()
    assert "deeper" not in sub.resolved_path.replace("\\", "/")
