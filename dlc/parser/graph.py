import networkx as nx

from dlc.parser.models import Circuit
from dlc.parser.netlist import NetList


def build_signal_graph(circuit: Circuit, netlist: NetList) -> nx.MultiDiGraph:
    """
    Build the directed signal-flow graph for `circuit` given its `netlist`.
    """
    g = nx.MultiDiGraph()
    for idx, comp in enumerate(circuit.components):
        g.add_node(
            idx,
            component=comp,
            element_name=comp.element_name,
            label=comp.label,
        )

    for net in netlist.nets:
        drivers = net.drivers()
        sinks = net.sinks()
        if not drivers or not sinks:
            continue
        for d in drivers:
            for s in sinks:
                g.add_edge(
                    d.component_index,
                    s.component_index,
                    net_id=net.net_id,
                    driver_pin=d.pin_name,
                    sink_pin=s.pin_name,
                )
    return g


def input_component_indices(circuit: Circuit) -> list[int]:
    """Indices of top-level In elements (circuit inputs)."""
    return [i for i, c in enumerate(circuit.components) if c.is_input()]


def output_component_indices(circuit: Circuit) -> list[int]:
    """Indices of top-level Out elements (circuit outputs)."""
    return [i for i, c in enumerate(circuit.components) if c.is_output()]


def reachable_outputs_from_inputs(
    circuit: Circuit, graph: nx.MultiDiGraph
) -> dict[int, set[int]]:
    """
    For each input component index, return the set of output component
    indices reachable along signal direction.
    """
    out_idxs = set(output_component_indices(circuit))
    result: dict[int, set[int]] = {}
    for in_idx in input_component_indices(circuit):
        descendants = nx.descendants(graph, in_idx) if in_idx in graph else set()
        result[in_idx] = descendants & out_idxs
    return result