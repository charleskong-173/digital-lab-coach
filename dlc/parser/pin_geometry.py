"""
Pin geometry for covered Digital element types (details specified at docs/digital_notes.md).

Digital component positions in the .dig file are anchor points. Each
component's actual pin positions are OFFSETS from that anchor. We use a registry 
mapping element_name to its pin offsets.

Digital uses x increasing rightward, y increasing downward. Offsets here are added to a
component's <pos x=.. y=..> to get the absolute pin location.

For elements whose pin geometry depends on attributes, we provide a function instead
of a static list.

"""

from dataclasses import dataclass

from dlc.parser.models import Component, Position


@dataclass(frozen=True)
class PinSpec:

    name: str
    offset_x: int
    offset_y: int
    direction: str  

# Single-input gate (Not). (Not Verified for all cases yet)
_NOT_PINS = [
    PinSpec("A", offset_x=0,  offset_y=0, direction="in"),
    PinSpec("Y", offset_x=40, offset_y=0, direction="out"),
]

_INPUT_PINS = [PinSpec("out", 0, 0, "out")]
_OUTPUT_PINS = [PinSpec("in", 0, 0, "in")]
_TUNNEL_PINS = [PinSpec("net", 0, 0, "bidir")]
_CONST_PINS = [PinSpec("out", 0, 0, "out")]
_CLOCK_PINS = [PinSpec("clk", 0, 0, "out")]

STATIC_PIN_TABLE: dict[str, list[PinSpec]] = {
    "Not":    _NOT_PINS,
    "In":     _INPUT_PINS,
    "Out":    _OUTPUT_PINS,
    "Tunnel": _TUNNEL_PINS,
    "Const":  _CONST_PINS,
    "Clock":  _CLOCK_PINS,
}

def _nary_gate_pins(comp: Component) -> list[PinSpec]:
    """
    Boolean gate (And/Or/XOr/NAnd/NOr/XNOr) with N inputs.

    Digital attribute 'Inputs' (<int>) controls input count; absent = 2.

    Gate Geometry (anchor at top input):
      - input i at offset (0, i*20), starting AT the anchor
      - output at (80, ((N-1)*20)//2)  (Not Verified for all cases yet)
    """
    n = int(comp.attributes.get("Inputs", 2))
    pins: list[PinSpec] = []
    for i in range(n):
        pins.append(PinSpec(f"in{i}", offset_x=0, offset_y=i * 20, direction="in"))
    center_y = ((n - 1) * 20) // 2
    pins.append(PinSpec("Y", offset_x=80, offset_y=center_y, direction="out"))
    return pins


def _multiplexer_pins(comp: Component) -> list[PinSpec]:
    """
    Multiplexer. 'Selector Bits' = N → 2^N data inputs (absent = 1 → 2-to-1) (Not Verified for all cases yet)
    """
    sel_bits = int(comp.attributes.get("Selector Bits", 1))
    n_inputs = 2 ** sel_bits

    pins: list[PinSpec] = []
    for i in range(n_inputs):
        pins.append(PinSpec(f"in{i}", offset_x=0, offset_y=i * 20, direction="in"))
    pins.append(PinSpec("sel", offset_x=20, offset_y=n_inputs * 20 + 20, direction="in"))
    pins.append(PinSpec("out", offset_x=40, offset_y=(n_inputs * 20) // 2, direction="out"))
    return pins


def _splitter_pins(comp: Component) -> list[PinSpec]:
    """
    Splitter. 
    bit-group sizes. Each group is one pin. Inputs left, outputs right.
    (Not Verified for all cases yet)
    """
    in_split = str(comp.attributes.get("Input Splitting", "1"))
    out_split = str(comp.attributes.get("Output Splitting", "1"))
    in_groups = [s.strip() for s in in_split.split(",") if s.strip()]
    out_groups = [s.strip() for s in out_split.split(",") if s.strip()]

    pins: list[PinSpec] = []
    for i, _ in enumerate(in_groups):
        pins.append(PinSpec(f"in{i}", offset_x=0, offset_y=i * 20, direction="in"))
    for i, _ in enumerate(out_groups):
        pins.append(PinSpec(f"out{i}", offset_x=20, offset_y=i * 20, direction="out"))
    return pins


def _register_pins(comp: Component) -> list[PinSpec]:
    """
    Register: D input, clock input, optional enable, Q output.
    (Not Verified for all cases yet)
    """
    return [
        PinSpec("D",  offset_x=0,  offset_y=0,  direction="in"),
        PinSpec("C",  offset_x=0,  offset_y=20, direction="in"),
        PinSpec("en", offset_x=20, offset_y=60, direction="in"),
        PinSpec("Q",  offset_x=60, offset_y=20, direction="out"),
    ]


def _comparator_pins(comp: Component) -> list[PinSpec]:
    """
    Comparator: A and B inputs left, greater/equal/less outputs right. 
    (Not Verified for all cases yet)
    """
    return [
        PinSpec("A",  offset_x=0,  offset_y=0,  direction="in"),
        PinSpec("B",  offset_x=0,  offset_y=20, direction="in"),
        PinSpec("gr", offset_x=80, offset_y=0,  direction="out"),
        PinSpec("eq", offset_x=80, offset_y=20, direction="out"),
        PinSpec("le", offset_x=80, offset_y=40, direction="out"),
    ]

DYNAMIC_PIN_TABLE: dict[str, callable] = {
    "And":  _nary_gate_pins,
    "Or":   _nary_gate_pins,
    "XOr":  _nary_gate_pins,
    "NAnd": _nary_gate_pins,
    "NOr":  _nary_gate_pins,
    "XNOr": _nary_gate_pins,
    "Multiplexer": _multiplexer_pins,
    "Splitter":    _splitter_pins,
    "Register":    _register_pins,
    "Comparator":  _comparator_pins,
}



# Public API

def get_pin_specs(component: Component) -> list[PinSpec]:
    name = component.element_name

    if name in STATIC_PIN_TABLE:
        return STATIC_PIN_TABLE[name]
    if name in DYNAMIC_PIN_TABLE:
        return DYNAMIC_PIN_TABLE[name](component)

    return []


def absolute_pin_positions(component: Component) -> list[tuple[Position, PinSpec]]:
    """
    Return each pin's absolute canvas position plus its spec.
    Used for matching wire endpoints to pins.
    """
    pins = get_pin_specs(component)
    result = []
    for pin in pins:
        absolute = Position(
            x=component.position.x + pin.offset_x,
            y=component.position.y + pin.offset_y,
        )
        result.append((absolute, pin))
    return result