#!/usr/bin/env python3
"""Week 5 · Task 3 — Make longest-prefix match fast.

Textbook §4.3.3.

`LinearTable` is correct and it is what you probably wrote in Task 1: keep the
prefixes in a list, check every one, remember the longest that matched. On six
entries that is fine. A real router holds close to a million, and it has to
answer while the packet is still in the buffer.

Beat it:

    python3 bench.py
    python3 bench.py --yours

Correctness first: `bench.py` checks every one of your answers against the
linear table. A fast router that forwards to the wrong next hop is not a
router, it is an outage.
"""


class LinearTable:
    """Correct, and slow in the obvious way."""

    def __init__(self):
        self.entries = []                     # (prefix_len, network, next_hop)

    def add(self, network, prefix_len, next_hop):
        self.entries.append((prefix_len, network, next_hop))

    def lookup(self, address):
        best = None
        for plen, net, hop in self.entries:
            mask = (0xFFFFFFFF << (32 - plen)) & 0xFFFFFFFF
            if address & mask == net and (best is None or plen > best[0]):
                best = (plen, hop)
        return best[1] if best else None


class YourTable:
    """Routes grouped by prefix length, longest length tried first.

    There are at most 33 prefix lengths, and a real table uses a handful (this
    benchmark uses 7). For each length I keep a dict {network: next_hop}.
    A lookup masks the address with each length's mask, longest first, and
    stops at the first dict hit - which is by definition the longest match.
    The default route is length 0, so it is only reached when everything
    longer missed.

    Memory: one dict entry per route, plus one small tuple per length.
    Time: at most one dict probe per distinct length, so it is bounded by the
    number of lengths (<= 33), not by the number of routes.
    """

    def __init__(self):
        self.by_length = {}         # prefix length -> {network: next_hop}
        self.steps = ()             # ((mask, dict), ...) longest length first

    def add(self, network, prefix_len, next_hop):
        self.by_length.setdefault(prefix_len, {})[network] = next_hop
        self.steps = tuple(
            ((0xFFFFFFFF << (32 - length)) & 0xFFFFFFFF, self.by_length[length])
            for length in sorted(self.by_length, reverse=True))

    def lookup(self, address):
        for mask, routes in self.steps:
            hop = routes.get(address & mask)
            if hop is not None:
                return hop
        return None