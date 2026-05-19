# Testing Notes

Last updated: 2026/5/19

---

## Quick reference

From repo root (These are all sample circuit tests, if you want to manually test a new .dig refer to 
" How to test manually" in each function specified below):

```bash
uv run pytest                              # Run all tests
uv run pytest -v                           # Show each test name
uv run pytest tests/test_netlist.py        # Run the test in one test file
uv run pytest -k subcircuit                # Name-match filter
uv run pytest tests/test_netlist.py::test_buggy_multi_driver_flags_one_net_with_two_drivers
                                           # Run one specific test
```

| File | Covers | # tests |
|---|---|---:|
| `tests/test_parser.py` | F1: parser, errors, subcircuit resolution | 25 |
| `tests/test_pin_geometry.py` | F2: pin offset tables + rotation | 20 |
| `tests/test_netlist.py` | F2: nets, buggy samples, subcircuit pin direction | 16 |
| `tests/test_graph.py` | F2: signal-flow graph + reachability | 11 |

---

## Function 1 — Parser (`test_parser.py`)

### What F1 produces

A `Circuit` object containing:
- `components`: list of `Component` (element_name, position, attributes dict, label)
- `wires`: list of `Wire` (p1, p2 Position pairs)
- `subcircuits`: list of resolved `SubcircuitReference` (recursively loaded child Circuits)
- `format_version`, `source_path`

### How to test manually


```python
uv run python -c "
from dlc.parser.dig_parser import parse_dig_file
c = parse_dig_file('data/sample_circuits/tier3_realistic/tier3_calculator.dig') # your .dig
print(f'Counts: components={len(c.components)} wires={len(c.wires)} subcircuits={len(c.subcircuits)}')
print()
print('Inputs:')
for inp in c.inputs():
    print(f'  {inp.label} ({inp.bit_width()}-bit)')
print('Outputs:')
for out in c.outputs():
    print(f'  {out.label} ({out.bit_width()}-bit)')
print()
print('All components (use the index for c.components[i] in the pin-geometry test):')
for i, comp in enumerate(c.components):
    attrs = {k: v for k, v in comp.attributes.items() if k != 'Label'}
    print(f'  [{i}] {comp.element_name} @ ({comp.position.x},{comp.position.y}) label={comp.label} attrs={attrs}')
"
# basic info
```

### Test categories

1. **Per-file structural sanity** (`test_single_and`, `test_half_adder`, `test_full_adder`, `test_mux_2to1`, `test_splitter`, `test_tunnel`, `test_comparator`, `test_register`) — assert exact component / wire / In / Out counts for known samples. Failure here means the parser missed or double-counted something.
2. **Invariants across all samples** — `test_all_samples_parse_without_error`, `test_all_samples_have_format_version`. Pipeline must never crash on a student file.
3. **Error handling** — `test_missing_file_raises`, `test_malformed_xml_raises`.
4. **Subcircuit resolution** — `test_uses_subcircuit_single`, `test_two_subcircuits_share_one_child`, `test_subfolder_reference_resolves`, `test_ambiguous_subcircuit_flagged_but_resolved`, `test_missing_subcircuit_recorded_not_crashed`. A parent's child must be fully loaded with its own In/Out labels so the LLM can speak hierarchically.
5. **Rotation parsing** — `test_rotation_attribute_parses_as_integer`. Ensures the `<rotation rotation="N"/>` XML quirk doesn't store the string `"rotation"`.

---

## Function 2 — Netlist + signal-flow graph

Split across three test files: `test_pin_geometry.py`, `test_netlist.py`, `test_graph.py`.

### F2: Pin geometry (`test_pin_geometry.py`)

#### What it produces

For each Component, the absolute pin positions and directions (after applying rotation). This is the table that lets F2 know "this AND gate's `in1` is at coord (X, Y) on the canvas."

#### How to test manually

```python
uv run python -c "
from dlc.parser.dig_parser import parse_dig_file
from dlc.parser.pin_geometry import absolute_pin_positions
c = parse_dig_file('data/sample_circuits/tier3_realistic/tier3_calculator.dig') # your .dig
for pos, spec in absolute_pin_positions(c.components[7]):  # change i in c.components[i] to view geometry for different components
    print(spec.name, (pos.x, pos.y), spec.direction)
"
```

#### Test categories

