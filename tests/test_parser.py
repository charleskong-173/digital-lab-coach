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


# -------------------------------------------------------------------
# Function 1 Tier 2 — subcircuit resolution tests
# -------------------------------------------------------------------

TIER2_DIR = Path(__file__).parent.parent / "data" / "sample_circuits" / "tier2_structured"


def _load_tier2(name: str) -> Circuit:
    return parse_dig_file(str(TIER2_DIR / name))


def test_subcircuit_inner_standalone():
    """The leaf subcircuit is itself a normal flat circuit"""
    c = _load_tier2("subcircuit_inner.dig")
    assert len(c.inputs()) == 2
    assert len(c.outputs()) == 1
    assert len(c.subcircuits) == 0  

    assert {inp.label for inp in c.inputs()} == {"A", "B"}
    assert {out.label for out in c.outputs()} == {"Y"}


def test_uses_subcircuit_single():
    """uses_subcircuit.dig references subcircuit_inner.dig exactly once."""
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
    """Two references to the same .dig should share the same child Circuit object (cache hit)."""
    c = _load_tier2("two_subcircuits.dig")

    assert len(c.subcircuits) == 2
    s1, s2 = c.subcircuits

    assert s1.reference == "subcircuit_inner.dig"
    assert s2.reference == "subcircuit_inner.dig"
    assert s1.resolution_error is None
    assert s2.resolution_error is None

    assert s1.child_circuit is s2.child_circuit


def test_subcircuit_components_helper():
    """The convenience method should return only .dig-reference components."""
    c = _load_tier2("two_subcircuits.dig")
    subs = c.subcircuit_components()
    assert len(subs) == 2
    for s in subs:
        assert s.element_name.endswith(".dig")


def test_missing_subcircuit_recorded_not_crashed(tmp_path):
    """If a parent references a missing file, parsing succeeds with an error logged."""
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
    """A reference to a file in a subfolder (no path in XML) should still resolve."""
    c = _load_tier2("uses_nested.dig")

    assert {inp.label for inp in c.inputs()} == {"In1"}
    assert {out.label for out in c.outputs()} == {"Out1"}

    assert len(c.subcircuits) == 1
    sub = c.subcircuits[0]
    assert sub.reference == "nested_inner.dig"
    assert sub.resolution_error is None
    assert sub.child_circuit is not None
    # The resolved path should land inside the subs/ folder.
    assert "subs" in sub.resolved_path.replace("\\", "/").split("/")


def test_ambiguous_subcircuit_flagged_but_resolved(tmp_path):
    """Two files with the same name in different subfolders → resolve to shallowest, flag warning."""
    # Layout:
    #   parent.dig (references "inner.dig")
    #   a/inner.dig
    #   a/deeper/inner.dig
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
    # Should have picked the shallower path.
    assert "deeper" not in sub.resolved_path.replace("\\", "/")

# -------------------------------------------------------------------
# Function 2: net building
# -------------------------------------------------------------------

from dlc.parser.netlist import build_netlist, NetList


def test_netlist_single_and():
    """single_and: A,B inputs, AND, Y output. Expect a connected structure."""
    c = parse_dig_file(str(SAMPLES_DIR / "single_and.dig"))
    nl = build_netlist(c)
    assert isinstance(nl, NetList)
    assert len(nl.nets) > 0

    has_real_connection = any(
        net.drivers() and net.sinks() for net in nl.nets
    )
    assert has_real_connection


def test_netlist_tunnel_connects_across():
    """
    tunnel_test: input A -> Tunnel(net1) ... Tunnel(net1) -> NOT -> Y.
    The two tunnels share NetName 'net1', so A's signal must reach the NOT
    even though there's no continuous wire between them.
    """
    c = parse_dig_file(str(SAMPLES_DIR / "tunnel_test.dig"))
    nl = build_netlist(c)
    net1_nets = [n for n in nl.nets if "net1" in n.tunnel_names]
    assert len(net1_nets) == 1, "Both 'net1' tunnels should be in ONE net"


def test_netlist_subcircuit_pins_via_wires():
    """
    uses_subcircuit: the subcircuit reference has no known geometry, so its
    connections come from implicit pins (wire endpoints near it).
    We just assert the netlist builds and the subcircuit component got at
    least one implicit pin.
    """
    c = parse_dig_file(
        str(TIER2_DIR / "uses_subcircuit.dig")
    )
    nl = build_netlist(c)

    sub_idx = next(
        i for i, comp in enumerate(c.components)
        if comp.element_name.endswith(".dig")
    )
    implicit = [
        p for net in nl.nets for p in net.pins
        if p.component_index == sub_idx
    ]
    assert len(implicit) > 0, "Subcircuit should get implicit pins from wires"


