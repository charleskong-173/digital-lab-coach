"""
Data models for parsed .dig circuits.
The parser reads raw XML and produces a Circuit object built from these pieces. 
"""

from dataclasses import dataclass, field


@dataclass
class Position:
    x: int
    y: int

    def as_tuple(self) -> tuple[int, int]:
        return (self.x, self.y)


@dataclass
class Component:
    """
    One visual element in the circuit: a gate, an I/O pin, a multiplexer, etc.

    Fields:
      element_name: Digital's type string, e.g. "And", "In", "Multiplexer".
      position:     where it (its anchor point) sits on the canvas.
      attributes:   the raw key/value pairs from <elementAttributes>,
                    e.g. {"Label": "A", "Bits": 4}. 
      label:        convenience copy of attributes["Label"] if present, else None.
    """
    element_name: str
    position: Position
    attributes: dict = field(default_factory=dict)
    label: str | None = None

    def is_input(self) -> bool:
        return self.element_name == "In"

    def is_output(self) -> bool:
        return self.element_name == "Out"

    def is_tunnel(self) -> bool:
        return self.element_name == "Tunnel"

    def bit_width(self) -> int:
        """
        Return the component's bit width.
        If the 'Bits' attribute is absent, Digital's default is 1.
        """
        return int(self.attributes.get("Bits", 1))

@dataclass
class SubcircuitReference:
    """
    A component that references another .dig file as its body.

    Detected by: the component's element_name ends in '.dig'.

    Fields:
      reference: the raw filename string from the .dig file (e.g. "alu.dig").
      resolved_path: the absolute filesystem path the parser actually loaded
                     from. None if resolution failed.
      child_circuit: the parsed Circuit object for the referenced file.
                     None if resolution failed.
      resolution_error: string explaining why child_circuit is None.
                        None if everything resolved fine.

    Note: SubcircuitReference is built ALONGSIDE the regular Component for
    each subcircuit instance, and a parallel SubcircuitReference is recorded in 
    Circuit.subcircuits. They share the same position.
    """
    reference: str
    parent_component: "Component"
    resolved_path: str | None = None
    child_circuit: "Circuit | None" = None
    resolution_error: str | None = None

@dataclass
class Wire:

    p1: Position
    p2: Position

    def is_axis_aligned(self) -> bool:
        return self.p1.x == self.p2.x or self.p1.y == self.p2.y

    def endpoints(self) -> list[tuple[int, int]]:
        return [self.p1.as_tuple(), self.p2.as_tuple()]


@dataclass
class Circuit:
    """
    A whole parsed .dig file.

    Fields:
      components: every visual element in the file.
      wires: every wire segment.
      source_path: where this circuit was loaded from.
      format_version: the <version> value from the .dig file.
      subcircuits: subcircuit references found in this circuit, with their resolved child circuits attached.
    """
    components: list[Component] = field(default_factory=list)
    wires: list[Wire] = field(default_factory=list)
    source_path: str | None = None
    format_version: int | None = None
    subcircuits: list["SubcircuitReference"] = field(default_factory=list) 

    def inputs(self) -> list[Component]:
        return [c for c in self.components if c.is_input()]

    def outputs(self) -> list[Component]:
        return [c for c in self.components if c.is_output()]

    def tunnels(self) -> list[Component]:
        return [c for c in self.components if c.is_tunnel()]

    def subcircuit_components(self) -> list[Component]:
        return [c for c in self.components if c.element_name.endswith(".dig")]

    def summary(self) -> str:
        return (
            f"Circuit({self.source_path}): "
            f"{len(self.components)} components, "
            f"{len(self.wires)} wires, "
            f"{len(self.inputs())} inputs, "
            f"{len(self.outputs())} outputs, "
            f"{len(self.tunnels())} tunnels, "
            f"{len(self.subcircuits)} subcircuits"
        )