1. **Static-table elements** — In, Out, Const, Clock, Tunnel, Ground, VDD all have a single pin at the anchor.
2. **Multi-pin static elements** — Add, BitExtender, BarrelShifter, ROM each carry a verified-empirically pin set.
3. **Dynamic elements** — Mux 2-input uses spacing 40; Mux 4+-input uses spacing 20; Decoder sel sits at `(20, n*20)`; Splitter honors `splitterSpreading`; wideShape even-N gates use the 40-unit middle-gap layout.
4. **Rotation** — formula tests for r=1/2/3 plus an integration test that a rotated Multiplexer's pins land at the expected absolute coords.


### F2: Netlist construction (`test_netlist.py`)

#### What it produces

A `NetList` where each `Net` has:
- `coords`: every (x, y) point that's electrically the same signal
- `pins`: every pin (component_index, pin_name, direction) attached to this net
- `tunnel_names`: any Tunnel NetNames merging into this net
- `drivers()` / `sinks()` helpers

Plus `summary()`: `"NetList: N nets, M driven, K undriven-with-pins, J multi-driver"`.

#### How to test manually

```python
uv run python -c "
from dlc.parser.dig_parser import parse_dig_file
from dlc.parser.netlist import build_netlist
c = parse_dig_file('data/sample_circuits/tier3_realistic/tier3_calculator.dig') # your .dig
nl = build_netlist(c)
print(nl.summary())
print()
print('All nets:')
for net in nl.nets:
    flags = []
    if net.pins and not net.drivers():
        flags.append('DANGLING')
    if len(net.drivers()) > 1:
        flags.append('MULTI-DRIVER')
    flag_str = ' [' + ','.join(flags) + ']' if flags else ''
    pins = [(c.components[p.component_index].element_name, p.pin_name, p.direction) for p in net.pins]
    tnames = sorted(net.tunnel_names) if net.tunnel_names else None
    print(f'  net {net.net_id}{flag_str}: coords={len(net.coords)}, pins={pins}, tunnels={tnames}')
"
```

#### Test categories

1. **Sanity** — `test_netlist_builds_for_all_samples`, `test_netlist_summary_runs`.
2. **Per-sample exact net counts** — `test_netlist_single_and_exact_three_nets`, `test_netlist_half_adder_exact_four_nets`, `test_netlist_full_adder_exact_eight_nets`. If these drift, something silently changed in pin geometry or union-find.
3. **Clean tier-1 invariant** — `test_tier1_minimal_all_clean` sweeps every tier-1 file and asserts 0 undriven, 0 multi-driver.
4. **wideShape attachment** — `test_wideshape_even_n_inputs_all_attached` verifies the 40-unit-gap layout actually attaches every input pin.
5. **Register fully wired** — `test_register_pins_all_attached_and_wired`.
6. **Tunnel cross-gap** — `test_tunnel_unifies_nets_across_gap` confirms same-named Tunnels collapse into one net.
7. **Tier-1 buggy regressions** (each surfaces a distinct signature):
   - `test_buggy_dangling_input_flags_one_undriven_singleton` — dangling_input.dig produces exactly 1 net with And.in1 as sole sink.
   - `test_buggy_multi_driver_flags_one_net_with_two_drivers` — multi_driver.dig produces exactly 1 multi-driver net with 2 In drivers.
   - `test_buggy_combinational_loop_keeps_signal_path` — netlist builds; cycle detection is F8's job.
   - `test_buggy_width_mismatch_netlist_is_structurally_clean` — width mismatch is F6's job, F2 should not flag it.
8. **Tier-2 subcircuit direction resolution** — `test_subcircuit_pins_get_child_io_labels` confirms the instance's implicit pins get their child's In/Out Labels (A, B, Y).
9. **Phantom-free subcircuit** — `test_two_subcircuits_no_phantom_pins` and `test_subcircuit_one_implicit_pin_per_net` guard against wire L-bends being misclaimed as subcircuit pins.
10. **Subcircuit pin cap** — `test_subcircuit_implicit_pin_count_capped_to_child_ports` ensures a wide IMPLICIT_PIN_RADIUS doesn't pull in unrelated endpoints.
11. **Tier-3 calculator regression** — `test_tier3_calculator_full_io_reachability` and `test_tier3_bool_unit_fully_clean` are the canonical "complex circuit with subcircuit ref" smoke tests.


### F2: Signal-flow graph + reachability (`test_graph.py`)

