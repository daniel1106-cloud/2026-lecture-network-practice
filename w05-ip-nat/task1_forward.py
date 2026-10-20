#!/usr/bin/env python3
"""Week 5 · Task 1 — Subnets and longest-prefix match.

Textbook §4.3.2 (IPv4 addressing, CIDR) and §4.3.3 (forwarding).

Two things a router does with every packet: work out which prefixes the
destination falls inside, and pick the longest one. The second is the whole
of "longest prefix match", and it is the reason the internet's routing table
can hold a million entries and still be answerable.

You build both, from integers up. No `ipaddress` module - that library is
exactly the thing you are supposed to understand this week.

    python3 task1_forward.py --verify
"""
import argparse


def _ip_to_int(text):
    """'163.152.6.10' -> 32-bit int, using shifts only."""
    parts = text.strip().split(".")
    if len(parts) != 4:
        raise ValueError(f"not a dotted-quad address: {text!r}")
    value = 0
    for part in parts:
        if not part.isdigit() or not 0 <= int(part) <= 255:
            raise ValueError(f"bad octet {part!r} in {text!r}")
        value = (value << 8) | int(part)
    return value


def _int_to_ip(value):
    return ".".join(str((value >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def _mask(prefix_len):
    return (0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF


def parse_cidr(cidr):
    """'163.152.6.0/24' -> (network as int, prefix length).

    Rejects a prefix length outside 0-32, and an address whose host bits are
    set (163.152.6.5/24 is a host written in network notation, not a network).
    """
    address, slash, length = cidr.strip().partition("/")
    if not slash or not length.isdigit():
        raise ValueError(f"not CIDR notation: {cidr!r}")
    prefix_len = int(length)
    if not 0 <= prefix_len <= 32:
        raise ValueError(f"prefix length {prefix_len} is outside 0-32")
    network = _ip_to_int(address)
    if network & ~_mask(prefix_len) & 0xFFFFFFFF:
        raise ValueError(f"{cidr!r} has host bits set")
    return network, prefix_len


def network_range(cidr):
    """'163.152.6.0/24' -> (first usable, last usable, broadcast) as strings.

    Edge cases (RFC 3021): a /31 is a point-to-point link where both addresses
    are hosts, so first = network, last = network + 1 and there is no
    broadcast (None). A /32 is a single host: first = last = that address,
    broadcast None.
    """
    network, prefix_len = parse_cidr(cidr)
    last_address = network | (~_mask(prefix_len) & 0xFFFFFFFF)
    if prefix_len == 32:
        return (_int_to_ip(network), _int_to_ip(network), None)
    if prefix_len == 31:
        return (_int_to_ip(network), _int_to_ip(last_address), None)
    return (_int_to_ip(network + 1), _int_to_ip(last_address - 1),
            _int_to_ip(last_address))


class ForwardingTable:
    """Longest-prefix-match forwarding.

    Routes are grouped by prefix length; a lookup tries the longest length
    first and stops at the first hit, so 0.0.0.0/0 (length 0) is only reached
    when nothing longer matched.

    Two entries with the same network and prefix length are a malformed
    table: the same next hop twice is ignored, a different next hop raises
    ValueError rather than silently picking one.
    """

    def __init__(self):
        self.by_length = {}                 # prefix length -> {network: next hop}

    def add(self, cidr, next_hop):
        network, prefix_len = parse_cidr(cidr)
        routes = self.by_length.setdefault(prefix_len, {})
        if network in routes and routes[network] != next_hop:
            raise ValueError(f"{cidr} already routes to {routes[network]}, "
                             f"cannot also route to {next_hop}")
        routes[network] = next_hop

    def lookup(self, address):
        value = _ip_to_int(address)
        for prefix_len in sorted(self.by_length, reverse=True):
            hop = self.by_length[prefix_len].get(value & _mask(prefix_len))
            if hop is not None:
                return hop
        return None
# ------------------------------------------------------------------- harness
RANGE_CASES = [
    ("192.168.0.0/24",  "192.168.0.1",   "192.168.0.254",  "192.168.0.255"),
    ("10.0.0.0/8",      "10.0.0.1",      "10.255.255.254", "10.255.255.255"),
    ("172.16.32.0/20",  "172.16.32.1",   "172.16.47.254",  "172.16.47.255"),
    ("203.0.113.64/26", "203.0.113.65",  "203.0.113.126",  "203.0.113.127"),
]

TABLE = [
    ("0.0.0.0/0",       "default-gw"),
    ("10.0.0.0/8",      "campus"),
    ("10.20.0.0/16",    "eng-building"),
    ("10.20.30.0/24",   "lab-floor"),
    ("10.20.30.64/26",  "lab-rack-2"),
    ("192.168.1.0/24",  "home"),
]

LOOKUP_CASES = [
    ("10.20.30.70",   "lab-rack-2"),     # inside all four 10.x entries
    ("10.20.30.10",   "lab-floor"),
    ("10.20.99.1",    "eng-building"),
    ("10.99.0.1",     "campus"),
    ("8.8.8.8",       "default-gw"),
    ("192.168.1.77",  "home"),
]


def verify():
    fails = 0
    for cidr, first, last, bcast in RANGE_CASES:
        try:
            got = network_range(cidr)
        except NotImplementedError:
            print("  network_range is still a stub"); return 1
        except Exception as e:
            print(f"  FAIL  {cidr:<18} raised {e!r}"); fails += 1; continue
        ok = tuple(got) == (first, last, bcast)
        print(f"  {'ok  ' if ok else 'FAIL'}  {cidr:<18} {got}")
        fails += not ok

    t = ForwardingTable()
    try:
        for cidr, hop in TABLE:
            t.add(cidr, hop)
    except NotImplementedError:
        print("  ForwardingTable is still a stub"); return 1

    for addr, expect in LOOKUP_CASES:
        got = t.lookup(addr)
        ok = got == expect
        print(f"  {'ok  ' if ok else 'FAIL'}  {addr:<16} -> {got}  (want {expect})")
        fails += not ok

    print(f"\n  {len(RANGE_CASES) + len(LOOKUP_CASES) - fails}"
          f"/{len(RANGE_CASES) + len(LOOKUP_CASES)} ok")
    return 1 if fails else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()
    raise SystemExit(verify() if a.verify else p.print_help())
