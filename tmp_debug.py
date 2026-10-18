"""Debug script to identify the exact FalkorDB query issue."""
from backend.graph_db import get_graph

g = get_graph()
eid = "alert_001"

# Test 1: Simple direct 1-hop match
try:
    r1 = g.query(
        "MATCH (n {entity_id: $eid})-[r]-(m) RETURN type(r), labels(m), properties(m) LIMIT 5",
        {"eid": eid}
    )
    print(f"Test 1 (depth=1): {len(r1.result_set)} rows")
    for row in r1.result_set:
        print(f"  rel={row[0]}, labels={row[1]}")
except Exception as e:
    print(f"Test 1 ERROR: {e}")

# Test 2: Variable length with named r and last(r) — the problematic one
try:
    r2 = g.query(
        "MATCH (start {entity_id: $eid})-[r*1..2]-(end) WHERE start <> end RETURN labels(end), properties(end), properties(last(r)), type(last(r)) LIMIT 5",
        {"eid": eid}
    )
    print(f"Test 2 (varlen+last(r)): {len(r2.result_set)} rows")
except Exception as e:
    print(f"Test 2 ERROR (varlen+last(r)): {e}")

# Test 3: Variable length without rel props
try:
    r3 = g.query(
        "MATCH (start {entity_id: $eid})-[*1..2]-(end) WHERE start <> end RETURN labels(end), properties(end) LIMIT 5",
        {"eid": eid}
    )
    print(f"Test 3 (varlen no rel): {len(r3.result_set)} rows")
    for row in r3.result_set:
        p = row[1]
        print(f"  labels={row[0]}, entity_id={p.get('entity_id','?')}")
except Exception as e:
    print(f"Test 3 ERROR: {e}")

# Test 4: APOC-style or WITH intermediate
try:
    r4 = g.query(
        "MATCH (start {entity_id: $eid})-[r1]-(hop1)-[r2*0..1]-(end) WHERE start <> end RETURN labels(end), properties(end), type(r1) LIMIT 10",
        {"eid": eid}
    )
    print(f"Test 4 (explicit hops): {len(r4.result_set)} rows")
except Exception as e:
    print(f"Test 4 ERROR: {e}")

# Test 5: depth 1 only, get rel type
try:
    r5 = g.query(
        "MATCH (start {entity_id: $eid})-[r]-(end) WHERE start <> end RETURN labels(end) AS lbl, properties(end) AS props, type(r) AS rel LIMIT 10",
        {"eid": eid}
    )
    print(f"Test 5 (depth 1 explicit): {len(r5.result_set)} rows")
    for row in r5.result_set:
        p = row[1]
        print(f"  rel={row[2]}, lbl={row[0]}, eid={p.get('entity_id','?')}")
except Exception as e:
    print(f"Test 5 ERROR: {e}")