#### What it produces

A `networkx.MultiDiGraph`:
- Nodes = component indices (with `element_name` and `component` attrs).
- Edges = directed driver→sink within each net (with `driver_pin`, `sink_pin`, `net_id` attrs).

Plus helpers: `input_component_indices`, `output_component_indices`, `reachable_outputs_from_inputs`.

#### How to test manually

```python
uv run python -c "
from dlc.parser.dig_parser import parse_dig_file
from dlc.parser.netlist import build_netlist
from dlc.parser.graph import build_signal_graph, reachable_outputs_from_inputs
c = parse_dig_file('data/sample_circuits/tier3_realistic/tier3_calculator.dig') # your .dig
nl = build_netlist(c)
g = build_signal_graph(c, nl)
reach = reachable_outputs_from_inputs(c, g)
for in_idx, outs in reach.items():
    print(c.components[in_idx].label, '->',
          [c.components[i].label for i in outs])
"
```

Text dumb visulization: 
```python
uv run python -c "
from dlc.parser.dig_parser import parse_dig_file
from dlc.parser.netlist import build_netlist
from dlc.parser.graph import build_signal_graph
c = parse_dig_file('data/sample_circuits/tier3_realistic/tier3_calculator.dig') # your .dig
nl = build_netlist(c)
g = build_signal_graph(c, nl)
print(f'Nodes: {g.number_of_nodes()}, Edges: {g.number_of_edges()}')
print()
print('Edges (driver -> sink, with pin names and net id):')
for u, v, data in g.edges(data=True):
    src = c.components[u]
    dst = c.components[v]
    src_lbl = src.label or src.element_name
    dst_lbl = dst.label or dst.element_name
    driver_pin = data['driver_pin']
    sink_pin = data['sink_pin']
    net_id = data['net_id']
    print(f'  [{u}] {src_lbl}.{driver_pin} -> [{v}] {dst_lbl}.{sink_pin}  (net {net_id})')
"
```

Visulization: 
```python
uv run --with matplotlib python -c "
from dlc.parser.dig_parser import parse_dig_file
from dlc.parser.netlist import build_netlist
from dlc.parser.graph import build_signal_graph
import networkx as nx, matplotlib.pyplot as plt

c = parse_dig_file('data/sample_circuits/tier3_realistic/tier3_calculator.dig') # your .dig
nl = build_netlist(c)
g = build_signal_graph(c, nl)

try:
    topo = list(nx.topological_sort(g))
except nx.NetworkXUnfeasible:
    topo = list(g.nodes())
in_idxs = [i for i, comp in enumerate(c.components) if comp.element_name == 'In']
out_idxs = [i for i, comp in enumerate(c.components) if comp.element_name == 'Out']
layer = {i: 0 for i in in_idxs}
for node in topo:
    if node in layer: continue
    preds = list(g.predecessors(node))
    layer[node] = max((layer.get(p, 0) for p in preds), default=0) + 1
max_l = max(layer.values()) if layer else 0
for i in out_idxs: layer[i] = max_l + 1

# Hide isolated nodes (Testcase, unused tunnels) 
keep = [n for n in g.nodes() if g.degree(n) > 0]
gs = g.subgraph(keep).copy()
for n in gs.nodes(): gs.nodes[n]['subset'] = layer.get(n, 0)

def col(comp):
    e = comp.element_name
    if e == 'In': return '#90caf9'
    if e == 'Out': return '#ffcc80'
    if e in ('And', 'Or', 'XOr', 'Not', 'NAnd', 'NOr', 'XNOr'): return '#a5d6a7'
    if e == 'Multiplexer': return '#ce93d8'
    if e == 'Splitter': return '#fff59d'
    if e.endswith('.dig'): return '#ef9a9a'
    if e == 'Comparator': return '#80cbc4'
    if e == 'Add': return '#ffab91'
    if e in ('Tunnel', 'Const', 'Ground', 'VDD', 'Clock'): return '#e0e0e0'
    return '#bdbdbd'

pos = nx.multipartite_layout(gs, subset_key='subset')
colors = [col(c.components[n]) for n in gs.nodes()]
labels = {n: (c.components[n].label or c.components[n].element_name) + f'\n[{n}]' for n in gs.nodes()}

plt.figure(figsize=(20, 12))
nx.draw(gs, pos, labels=labels, node_color=colors, node_size=2200,
        font_size=9, font_weight='bold', arrows=True, arrowsize=18,
        edge_color='#555555', width=1.3,
        connectionstyle='arc3,rad=0.08')
plt.title('tier3_calculator.dig — signal-flow graph', fontsize=15)    # Feel free to modify here
plt.axis('off')             
plt.tight_layout()
plt.savefig('graph.png', dpi=200, bbox_inches='tight', facecolor='white')  # Feel free to modify here
print('Saved to graph.png')
"
```

