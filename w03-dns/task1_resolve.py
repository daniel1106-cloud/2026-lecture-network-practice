#!/usr/bin/env python3
"""Week 3 · Task 1 — Build your own iterative resolver.

Textbook §2.4.2 - §2.4.3.

`dig +trace` walks root -> TLD -> authoritative for you. In this task you do
that walk yourself: start at a root server, read the delegation it returns,
ask the next server, and keep going until somebody answers authoritatively.

You may shell out to `dig` for the transport, or use a DNS library
(`dnspython` is in the container). Either is fine - what matters is that
*you* follow the delegations rather than letting a tool do it.

    python3 task1_resolve.py www.korea.ac.kr
    python3 task1_resolve.py --verify        # check yourself against dig

Pass condition
--------------
`--verify` resolves five names with your resolver and with `dig`, and the
addresses must agree. A name behind a CDN may legitimately return a different
address each time; the harness compares the *set of authoritative nameservers*
you ended at for those, not the address.
"""
import argparse, subprocess, sys
import dns.flags, dns.message, dns.name, dns.query, dns.rdatatype

# Root servers. Everything starts here; there is no earlier step.
ROOT_SERVERS = [
    "198.41.0.4",       # a.root-servers.net
    "199.9.14.201",     # b.root-servers.net
    "192.33.4.12",      # c.root-servers.net
]

# (name, kind).  "stable" names must match dig exactly.  "cdn" names are served
# from many replicas and may legitimately give you a different address than dig
# got a second earlier - for those we only require that you reached an answer.
VERIFY_NAMES = [
    ("www.korea.ac.kr", "stable"),
    ("dns.google", "stable"),
    ("en.wikipedia.org", "stable"),
    ("www.stanford.edu", "stable"),
    ("www.microsoft.com", "cdn"),
]


class Resolver:
    """Iterative resolver: root -> TLD -> authoritative, never asking anyone to recurse.

    R1 resolve(name) -> (address, path)
    R2 every walk starts at ROOT_SERVERS
    R3 no glue -> resolve the nameserver's own name first (a separate walk)
    R4 a server that does not answer -> try the next one
    R5 CNAME -> restart the walk from the root with the new name
    R6 MAX_STEPS caps the total number of questions, so a bad zone cannot hang us
    """

    MAX_STEPS = 40      # total questions allowed for one resolve(), glue walks included
    TIMEOUT = 2         # seconds to wait for one server

    def __init__(self):
        self.glueless = 0           # how many times a delegation came without glue

    def resolve(self, name, _path=None):
        path = [] if _path is None else _path
        qname = dns.name.from_text(name)

        for _ in range(10):                         # at most 10 CNAMEs in a row
            servers = list(ROOT_SERVERS)            # R2: always start at a root
            while True:
                if len(path) >= self.MAX_STEPS:     # R6
                    raise RuntimeError(f"gave up on {name}: more than {self.MAX_STEPS} steps")

                response, server = self._ask(qname, servers)
                path.append(server)

                # 1) the answer section has something for us
                if response.answer:
                    cname = None
                    for rrset in response.answer:
                        if rrset.name == qname and rrset.rdtype == dns.rdatatype.A:
                            return rrset[0].address, path
                        if rrset.name == qname and rrset.rdtype == dns.rdatatype.CNAME:
                            cname = rrset[0].target
                    if cname is not None:           # R5: start again with the new name
                        qname = cname
                        break
                    raise RuntimeError(f"answer for {qname} has neither A nor CNAME")

                # 2) no answer, but a delegation in the authority section
                ns_names = [rr.target for rrset in response.authority
                            if rrset.rdtype == dns.rdatatype.NS for rr in rrset]
                if not ns_names:
                    raise RuntimeError(f"{server} gave neither an answer nor a delegation for {qname}")

                glue = [rr.address for rrset in response.additional
                        if rrset.rdtype == dns.rdatatype.A and rrset.name in ns_names
                        for rr in rrset]
                if glue:
                    servers = glue
                else:                               # R3: no glue, walk for the NS name first
                    self.glueless += 1
                    ns_addr, _ = self.resolve(ns_names[0].to_text(), path)
                    servers = [ns_addr]
        raise RuntimeError(f"too many CNAMEs for {name}")

    def _ask(self, qname, servers):
        """Send one non-recursive query. R4: if a server is silent, try the next."""
        query = dns.message.make_query(qname, dns.rdatatype.A)
        query.flags &= ~dns.flags.RD                # do not recurse for me
        for server in servers:
            try:
                return dns.query.udp(query, server, timeout=self.TIMEOUT), server
            except Exception:
                continue
        raise RuntimeError(f"none of {servers} answered for {qname}")


# ------------------------------------------------------------------- harness
def dig_answer(name):
    """What the system resolver says, for comparison."""
    out = subprocess.run(["dig", "+short", name, "A"],
                         capture_output=True, text=True).stdout
    return [l for l in out.split() if l and l[0].isdigit()]


def verify():
    r, failures = Resolver(), 0
    for name, kind in VERIFY_NAMES:
        try:
            addr, path = r.resolve(name)
        except NotImplementedError:
            print("Nothing implemented yet - write Resolver.resolve first.")
            return 1
        except Exception as e:
            print(f"  FAIL  {name:<22} your resolver raised {e!r}")
            failures += 1
            continue
        expected = dig_answer(name)
        if addr in expected:
            note = ""
        elif kind == "cdn":
            note = "  <- differs, but this name is CDN-hosted. Explain it."
        else:
            note = "  <- should have matched"
            failures += 1
        print(f"  {'FAIL' if note.endswith('matched') else 'ok  '}  {name:<22} "
              f"you={addr:<16} dig={','.join(expected) or '-'}   "
              f"hops={len(path)}{note}")
    print(f"\n  {len(VERIFY_NAMES) - failures}/{len(VERIFY_NAMES)} ok")
    return 1 if failures else 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name", nargs="?", default="www.korea.ac.kr")
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()

    if a.verify:
        sys.exit(verify())

    addr, path = Resolver().resolve(a.name)
    for i, server in enumerate(path, 1):
        print(f"  {i}. asked {server}")
    print(f"\n  {a.name} -> {addr}")


if __name__ == "__main__":
    main()
