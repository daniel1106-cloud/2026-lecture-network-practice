#!/usr/bin/env python3
"""Week 6 · Task 1 — Link state: build the forwarding table yourself.

Textbook §5.2 (link state and distance vector) and §5.3 (OSPF).

Every OSPF router ends up holding the same map of the network, and then each one
computes, alone, where to send a packet for every destination. The computation is
Dijkstra; the output is a forwarding table with **one next hop per destination**,
not a path.

That last part is what makes routing work without anybody carrying a route around
in the packet. Build it.

    python3 task1_linkstate.py --verify
"""
import argparse, heapq

# Undirected weighted graph: node -> {neighbour: cost}
TOPOLOGY = {
    "u": {"v": 2, "w": 5, "x": 1},
    "v": {"u": 2, "w": 3, "x": 2},
    "w": {"u": 5, "v": 3, "x": 3, "y": 1, "z": 5},
    "x": {"u": 1, "v": 2, "w": 3, "y": 1},
    "y": {"w": 1, "x": 1, "z": 2},
    "z": {"w": 5, "y": 2},
}


def dijkstra(graph, source):
    """Shortest path cost from `source` to every node.

    Return {node: cost}. Unreachable nodes do not appear, and neither does
    `source` itself (its cost to itself is 0 and carries no information).
    """
    cost = {}
    heap = [(0, source)]
    while heap:
        c, node = heapq.heappop(heap)
        if node in cost:                      # an older, longer entry for a settled node
            continue
        cost[node] = c
        for neighbour, weight in graph[node].items():
            if neighbour not in cost:
                heapq.heappush(heap, (c + weight, neighbour))
    del cost[source]
    return cost


def forwarding_table(graph, source):
    """What the router at `source` actually installs: {destination: first_hop}.

    The first hop is carried along the search instead of reconstructing a path
    afterwards: a neighbour of `source` starts with itself as the first hop, and
    every node reached through a settled node inherits that node's first hop.

    Tie-breaking: when two shortest paths have equal cost, the heap entries
    compare (cost, node, first_hop), so the lexicographically smallest first
    hop is settled first and wins. A real router would keep both (equal-cost
    multipath) and spread flows across them by hashing the packet's addresses
    and ports; one fixed choice pins all traffic to one path.
    """
    table = {}
    settled = set()
    heap = [(0, source, None)]
    while heap:
        c, node, first_hop = heapq.heappop(heap)
        if node in settled:
            continue
        settled.add(node)
        if node != source:
            table[node] = first_hop
        for neighbour, weight in graph[node].items():
            if neighbour not in settled:
                hop = neighbour if node == source else first_hop
                heapq.heappush(heap, (c + weight, neighbour, hop))
    return table



def link_down(graph, a, b):
    """A copy of `graph` with the link a-b removed, in both directions."""
    g = {n: dict(e) for n, e in graph.items()}
    g[a].pop(b, None)
    g[b].pop(a, None)
    return g


# ------------------------------------------------------------------- harness
# Costs from the textbook's worked example, §5.2.1
EXPECTED_COST_U = {"v": 2, "w": 3, "x": 1, "y": 2, "z": 4}
EXPECTED_TABLE_U = {"v": "v", "w": "x", "x": "x", "y": "x", "z": "x"}


def verify():
    fails = 0
    try:
        cost = dijkstra(TOPOLOGY, "u")
    except NotImplementedError:
        print("  dijkstra is still a stub"); return 1
    ok = cost == EXPECTED_COST_U
    print(f"  {'ok  ' if ok else 'FAIL'}  costs from u: {cost}")
    if not ok:
        print(f"        expected {EXPECTED_COST_U}")
    fails += not ok

    try:
        table = forwarding_table(TOPOLOGY, "u")
    except NotImplementedError:
        print("  forwarding_table is still a stub"); return 1
    ok = table == EXPECTED_TABLE_U
    print(f"  {'ok  ' if ok else 'FAIL'}  table at u:  {table}")
    if not ok:
        print(f"        expected {EXPECTED_TABLE_U}")
    fails += not ok

    # every node should be able to reach every other
    for n in TOPOLOGY:
        t = forwarding_table(TOPOLOGY, n)
        missing = set(TOPOLOGY) - {n} - set(t)
        bad = [d for d, h in t.items() if h not in TOPOLOGY[n]]
        ok = not missing and not bad
        print(f"  {'ok  ' if ok else 'FAIL'}  table at {n} covers all, hops are neighbours"
              + (f"  missing={missing} bad={bad}" if not ok else ""))
        fails += not ok

    # cutting a link must change somebody's mind
    cut = link_down(TOPOLOGY, "u", "x")
    after = forwarding_table(cut, "u")
    ok = after != table
    print(f"  {'ok  ' if ok else 'FAIL'}  u reroutes when u-x goes down: {after}")
    fails += not ok

    print(f"\n  {'all ok' if not fails else str(fails) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()
    raise SystemExit(verify() if a.verify else p.print_help())