def test_netlist_all_samples_build():
    """Net building must not crash on any tier-1 or tier-2 sample."""
    import glob
    for f in glob.glob("data/sample_circuits/**/*.dig", recursive=True):
        c = parse_dig_file(f)
        nl = build_netlist(c)
        assert isinstance(nl, NetList)


def test_netlist_summary_runs():
    c = parse_dig_file(str(SAMPLES_DIR / "full_adder.dig"))
    nl = build_netlist(c)
    s = nl.summary()
    assert "NetList:" in s

# -------------------------------------------------------------------
# Function 2 Stage 2, 2.5, 3 rework :endpoint-primary attachment.
# -------------------------------------------------------------------

def test_netlist_single_and_clean():
    """
    single_and: 2-input AND wideShape, exactly 3 logical nets
    (A->AND.in0, B->AND.in1, AND.Y->Y). Before the rework this reported
    5/3/2 because predicted in1/Y coords didn't sit on wire endpoints.
    """
    c = parse_dig_file(str(SAMPLES_DIR / "single_and.dig"))
    nl = build_netlist(c)
    assert len(nl.nets) == 3
    assert sum(1 for n in nl.nets if n.drivers()) == 3
    assert sum(1 for n in nl.nets if n.pins and not n.drivers()) == 0
    assert sum(1 for n in nl.nets if len(n.drivers()) > 1) == 0


def test_netlist_half_adder_clean():
    """
    Half-adder: A and B each fan out to XOR and AND.
    Expect 4 nets (A, B, Sum, Carry), all driven, no phantoms.
    """
    c = parse_dig_file(str(SAMPLES_DIR / "half_adder.dig"))
    nl = build_netlist(c)
    assert len(nl.nets) == 4
    assert sum(1 for n in nl.nets if n.drivers()) == 4
    assert sum(1 for n in nl.nets if n.pins and not n.drivers()) == 0


def test_netlist_full_adder_clean():
    """
    Full adder: 3 input nets + XOR1.Y fanout + 4 output-side nets = 8 nets,
    all driven. Heavy stress test for wideShape gate snapping (5 gates).
    """
    c = parse_dig_file(str(SAMPLES_DIR / "full_adder.dig"))
    nl = build_netlist(c)
    assert len(nl.nets) == 8
    assert sum(1 for n in nl.nets if n.drivers()) == 8
    assert sum(1 for n in nl.nets if n.pins and not n.drivers()) == 0


def test_netlist_wideshape_even_n_gates_attach_all_inputs():
    """
    Even-N wideShape AND gates (N=2, 4, 6) have a 40-unit gap in the middle
    of the input column. Endpoint-primary snapping plus the corrected
    geometry must attach every input pin.
    """
    cases = {
        "single_and.dig": 2,
        "four_inputand.dig": 4,
        "six_inputand.dig": 6,
    }
    for fname, expected_inputs in cases.items():
        c = parse_dig_file(str(SAMPLES_DIR / fname))
        nl = build_netlist(c)
        and_idx = next(
            i for i, comp in enumerate(c.components)
            if comp.element_name == "And"
        )
        and_input_pins = [
            p for net in nl.nets for p in net.pins
            if p.component_index == and_idx and p.direction == "in"
        ]
        assert len(and_input_pins) == expected_inputs, (
            f"{fname}: expected {expected_inputs} AND inputs, got "
            f"{len(and_input_pins)} ({[p.pin_name for p in and_input_pins]})"
        )


def test_netlist_register_en_pin_attached():
    """
    register_test: Const(1) ties the Register's en pin. Verify the
    Register has exactly 4 pins (D, C, en, Q) and all are on real nets.
    """
    c = parse_dig_file(str(SAMPLES_DIR / "register_test.dig"))
    nl = build_netlist(c)
    reg_idx = next(
        i for i, comp in enumerate(c.components)
        if comp.element_name == "Register"
    )
    reg_pins = [
        p for net in nl.nets for p in net.pins
        if p.component_index == reg_idx
    ]
    assert sorted(p.pin_name for p in reg_pins) == ["C", "D", "Q", "en"]
    # Every register pin should sit in a net with at least one other pin
    # (it's wired to something) — no dangling singletons.
    for p in reg_pins:
        net = nl.net_at(p.x, p.y)
        assert net is not None
        assert len(net.pins) >= 2, (
            f"Register pin {p.pin_name} ended up alone in a singleton net"
        )


def test_netlist_tier1_no_phantom_singletons():
    """
    Tier-1 samples are flat circuits with only known-geometry components.
    After the endpoint-primary rework, none of them should report any
    'undriven-with-pins' nets — every pin should sit on a real wire net.
    Testcase components are exempt (they legitimately have no wires).
    """
    import glob
    for f in glob.glob("data/sample_circuits/tier1_minimal/*.dig"):
        c = parse_dig_file(f)
        nl = build_netlist(c)
        undriven = [n for n in nl.nets if n.pins and not n.drivers()]
        assert undriven == [], (
            f"{f}: {len(undriven)} undriven-with-pins net(s) — "
            f"phantom singletons should be gone after the rework. "
            f"summary: {nl.summary()}"
        )


