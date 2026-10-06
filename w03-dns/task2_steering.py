#!/usr/bin/env python3
"""Week 3 · Task 2 — Does DNS actually steer you? Measure it.

Textbook §2.4.3 (records) and §2.5 (CDNs).

The lecture claims two things:

    (a) most large sites are served by a CDN, reached through a CNAME chain
    (b) DNS steers each user to a *nearby* replica

Both are testable from your laptop, and one of them is harder to prove than
the slide makes it look. Your job is to produce the evidence and a number.

    python3 task2_steering.py --collect        # gather the raw data
    python3 task2_steering.py --report         # your analysis

What you have to build
----------------------
1.  For each hostname in SITES, follow the CNAME chain to its end and record
    every hop. `--collect` should leave the raw data in out/chains.json.

2.  Decide, for each site, whether it is served by a **third party**.
    This is the hard part and there is no single right answer:

      - `www.microsoft.com` ends at `akamaiedge.net`     - clearly third party
      - `www.netflix.com`   stops inside `netflix.com`   - own CDN, not third party
      - some sites have no CNAME at all and still sit behind a CDN (anycast)
      - `foo.cloudfront.net` and `foo.s3.amazonaws.com` are both Amazon,
        but they are not the same service

    Write down the rule you used and **defend it in observation.md**. A rule
    that just compares the last two labels will be wrong on at least one of
    the sites below; find which, and say so.

3.  Ask **two different resolvers** for the same name and compare the
    addresses you get back. If DNS really steers by location, a CDN-hosted
    name should answer differently to resolvers sitting in different places.

        RESOLVERS below has your system resolver and two public ones.

    Report: of N CDN-hosted sites, how many returned a different address set
    from a different resolver? Claim (b) predicts most of them. Check it.

Pass condition
--------------
There is no fixed answer. You pass by producing, in out/report.md:

  - the table: site | chain length | final zone | third party? | your rule's verdict
  - the steering number: "X of N sites answered differently to a different resolver"
  - at least one site where your classification rule was wrong, and why
"""
import argparse, json, os

import dns.resolver

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
CHAINS = os.path.join(OUT, "chains.json")
REPORT = os.path.join(OUT, "report.md")
CAPTURE_NOTES = os.path.join(OUT, "capture-notes.md")

SITES = [
    "www.microsoft.com",     # Akamai, multi-hop
    "www.netflix.com",       # own CDN
    "www.adobe.com",
    "www.cnn.com",
    "www.apple.com",
    "www.korea.ac.kr",       # no CDN at all
    "www.stanford.edu",
    "www.bbc.co.uk",
    "www.spotify.com",
    "www.github.com",
    "www.wikipedia.org",
    "www.nytimes.com",
]

RESOLVERS = {
    "system": None,          # whatever Windows is configured to use
    "google": "8.8.8.8",
    "quad9":  "9.9.9.9",
}

# What I decided by hand after reading each chain (and who owns the final name).
# This is the "truth" column the rule is judged against.
TRUTH = {
    "www.microsoft.com": ("third", "ends at akamaiedge.net (Akamai)"),
    "www.netflix.com":   ("own",   "stays inside netflix.com - Netflix's own CDN"),
    "www.adobe.com":     ("third", "edgesuite.net -> akamai.net (Akamai)"),
    "www.cnn.com":       ("third", "map.fastly.net (Fastly)"),
    "www.apple.com":     ("third", "aaplimg.com is Apple's, but it hands off to akamaiedge.net"),
    "www.korea.ac.kr":   ("none",  "no CNAME, the university's own server"),
    "www.stanford.edu":  ("third", "netlifyglobalcdn.com (Netlify)"),
    "www.bbc.co.uk":     ("third", "pri.bbc.co.uk -> map.fastly.net (Fastly)"),
    "www.spotify.com":   ("third", "map.fastly.net (Fastly)"),
    "www.github.com":    ("own",   "CNAME to github.com, GitHub's own servers"),
    "www.wikipedia.org": ("own",   "dyna.wikimedia.org - the Wikimedia Foundation runs Wikipedia"),
    "www.nytimes.com":   ("third", "nyt.net -> map.fastly.net (Fastly)"),
}


def make_resolver(server):
    """Transport only. server=None means the system resolver."""
    if server is None:
        r = dns.resolver.Resolver()
    else:
        r = dns.resolver.Resolver(configure=False)
        r.nameservers = [server]
    r.lifetime = 5
    return r


def lookup(name, server=None):
    """-> (cname chain, sorted A addresses)."""
    answer = make_resolver(server).resolve(name, "A")
    chain = [str(rr[0].target).rstrip(".") for rr in answer.chaining_result.cnames]
    return chain, sorted(rr.address for rr in answer)


def zone(name):
    """The rule's idea of 'who owns this name': the last two labels."""
    return ".".join(name.split(".")[-2:])


