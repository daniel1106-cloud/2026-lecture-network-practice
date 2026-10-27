#!/usr/bin/env python3
"""Week 6 · Task 3 — Reconverge without recomputing the world.

Textbook §5.2.1, §5.3.

A link flaps. Every router in the area has to decide what changed. `FullRecompute`
does the honest thing: throw the table away and run Dijkstra again, from scratch,
for every event. It is correct and it is what the first implementations did.

It is also why a single flapping link in a large area used to melt the CPU of
every router that could see it.

Beat it:

    python3 bench.py
    python3 bench.py --yours

Correctness first. `bench.py` compares your table against a full recompute after
**every single event**. A router that is fast and wrong black-holes traffic.
"""
import heapq

# The harness counts how many times you run a full SPF. This is the score:
# wall-clock time in Python says more about dictionary overhead than about
# routing, but "how many times did the CPU have to recompute the world" is
# exactly what melted real routers.
SPF_RUNS = 0


def dijkstra_table(graph, source):
    """Reference shortest-path-first. Returns {destination: first_hop}.

    Use THIS function whenever you need a full recompute. Rolling your own to
    dodge the counter is not an optimisation, it is cheating the meter.
    """
    global SPF_RUNS
    SPF_RUNS += 1
    best = {source: (0, None)}
    pq, done = [(0, source, None)], set()
    while pq:
        cost, node, first_hop = heapq.heappop(pq)
        if node in done:
            continue
        done.add(node)
        best[node] = (cost, first_hop)
        for nbr, w in sorted(graph[node].items()):
            if nbr in done:
                continue
            hop = nbr if node == source else first_hop
            if cost + w < best.get(nbr, (float("inf"), None))[0]:
                best[nbr] = (cost + w, hop)
                heapq.heappush(pq, (cost + w, nbr, hop))
    return {d: h for d, (_, h) in best.items() if d != source and h}


class FullRecompute:
    """On every event, forget everything and run SPF again."""

    def __init__(self, graph, source):
        self.graph = {n: dict(e) for n, e in graph.items()}
        self.source = source
        self.table = dijkstra_table(self.graph, source)

    def link_change(self, a, b, cost):
        """cost=None means the link went down."""
        if cost is None:
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        else:
            self.graph[a][b] = cost
            self.graph[b][a] = cost
        self.table = dijkstra_table(self.graph, self.source)


