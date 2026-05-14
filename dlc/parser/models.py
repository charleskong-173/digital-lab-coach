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
      wires:      every wire segment.
      source_path: where this circuit was loaded from.
      format_version: the <version> value from the .dig file.
    """
    components: list[Component] = field(default_factory=list)
    wires: list[Wire] = field(default_factory=list)
    source_path: str | None = None
    format_version: int | None = None

    def inputs(self) -> list[Component]:
        return [c for c in self.components if c.is_input()]

    def outputs(self) -> list[Component]:
        return [c for c in self.components if c.is_output()]

    def tunnels(self) -> list[Component]:
        return [c for c in self.components if c.is_tunnel()]

    def summary(self) -> str:
        return (
            f"Circuit({self.source_path}): "
            f"{len(self.components)} components, "
            f"{len(self.wires)} wires, "
            f"{len(self.inputs())} inputs, "
            f"{len(self.outputs())} outputs, "
            f"{len(self.tunnels())} tunnels"
        )