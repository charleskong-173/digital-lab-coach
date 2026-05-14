"""
Parser: reads a .dig XML file and produces a Circuit object.
This stage handles ONLY components, attributes, and wire segments. 
This stage does NOT infer connectivity or nets.
"""

from lxml import etree
from dlc.parser.models import Circuit, Component, Wire, Position


def _parse_attributes(element_attributes) -> dict:
    """
    Convert a <elementAttributes> XML block into a plain Python dict.

    Digital stores attributes as a list of <entry> blocks, each containing
    a <string> key followed by a value element whose TAG tells us the type:
      <int>, <long>, <boolean>, <string>, etc.

    Example XML:
      <elementAttributes>
        <entry>
          <string>Label</string>
          <string>A</string>
        </entry>
        <entry>
          <string>Bits</string>
          <int>4</int>
        </entry>
      </elementAttributes>

    Produces: {"Label": "A", "Bits": 4}

    Anything failed to be recognized now will be added in in the future development or placed as raw text.
    """
    attributes = {}
    if element_attributes is None:
        return attributes

    for entry in element_attributes.findall("entry"):
        children = list(entry)
        # An entry must have at least a key; most have key + value.
        if len(children) < 2:
            continue

        key_element = children[0]
        value_element = children[1]

        # The key is always a <string>.
        key = key_element.text
        if key is None:
            continue

        # The value's type is its tag name.
        value_tag = value_element.tag
        value_text = value_element.text

        if value_tag in ("int", "long"):
            value = int(value_text) if value_text is not None else 0
        elif value_tag == "boolean":
            value = (value_text == "true")
        elif value_tag == "string":
            value = value_text if value_text is not None else ""
        else:
            # Unknown value type (e.g. <rotation>, <testData>, <shape>).
            # Keep the raw text so nothing is lost; checkers can ignore it.
            value = value_text if value_text is not None else value_tag

        attributes[key] = value

    return attributes


def _parse_position(element) -> Position:
    """
    Read a <pos x="..." y="..."/> child from an element.
    Every visualElement and every wire endpoint has one.
    """
    pos = element.find("pos")
    if pos is None:
        # Shouldn't happen in valid files, but fail loud rather than guess.
        raise ValueError("Element missing <pos> tag")
    x = int(pos.get("x"))
    y = int(pos.get("y"))
    return Position(x, y)


def _parse_component(visual_element) -> Component:
    """Turn one <visualElement> block into a Component object."""
    element_name = visual_element.findtext("elementName")
    if element_name is None:
        raise ValueError("visualElement missing <elementName>")

    attributes = _parse_attributes(visual_element.find("elementAttributes"))
    position = _parse_position(visual_element)
    label = attributes.get("Label")

    return Component(
        element_name=element_name,
        position=position,
        attributes=attributes,
        label=label,
    )


def _parse_wire(wire_element) -> Wire:
    """
    Turn one <wire> block into a Wire object.
    A wire has two endpoints: <p1 x.. y..> and <p2 x.. y..>.
    """
    p1 = wire_element.find("p1")
    p2 = wire_element.find("p2")
    if p1 is None or p2 is None:
        raise ValueError("wire missing p1 or p2")

    return Wire(
        p1=Position(int(p1.get("x")), int(p1.get("y"))),
        p2=Position(int(p2.get("x")), int(p2.get("y"))),
    )


def parse_dig_file(path: str) -> Circuit:
    """
    Main entry point: read a .dig file from disk, return a Circuit object.

    Raises:
      FileNotFoundError if the path doesn't exist.
      etree.XMLSyntaxError if the file isn't valid XML.
      ValueError if the XML is valid but missing expected structure.
    """
    tree = etree.parse(path)
    root = tree.getroot()

    if root.tag != "circuit":
        raise ValueError(f"Expected root <circuit>, got <{root.tag}>")

    # Format version (e.g. <version>2</version>).
    version_text = root.findtext("version")
    format_version = int(version_text) if version_text is not None else None

    # Parse all components under <visualElements>.
    components = []
    visual_elements = root.find("visualElements")
    if visual_elements is not None:
        for ve in visual_elements.findall("visualElement"):
            components.append(_parse_component(ve))

    # Parse all wires under <wires>.
    wires = []
    wires_block = root.find("wires")
    if wires_block is not None:
        for w in wires_block.findall("wire"):
            wires.append(_parse_wire(w))

    return Circuit(
        components=components,
        wires=wires,
        source_path=path,
        format_version=format_version,
    )