class YourRouter:
    """Incremental SPF: repair only the part of the tree a link change touches.

    Kept between events (about 400 entries each, so a few tens of KB):
      dist    shortest cost from the source to every reachable node
      parent  each node's chosen predecessor on its shortest path
      table   destination -> first hop (the thing the harness checks)

    What a link change can do:

      * link down or dearer, and it was on no shortest path (dist[a] + w is not
        dist[b], nor the other way round): nothing changes. Free.
      * link up or cheaper, and it neither ties nor beats what the nodes behind
        it already have (dist[a] + w > dist[b] and the same the other way):
        useless. Free.
      * otherwise some distances change. Only those nodes, and the ones hanging
        below them in the tree, are repaired, not the whole area. Costs are
        repaired with a local Dijkstra seeded from the unaffected border, which
        is what incremental SPF does.

    The table has to equal the reference's, ties included. dijkstra_table
    settles nodes in (cost, name) order, and the first settled node that reaches
    v at its final cost becomes v's parent. So parent[v] is the tight neighbour
    with the smallest (dist, name), and v's first hop is its parent's first hop
    (or v itself when the parent is the source). That rule is local: a change
    only has to re-decide the parent of nodes whose distance moved and of their
    neighbours.

    If one change moves more than FALLBACK nodes the local repair is no cheaper
    than the real thing, so one full dijkstra_table is run (and counted).
    """

    INF = float("inf")
    FALLBACK = 100

    def __init__(self, graph, source):
        self.graph = {n: dict(e) for n, e in graph.items()}
        self.source = source
        self.table = dijkstra_table(self.graph, source)         # the one counted SPF
        self.dist = self._distances()
        self.parent = {}
        self._rebuild_parents()

    # ---------------------------------------------------------------- events
    def link_change(self, a, b, cost):
        """cost=None means the link went down."""
        old = self.graph[a].get(b)
        if cost == old:
            return
        self._set_edge(a, b, cost)
        if cost is None or (old is not None and cost > old):
            changed = self._repair_after_increase(a, b, old) if old is not None else set()
        else:
            changed = self._repair_after_decrease(a, b, cost)

        if len(changed) > self.FALLBACK:
            self.table = dijkstra_table(self.graph, self.source)
            self._rebuild_parents()
            return
        self._repair_tree(changed | {a, b})

    # ----------------------------------------------------------- tree repair
    def _best_parent(self, n):
        """Tight neighbour with the smallest (dist, name), as the reference picks."""
        d, best = self.dist, None
        for p, w in self.graph[n].items():
            if p in d and d[p] + w == d[n]:
                key = (d[p], p)
                if best is None or key < best:
                    best = key
        return None if best is None else best[1]

    def _repair_tree(self, touched):
        """Re-decide parents and first hops of touched nodes, then of anything
        below a node whose first hop changed, nearest to the source first."""
        d = self.dist
        seeds = set(touched)
        for n in touched:
            seeds.update(self.graph[n])             # a neighbour's distance moved
        heap = [(d[n], n) for n in seeds if n in d and n != self.source]
        heapq.heapify(heap)
        for n in list(self.parent):                 # nodes that became unreachable
            if n not in d:
                del self.parent[n]
                self.table.pop(n, None)
        done = set()
        while heap:
            _, n = heapq.heappop(heap)
            if n in done:
                continue
            done.add(n)
            p = self._best_parent(n)
            hop = n if p == self.source else self.table.get(p)
            if p == self.parent.get(n) and hop == self.table.get(n):
                continue
            self.parent[n] = p
            self.table[n] = hop
            for m in self.graph[n]:                 # children inherit the new hop
                if self.parent.get(m) == n and m not in done:
                    heapq.heappush(heap, (d[m], m))

    def _rebuild_parents(self):
        self.parent = {n: self._best_parent(n) for n in self.dist if n != self.source}

    # ------------------------------------------------------------ distances
    def _set_edge(self, a, b, cost):
        if cost is None:
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        else:
            self.graph[a][b] = cost
            self.graph[b][a] = cost

    def _distances(self):
        """Plain Dijkstra over costs, once, at start-up."""
        dist, heap = {}, [(0, self.source)]
        while heap:
            c, n = heapq.heappop(heap)
            if n in dist:
                continue
            dist[n] = c
            for m, w in self.graph[n].items():
                if m not in dist:
                    heapq.heappush(heap, (c + w, m))
        return dist

    def _repair_after_decrease(self, a, b, w):
        """New or cheaper link: relax outwards from whichever end improves."""
        d, heap, changed = self.dist, [], set()
        for u, v in ((a, b), (b, a)):
            if u in d and d[u] + w < d.get(v, self.INF):
                d[v] = d[u] + w
                changed.add(v)
                heapq.heappush(heap, (d[v], v))
        while heap:
            c, n = heapq.heappop(heap)
            if c > d[n]:
                continue
            for m, x in self.graph[n].items():
                if c + x < d.get(m, self.INF):
                    d[m] = c + x
                    changed.add(m)
                    heapq.heappush(heap, (d[m], m))
        return changed

    def _repair_after_increase(self, a, b, old):
        """Link removed or dearer. The nodes that lose every shortest path are
        found nearest-first, then recomputed from their unaffected neighbours."""
        d = self.dist
        affected, heap, seen = set(), [], set()
        for u, v in ((a, b), (b, a)):
            if u in d and v in d and d[u] + old == d[v]:
                heapq.heappush(heap, (d[v], v))
        while heap:
            c, n = heapq.heappop(heap)
            if n in seen:
                continue
            seen.add(n)
            if any(p not in affected and p in d and d[p] + w == d[n]
                   for p, w in self.graph[n].items()):
                continue                              # still has a shortest path
            affected.add(n)
            for m, w in self.graph[n].items():
                if m in d and d[n] + w == d[m]:
                    heapq.heappush(heap, (d[m], m))
        for n in affected:
            del d[n]
        for n in affected:                            # seed from the unaffected border
            best = min((d[p] + w for p, w in self.graph[n].items() if p in d),
                       default=self.INF)
            if best < self.INF:
                heapq.heappush(heap, (best, n))
        while heap:
            c, n = heapq.heappop(heap)
            if n in d:
                continue
            d[n] = c
            for m, w in self.graph[n].items():
                if m in affected and m not in d:
                    heapq.heappush(heap, (c + w, m))
        return affected