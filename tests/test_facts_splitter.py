"""Tests for dlc.facts.splitter"""

import pytest
from dlc.facts.splitter import BitGroup, parse_splitting, total_bits, bus_width_of


def test_single_bare_integer():
    assert parse_splitting("4") == [BitGroup(0, 3, 4)]


def test_packed_one_bit_lanes():
    assert parse_splitting("1,1,1,1") == [
        BitGroup(0, 0, 1),
        BitGroup(1, 1, 1),
        BitGroup(2, 2, 1),
        BitGroup(3, 3, 1),
    ]


def test_full_range_explicit():
    assert parse_splitting("0-31") == [BitGroup(0, 31, 32)]


def test_instruction_field_split():
    spec = "25-31, 24-20, 19-15, 14-12, 11-7, 6-0"
    groups = parse_splitting(spec)
    assert groups == [
        BitGroup(25, 31, 7),
        BitGroup(20, 24, 5),
        BitGroup(15, 19, 5),
        BitGroup(12, 14, 3),
        BitGroup(7, 11, 5),
        BitGroup(0, 6, 7),
    ]
    assert total_bits(groups) == 32


def test_range_with_high_first():
    assert parse_splitting("31-0") == [BitGroup(0, 31, 32)]


def test_mixed_bare_and_range_cursor_advances():
    assert parse_splitting("2, 10") == [
        BitGroup(0, 1, 2),
        BitGroup(2, 11, 10),
    ]


def test_whitespace_tolerance():
    assert parse_splitting("  1 , 1 ,  1 ") == parse_splitting("1,1,1")


def test_empty_string_returns_empty():
    assert parse_splitting("") == []
    assert parse_splitting("   ") == []


def test_bus_width_helper():
    assert bus_width_of("4") == 4
    assert bus_width_of("1,1,1,1") == 4
    assert bus_width_of("0-31") == 32
    assert bus_width_of("25-31, 24-20, 19-15, 14-12, 11-7, 6-0") == 32


def test_invalid_token_raises():
    with pytest.raises(ValueError):
        parse_splitting("4,abc")
    with pytest.raises(ValueError):
        parse_splitting("0-foo")


def test_zero_width_rejected():
    with pytest.raises(ValueError):
        parse_splitting("0")


def test_bitgroup_validates_invariants():
    with pytest.raises(ValueError):
        BitGroup(5, 3, 3)  
    with pytest.raises(ValueError):
        BitGroup(0, 3, 5) 