def test_netlist_subcircuit_one_implicit_pin_per_net():
    """
    Implicit pins for a subcircuit reference should dedupe per net.
    In uses_subcircuit.dig the subcircuit has 3 logical connections
    (X, Z, Out). It must end up with exactly 3 implicit pins, not one
    per wire endpoint touching it.
    """
    c = parse_dig_file(str(TIER2_DIR / "uses_subcircuit.dig"))
    nl = build_netlist(c)
    sub_idx = next(
        i for i, comp in enumerate(c.components)
        if comp.element_name.endswith(".dig")
    )
    sub_pins = [
        p for net in nl.nets for p in net.pins
        if p.component_index == sub_idx
    ]
    # Each pin is in a distinct net.
    nets_with_sub = {
        nl.net_at(p.x, p.y).net_id for p in sub_pins
    }
    assert len(nets_with_sub) == len(sub_pins), (
        "Subcircuit should have at most one implicit pin per net"
    )
    assert len(sub_pins) == 3, (
        f"Expected 3 implicit pins on the subcircuit (X, Z, Out), got "
        f"{len(sub_pins)}: {[(p.x, p.y) for p in sub_pins]}"
    )


# -------------------------------------------------------------------
# Function 2 Stage 3: signal-flow graph (networkx)
# -------------------------------------------------------------------

from dlc.parser.graph import (
    build_signal_graph,
    input_component_indices,
    output_component_indices,
    reachable_outputs_from_inputs,
)


def _idx_by_label(circuit, label):
    return next(
        i for i, c in enumerate(circuit.components) if c.label == label
    )


def _idx_by_element(circuit, element_name):
    return next(
        i for i, c in enumerate(circuit.components)
        if c.element_name == element_name
    )


def test_graph_single_and_edges():
    """single_and: signal flow is In(A)->AND, In(B)->AND, AND->Out(Y)."""
    c = parse_dig_file(str(SAMPLES_DIR / "single_and.dig"))
    nl = build_netlist(c)
    g = build_signal_graph(c, nl)

    in_a = _idx_by_label(c, "A")
    in_b = _idx_by_label(c, "B")
    and_idx = _idx_by_element(c, "And")
    out_y = _idx_by_label(c, "Y")

    assert g.has_edge(in_a, and_idx)
    assert g.has_edge(in_b, and_idx)
    assert g.has_edge(and_idx, out_y)
    assert g.number_of_edges() == 3


def test_graph_node_attributes_carry_component():
    c = parse_dig_file(str(SAMPLES_DIR / "single_and.dig"))
    nl = build_netlist(c)
    g = build_signal_graph(c, nl)

    and_idx = _idx_by_element(c, "And")
    assert g.nodes[and_idx]["element_name"] == "And"
    assert g.nodes[and_idx]["component"] is c.components[and_idx]


def test_graph_edge_attributes_have_pin_names_and_net_id():
    """Edges should record which pin drove and which pin received."""
    c = parse_dig_file(str(SAMPLES_DIR / "single_and.dig"))
    nl = build_netlist(c)
    g = build_signal_graph(c, nl)

    and_idx = _idx_by_element(c, "And")
    out_y = _idx_by_label(c, "Y")
    edges = list(g.get_edge_data(and_idx, out_y).values())
    assert len(edges) == 1
    e = edges[0]
    assert e["driver_pin"] == "Y"
    assert e["sink_pin"] == "in"
    assert isinstance(e["net_id"], int)


def test_graph_full_adder_inputs_reach_outputs():
    """In a full adder every input must reach every output."""
    c = parse_dig_file(str(SAMPLES_DIR / "full_adder.dig"))
    nl = build_netlist(c)
    g = build_signal_graph(c, nl)

    reach = reachable_outputs_from_inputs(c, g)
    out_idxs = set(output_component_indices(c))
    for in_idx, outs in reach.items():
        label = c.components[in_idx].label
        assert outs == out_idxs, (
            f"Input {label} reaches {outs}, expected {out_idxs}"
        )


def test_graph_tunnel_carries_signal_via_net():
    """
    tunnel_test: tunnel-only handoff. The graph must still have an edge
    In(A) -> NOT (the tunnel sits in the middle but doesn't appear as a
    driver or sink — its NetName merging at netlist time is what carries
    the signal).
    """
    c = parse_dig_file(str(SAMPLES_DIR / "tunnel_test.dig"))
    nl = build_netlist(c)
    g = build_signal_graph(c, nl)

    in_a = _idx_by_label(c, "A")
    not_idx = _idx_by_element(c, "Not")
    out_y = _idx_by_label(c, "Y")

    assert g.has_edge(in_a, not_idx)
    assert g.has_edge(not_idx, out_y)