def rule(site, final):
    """My rule: third party if the chain ends in a different last-two-label zone."""
    return "third" if zone(final) != zone(site) else "not third"


def collect(network):
    data = json.load(open(CHAINS, encoding="utf-8")) if os.path.exists(CHAINS) else {}
    for site in SITES:
        entry = data.setdefault(site, {"answers": {}})
        chain, _ = lookup(site, "8.8.8.8")                       # B1
        entry["chain"] = chain
        entry["final"] = chain[-1] if chain else site
        entry["answers"][network] = {}
        for label, server in RESOLVERS.items():                  # B2
            try:
                _, addrs = lookup(site, server)
            except Exception as e:
                addrs = [f"error: {type(e).__name__}"]
            entry["answers"][network][label] = addrs
        print(f"  {site:<20} chain={len(chain)}  "
              + "  ".join(f"{k}={','.join(v)}" for k, v in entry["answers"][network].items()))
    json.dump(data, open(CHAINS, "w", encoding="utf-8"), indent=2)
    print(f"\n  saved network '{network}' -> {CHAINS}")


def report():
    data = json.load(open(CHAINS, encoding="utf-8"))
    networks = sorted({n for e in data.values() for n in e["answers"]})

    rows, wrong = [], []
    for site in SITES:
        e = data[site]
        truth, why = TRUTH[site]
        verdict = rule(site, e["final"])
        ok = (verdict == "third") == (truth == "third")
        if not ok:
            wrong.append((site, e["final"], verdict, truth, why))
        rows.append(f"| {site} | {len(e['chain'])} | {zone(e['final'])} | {truth} | "
                    f"{verdict} | {'ok' if ok else '**wrong**'} |")

    # B5: of the CDN-hosted sites, which gave different address sets
    cdn = [s for s in SITES if TRUTH[s][0] != "none"]
    by_resolver, by_network, any_diff = [], [], []
    for site in cdn:
        ans = data[site]["answers"]
        per_net = [{tuple(a) for a in ans[n].values()} for n in networks]
        if any(len(s) > 1 for s in per_net):
            by_resolver.append(site)
        if len(networks) > 1 and len({tuple(ans[n]["system"]) for n in networks}) > 1:
            by_network.append(site)
        if len(set().union(*per_net)) > 1:
            any_diff.append(site)

    lines = [
        "# Week 3 · Task 2 report", "",
        f"Networks measured: {', '.join(networks)}",
        f"Resolvers: {', '.join(f'{k} ({v or 'system'})' for k, v in RESOLVERS.items())}", "",
        "## Rule", "",
        "A site is on a **third party** if its CNAME chain ends in a different zone, where",
        "zone = the last two labels of the name. No CNAME means not third party.", "",
        "## Table", "",
        "| site | chain length | final zone | third party? (by hand) | rule's verdict | rule right? |",
        "|---|---|---|---|---|---|",
        *rows, "",
        "## Where the rule was wrong", "",
    ]
    for site, final, verdict, truth, why in wrong:
        lines.append(f"- **{site}** ends at `{final}`. The rule says *{verdict}*, "
                     f"but it is *{truth}*: {why}. Same owner, different domain name.")
    lines += [
        "- Latent: `www.bbc.co.uk` has last two labels `co.uk`, which is a public suffix, not an owner. "
        "Had its chain stopped at `pri.bbc.co.uk` the rule would treat every `.co.uk` site as the same owner.",
        "- Blind spot: a site behind an anycast CDN with no CNAME would be called *not third*; "
        "the rule only reads names, never who owns the addresses.", "",
        "## Steering", "",
        f"CDN-hosted sites (own or third-party CDN): N = {len(cdn)}", "",
        f"- **{len(by_resolver)} of {len(cdn)}** sites answered differently to a different resolver "
        f"on the same network: {', '.join(by_resolver) or '-'}",
        f"- **{len(by_network)} of {len(cdn)}** sites answered differently on a different network "
        f"(system resolver, {' vs '.join(networks)}): {', '.join(by_network) or '-'}",
        f"- **{len(any_diff)} of {len(cdn)}** differed in at least one way", "",
        "## Raw answers", "",
    ]
    for site in SITES:
        lines.append(f"- {site}: " + "; ".join(
            f"{n}/{r}={','.join(a)}" for n in networks
            for r, a in data[site]["answers"][n].items()))
    lines += ["", "## Part A · capture", ""]
    if os.path.exists(CAPTURE_NOTES):
        lines.append(open(CAPTURE_NOTES, encoding="utf-8").read().strip())
    else:
        lines.append("(write out/capture-notes.md and run --report again)")

    open(REPORT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"  wrote {REPORT}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--collect", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--network", default="wifi",
                   help="a label for the network you are on, e.g. wifi or hotspot")
    a = p.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.collect:
        collect(a.network)
    elif a.report:
        report()
    else:
        p.print_help()