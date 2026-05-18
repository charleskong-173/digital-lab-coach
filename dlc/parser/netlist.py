"""
Net construction: turn a parsed Circuit's components + wires into nets.

A NET is a maximal set of points that are connected via:
  - wires whose endpoints share coordinates (transitively), and
  - tunnels that share a NetName.

A pin "belongs to" a net if a wire endpoint of that net coincides with the pin's coordinate.

Design choice:
  1. Build nets purely from wire endpoints + tunnel names.
  2. For each component, determine its pin coordinates by pin_geometry.
  3. Attach pins to nets by coordinate coincidence.

This makes connectivity robust to imperfect geometry tables.
"""

from dataclasses import dataclass, field

from dlc.parser.models import Circuit, Component, Wire
from dlc.parser.pin_geometry import absolute_pin_positions



class _UnionFind:
    """
    find(x): returns the canonical representative of x's group.
    union(a,b): merges the groups containing a and b.
    """

    def __init__(self):
        self._parent: dict = {}

    def _ensure(self, x):
        if x not in self._parent:
            self._parent[x] = x

    def find(self, x):
        self._ensure(x)
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb

    def groups(self) -> dict:
        out: dict = {}
        for key in self._parent:
            root = self.find(key)
            out.setdefault(root, []).append(key)
        return out


@dataclass(frozen=True)
class Pin:
    component_index: int
    element_name: str
    pin_name: str
    x: int
    y: int
    direction: str


@dataclass
class Net:
    """
    One electrical net.

    Fields:
      net_id:     stable integer id within a NetList.
      coords:     set of (x, y) coordinates that belong to this net.
      pins:       Pin objects attached to this net.
      tunnel_names: set of tunnel NetNames merged into this net (if any).
    """
    net_id: int
    coords: set = field(default_factory=set)
    pins: list = field(default_factory=list)
    tunnel_names: set = field(default_factory=set)

    def drivers(self) -> list:
        return [p for p in self.pins if p.direction == "out"]

    def sinks(self) -> list:
        return [p for p in self.pins if p.direction == "in"]


@dataclass
class NetList:
    """
    All nets of a circuit, plus lookups.
    """
    nets: list = field(default_factory=list)
    by_coord: dict = field(default_factory=dict)

    def net_at(self, x: int, y: int):
        nid = self.by_coord.get((x, y))
        if nid is None:
            return None
        return self.nets[nid]

    def summary(self) -> str:
        n_with_driver = sum(1 for net in self.nets if net.drivers())
        n_no_driver = sum(
            1 for net in self.nets if net.pins and not net.drivers()
        )
        n_multi_driver = sum(1 for net in self.nets if len(net.drivers()) > 1)
        return (
            f"NetList: {len(self.nets)} nets, "
            f"{n_with_driver} driven, "
            f"{n_no_driver} undriven-with-pins, "
            f"{n_multi_driver} multi-driver"
        )


# Net builder

def _component_pins(circuit: Circuit) -> list[Pin]:
    """
    Produce Pin objects for every component.

    For components we have geometry for: use absolute_pin_positions().
    For subcircuit references and unknown components: we don't know exact
    pin layout, so we create no explicit pins here. They get implicit pins
    later from wire endpoints that touch them (handled in build_netlist).
    """
    pins: list[Pin] = []
    for idx, comp in enumerate(circuit.components):
        positioned = absolute_pin_positions(comp)
        for abs_pos, spec in positioned:
            pins.append(
                Pin(
                    component_index=idx,
                    element_name=comp.element_name,
                    pin_name=spec.name,
                    x=abs_pos.x,
                    y=abs_pos.y,
                    direction=spec.direction,
                )
            )
    return pins


def _nearest_component_index(
    circuit: Circuit, x: int, y: int, max_dist: int = 40
) -> int | None:
    """
    For an endpoint that doesn't sit on a known pin (subcircuit / unknown
    component case), find the closest component anchor within max_dist
    (Manhattan distance). Used to attach implicit pins.
    """
    best_idx = None
    best_dist = max_dist + 1
    for idx, comp in enumerate(circuit.components):
        d = abs(comp.position.x - x) + abs(comp.position.y - y)
        if d < best_dist:
            best_dist = d
            best_idx = idx
    return best_idx


def build_netlist(circuit: Circuit) -> NetList:
    """
    Build the NetList for a circuit.

    Steps:
      1. Union every wire's two endpoints.
      2. Union tunnel coordinates that share a NetName.
      3. Materialize nets from union-find groups.
      4. Attach known component pins to nets by coordinate match.
      5. For wire endpoints not matched to a known pin, attach an implicit
         pin to the nearest component.
    """
    uf = _UnionFind()

    # Step 1
    for wire in circuit.wires:
        a = wire.p1.as_tuple()
        b = wire.p2.as_tuple()
        uf.union(a, b)

    # Step 2
    tunnels_by_name: dict[str, list[tuple[int, int]]] = {}
    for comp in circuit.components:
        if comp.element_name != "Tunnel":
            continue
        net_name = comp.attributes.get("NetName")
        coord = comp.position.as_tuple()
        uf._ensure(coord)
        if net_name is not None:
            tunnels_by_name.setdefault(net_name, []).append(coord)

    for net_name, coords in tunnels_by_name.items():
        first = coords[0]
        for other in coords[1:]:
            uf.union(first, other)

    #Step 3
    groups = uf.groups()
    netlist = NetList()
    rep_to_netid: dict = {}

    for rep, members in groups.items():
        net_id = len(netlist.nets)
        rep_to_netid[rep] = net_id
        net = Net(net_id=net_id, coords=set(members))
        # Record which tunnel names landed in this net.
        for comp in circuit.components:
            if comp.element_name == "Tunnel":
                if comp.position.as_tuple() in net.coords:
                    nm = comp.attributes.get("NetName")
                    if nm is not None:
                        net.tunnel_names.add(nm)
        netlist.nets.append(net)
        for m in members:
            netlist.by_coord[m] = net_id

    #Step 4
    all_pins = _component_pins(circuit)
    matched_pin_coords: set = set()

    for pin in all_pins:
        coord = (pin.x, pin.y)
        nid = netlist.by_coord.get(coord)
        if nid is not None:
            netlist.nets[nid].pins.append(pin)
            matched_pin_coords.add(coord)
        else:
            net_id = len(netlist.nets)
            net = Net(net_id=net_id, coords={coord})
            net.pins.append(pin)
            netlist.nets.append(net)
            netlist.by_coord[coord] = net_id

    #Step 5
    for wire in circuit.wires:
        for endpoint in (wire.p1.as_tuple(), wire.p2.as_tuple()):
            if endpoint in matched_pin_coords:
                continue
            nid = netlist.by_coord.get(endpoint)
            if nid is None:
                continue
            net = netlist.nets[nid]
            already = any((p.x, p.y) == endpoint for p in net.pins)
            if already:
                continue
            idx = _nearest_component_index(
                circuit, endpoint[0], endpoint[1]
            )
            if idx is None:
                continue
            comp = circuit.components[idx]
            if absolute_pin_positions(comp):
                continue
            net.pins.append(
                Pin(
                    component_index=idx,
                    element_name=comp.element_name,
                    pin_name=f"wire@{endpoint[0]},{endpoint[1]}",
                    x=endpoint[0],
                    y=endpoint[1],
                    direction="unknown",
                )
            )

    return netlist