def test_graph_half_adder_topology():
    """
    Half-adder: In(A) and In(B) each drive XOr and And; XOr drives Sum;
    And drives Carry. Expect 6 edges total: 2 (A) + 2 (B) + 1 (Sum) + 1
    (Carry).
    """
    c = parse_dig_file(str(SAMPLES_DIR / "half_adder.dig"))
    nl = build_netlist(c)
    g = build_signal_graph(c, nl)

    in_a = _idx_by_label(c, "A")
    in_b = _idx_by_label(c, "B")
    xor_idx = _idx_by_element(c, "XOr")
    and_idx = _idx_by_element(c, "And")
    sum_idx = _idx_by_label(c, "Sum")
    carry_idx = _idx_by_label(c, "Carry")

    assert g.has_edge(in_a, xor_idx)
    assert g.has_edge(in_a, and_idx)
    assert g.has_edge(in_b, xor_idx)
    assert g.has_edge(in_b, and_idx)
    assert g.has_edge(xor_idx, sum_idx)
    assert g.has_edge(and_idx, carry_idx)
    assert g.number_of_edges() == 6


def test_graph_builds_for_all_samples():
    """Graph builder must not crash on any sample."""
    import glob
    for f in glob.glob("data/sample_circuits/**/*.dig", recursive=True):
        c = parse_dig_file(f)
        nl = build_netlist(c)
        g = build_signal_graph(c, nl)
        # Every component should appear as a node.
        assert g.number_of_nodes() == len(c.components), f


def test_graph_input_output_helpers():
    c = parse_dig_file(str(SAMPLES_DIR / "full_adder.dig"))
    in_idxs = input_component_indices(c)
    out_idxs = output_component_indices(c)
    assert {c.components[i].label for i in in_idxs} == {"A", "B", "Cin"}
    assert {c.components[i].label for i in out_idxs} == {"Sum", "Cout"}


# -------------------------------------------------------------------
# Function 2 Stage 2.5: subcircuit-instance pin direction resolution.
# -------------------------------------------------------------------

def test_subcircuit_pins_resolved_to_child_io_labels():
    """
    uses_subcircuit instance pins should be named after the child's
    In/Out element Labels (A, B, Y) and have proper directions, not
    'wire@x,y' / 'unknown'.
    """
    c = parse_dig_file(str(TIER2_DIR / "uses_subcircuit.dig"))
    nl = build_netlist(c)
    sub_idx = next(
        i for i, comp in enumerate(c.components)
        if comp.element_name.endswith(".dig")
    )
    sub_pins = [
        p for net in nl.nets for p in net.pins
        if p.component_index == sub_idx
    ]
    assert sorted(p.pin_name for p in sub_pins) == ["A", "B", "Y"]
    by_name = {p.pin_name: p for p in sub_pins}
    assert by_name["A"].direction == "in"
    assert by_name["B"].direction == "in"
    assert by_name["Y"].direction == "out"


def test_two_subcircuits_no_phantom_pins():
    """
    two_subcircuits.dig has wire L-bends at (440, 260), (440, 200),
    (460, 180) that are routing-only, not subcircuit pins. After the
    degree-1 filter on implicit-pin attachment, neither subcircuit
    instance should claim them. Net summary must be 6 driven / 0
    undriven / 0 multi-driver.
    """
    c = parse_dig_file(str(TIER2_DIR / "two_subcircuits.dig"))
    nl = build_netlist(c)
    assert len(nl.nets) == 6
    assert sum(1 for n in nl.nets if n.drivers()) == 6
    assert sum(1 for n in nl.nets if n.pins and not n.drivers()) == 0
    assert sum(1 for n in nl.nets if len(n.drivers()) > 1) == 0


def test_subcircuit_signal_flow_reaches_outputs():
    """
    Once subcircuit pin directions are resolved, every input must reach
    every output in tier-2 parent circuits (uses_subcircuit,
    two_subcircuits, uses_nested).
    """
    cases = ["uses_subcircuit.dig", "two_subcircuits.dig", "uses_nested.dig"]
    for fname in cases:
        c = parse_dig_file(str(TIER2_DIR / fname))
        nl = build_netlist(c)
        g = build_signal_graph(c, nl)
        out_idxs = set(output_component_indices(c))
        reach = reachable_outputs_from_inputs(c, g)
        for in_idx, outs in reach.items():
            assert outs == out_idxs, (
                f"{fname}: input {c.components[in_idx].label} reaches "
                f"{outs}, expected {out_idxs}"
            )