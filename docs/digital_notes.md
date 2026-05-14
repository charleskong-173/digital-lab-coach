# Digital Notes

Last updated: [2026/5/14]

---

## .dig File Format

### Top-level structure

- Root element: `<circuit>`
- Two main children: `<visualElements>` (components), `<wires>` (connections)
- Wires are geometric (p1, p2 coordinates), not pin-typed — must match endpoints to component pin positions
- Subcircuits referenced as `<elementName>filename.dig</elementName>`
- `<version>2</version>` is the current `.dig` format version
- `<measurementOrdering/>` appears (empty) at the end of every file

### Element types I've encountered

| Element name | Purpose | Notes |
|---|---|---|
| And, Or, XOr, Not | Basic gates | `Not` is single-input. Optional `Bits` attribute (default 1). `wideShape` boolean is cosmetic only |
| In, Out | Circuit I/O pins | Has `Label`. `Bits` attribute optional (absent = 1 bit) |
| Multiplexer | Mux | Has `Selector Bits` attribute |
| Splitter | Bus split/merge | `Input Splitting` / `Output Splitting` are comma-separated strings (e.g. "4" → "1,1,1,1") |
| Tunnel | Named net | Attribute is `NetName`. Tunnels sharing a NetName are electrically connected. Can have `rotation` |
| ROM | Read-only memory | Has `Bits` (data width), `AddrBits` (address width) |
| Register | Sequential register | Has `Bits`, optional `isProgramCounter` |
| Const | Constant value | Has `Value`, `Bits` |
| Comparator | Bit comparison | Has `Signed`, `Bits` attributes |
| Add | Adder | Has `Bits` |
| BitExtender | Sign extension | |
| Clock | Clock signal | No attributes in basic use |
| Testcase | Embedded test cases | Contains `<testData>` → `<dataString>` for test data |

### Wires

- A `<wire>` has exactly two endpoints: `<p1>` and `<p2>`, each with x/y coordinates
- Wires carry NO pin or signal-type information — pure geometry
- Connectivity is INFERRED: wires sharing an endpoint coordinate form a net
- Wires can be diagonal (Digital allows it) — not inherently an error
- Real bug patterns: miswire (connected to wrong pin, usually surfaces as failed tests), dangling wire (endpoint connects to nothing)

## Digital UI Features Relevant to Students

### Debugging tools that exist natively
- Single-step simulation
- Test case runner with pass/fail output

### What students struggle with (from ULA experience)


### Features we'd want DLC to add or enhance

## Parser scope policy

DLC's parser aims to **semantically understand** elements used in
COMP 311 labs (all semesters). Other elements (transistor primitives,
FPGA-specific blocks, FSM editor outputs, etc.) are parsed structurally
but treated as opaque `UnknownComponent` with named pins. This lets
the analyzer skip unrecognized components and the LLM describe them
generically, while keeping the parser future-proof for new labs.

Known-and-semantically-supported (initial target):
Wire, And, Or, XOr, Not, NAnd, NOr, In, Out, Multiplexer, Splitter, Tunnel,
ROM, RAM, Register, Const, Comparator, Add, BitExtender, Clock,
Testcase, PriorityEncoder

Out of initial scope (parsed but opaque):
all transistor-level elements, FSM elements, FPGA-board-specific blocks,
VHDL/Verilog wrappers, GAL/JEDEC-specific elements

## CLI Mode (what the autograder uses)

- Command: `java -cp Digital.jar CLI test -circ FILE.dig`
- Output format: `Test: passed` or `Test: failed (N%)` per test case
- Exit codes: 

## Subcircuit Resolution

- A circuit referencing `alu.dig` means Digital looks for `alu.dig` in the same directory or library path
- For our parser: must recursively load referenced subcircuits to fully analyze a top-level circuit

## Open Questions under investigation

- How does Digital handle missing subcircuit files? (Investigating)
- Does Digital's CLI mode produce structured output (JSON?) or only human-readable text? (Investigating)
- Where exactly does Java plugin API expose hooks for adding analysis panels? (Path 3 question, defer investigation)