#### Test categories

1. **Graph builds without crashing** — `test_graph_builds_for_all_samples`, asserts node count = component count.
2. **Edge correctness** — `test_graph_single_and_edges` (3 edges in a single-AND circuit), `test_graph_half_adder_topology` (6 edges).
3. **Edge attributes** — `test_graph_edge_attributes_carry_pin_and_net` confirms every edge carries the pin pair and net id.
4. **Node attributes** — `test_graph_node_attributes` confirms each node points back to its Component.
5. **Tunnel-only handoff** — `test_graph_tunnel_handoff` confirms signals cross via Tunnel NetName matching, not just direct wires.
6. **Reachability invariant** — `test_full_adder_full_reachability`, `test_tier1_minimal_full_reachability`, `test_tier2_subcircuits_full_reachability` sweep all samples and assert every input reaches every output.

---

## Concrete tier-3 calculator example (what Layer 3 actually gets)

Run on `data/sample_circuits/tier3_realistic/tier3_calculator.dig`:

```
Component inventory: 25 total
  4 In:  A (4-bit), B (4-bit), Ci (1-bit), Op (2-bit)
  4 Out: Result (4-bit), Carry (1-bit), Zero (1-bit), Bit0 (1-bit)
  2 Add (Bits=4)          [ADD adder + SUB adder]
  4 Splitter              [op-bit-split, B-invert split, recombine, result bit0]
  1 Multiplexer Bits=4 Selector Bits=2    [Result selector]
  1 Multiplexer (default 2-to-1)          [Carry selector]
  1 Comparator Bits=4     [Zero detector]
  1 Const, 1 Ground, 1 Not
  4 Tunnel                [A x2, B x2 — bus distribution]
  1 Subcircuit: bool_unit.dig (3 In + 1 Out)

NetList: 21 nets, 21 driven, 0 undriven-with-pins, 0 multi-driver

Reachability: 16 / 16 input-output pairs
  A   reaches {Result, Carry, Zero, Bit0}
  B   reaches {Result, Carry, Zero, Bit0}
  Ci  reaches {Result, Carry, Zero, Bit0}
  Op  reaches {Result, Carry, Zero, Bit0}

Subcircuit bool_unit instance pins resolved:
  A (in), B (in), LogSel (in), Result (out)
```

For the **bug1 sibling** (`30_buggy_benchmark/bug1_meaningless_mux_in3/`):

```
Same structural picture: 22 nets, 22 driven, 0 undriven, 0 multi-driver, 16/16 I→O.
```

Both look identical to Layer 1. The semantic bug — `Mux[14].in3` wired to a 4-bit Ground instead of the bool_unit's `Result` output — is invisible to deterministic structural checks. It surfaces only when:
- a test vector exercises Op=11 (OR mode) and observes Result=0 instead of A|B, OR
- Layer 3 reads the netlist + intent and notices "your OR-mode mux input is a constant zero."

**This is the canonical Layer-3-only case** and the first of the 30 buggy benchmark.

---

## Function 3 — Structural fact extractor (TBD)

Goal: turn the (Circuit, NetList, signal_graph) trio into a single JSON-serializable bundle of facts an L3 prompt can consume verbatim. Will need:
- Splitter bit-range parsing (`"25-31, 24-20, …"` → typed tuples)
- Per-net bit-width inference (propagate driver widths through wires)
- Stable component IDs across edits
- Pretty-printable circuit summary

Tests will live in `tests/test_facts.py` (placeholder).

---

## Function 4 — Test result parser (TBD)

Goal: parse Digital CLI output (`Test: passed`, `Test: failed (N%)`) into structured pass/fail records keyed by test-case name. Will need:
- Exit-code mapping
- Per-test-vector diff capture (expected vs actual when failure)

Tests will live in `tests/test_cli_results.py` (placeholder).

---

## When you add a new test

