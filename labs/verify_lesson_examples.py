"""Verify that code examples quoted in the lessons actually run."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from graphlab.store import GraphStore

# Lesson 3's temporal example, exactly as printed on the site.
g = GraphStore()
g.upsert_entity("Alice", "person")
g.upsert_entity("X", "organization")
g.upsert_entity("Y", "organization")
g.add_edge("Alice", "works_at", "X", valid_from="2024", valid_until="2026")
g.add_edge("Alice", "works_at", "Y", valid_from="2026")

a = {e.target for e in g.edges_of("Alice", as_of="2025")}
b = {e.target for e in g.edges_of("Alice", as_of="2027")}
print(f"as_of 2025 -> {a}   (lesson claims {{'X'}})")
print(f"as_of 2027 -> {b}   (lesson claims {{'Y'}})")
assert a == {"X"} and b == {"Y"}

# Lesson 3's invalidate claim: 1 then 0.
g2 = GraphStore()
g2.upsert_entity("A", "person")
g2.upsert_entity("B", "organization")
g2.add_edge("A", "works_at", "B", valid_from="2020")
first = g2.invalidate("A", "works_at", "B", "2024")
second = g2.invalidate("A", "works_at", "B", "2025")
print(f"invalidate -> {first} then {second}   (lesson claims 1 then 0)")
assert (first, second) == (1, 0)

print("\nAll lesson code examples verified against the real implementation.")
