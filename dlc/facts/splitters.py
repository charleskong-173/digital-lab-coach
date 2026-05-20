"""
Splitter bit-range parser.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BitGroup:
    bit_lo: int
    bit_hi: int
    width: int

    def __post_init__(self) -> None:
        if self.bit_lo > self.bit_hi:
            raise ValueError(
                f"bit_lo ({self.bit_lo}) must be <= bit_hi ({self.bit_hi})"
            )
        if self.width != self.bit_hi - self.bit_lo + 1:
            raise ValueError(
                f"width ({self.width}) does not match range "
                f"[{self.bit_lo}, {self.bit_hi}]"
            )


def parse_splitting(spec: str) -> list[BitGroup]:
    if not spec or not spec.strip():
        return []

    groups: list[BitGroup] = []
    cursor = 0  

    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        if "-" in token:
            a_str, b_str = token.split("-", 1)
            try:
                a = int(a_str.strip())
                b = int(b_str.strip())
            except ValueError as e:
                raise ValueError(
                    f"Invalid range token {token!r} in splitting {spec!r}"
                ) from e
            lo, hi = (a, b) if a <= b else (b, a)
            groups.append(BitGroup(lo, hi, hi - lo + 1))
            cursor = max(cursor, hi + 1)
        else:
            try:
                width = int(token)
            except ValueError as e:
                raise ValueError(
                    f"Invalid integer token {token!r} in splitting {spec!r}"
                ) from e
            if width <= 0:
                raise ValueError(
                    f"Splitting width must be positive, got {width} in {spec!r}"
                )
            lo = cursor
            hi = cursor + width - 1
            groups.append(BitGroup(lo, hi, width))
            cursor = hi + 1
    return groups


def total_bits(groups: list[BitGroup]) -> int:
    return sum(g.width for g in groups)


def bus_width_of(spec: str) -> int:
    return total_bits(parse_splitting(spec))