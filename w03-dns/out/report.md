# Week 3 · Task 2 report

Networks measured: hotspot, wifi
Resolvers: system (system), google (8.8.8.8), quad9 (9.9.9.9)

## Rule

A site is on a **third party** if its CNAME chain ends in a different zone, where
zone = the last two labels of the name. No CNAME means not third party.

## Table

| site | chain length | final zone | third party? (by hand) | rule's verdict | rule right? |
|---|---|---|---|---|---|
| www.microsoft.com | 2 | akamaiedge.net | third | third | ok |
| www.netflix.com | 1 | netflix.com | own | not third | ok |
| www.adobe.com | 2 | akamai.net | third | third | ok |
| www.cnn.com | 1 | fastly.net | third | third | ok |
| www.apple.com | 3 | akamaiedge.net | third | third | ok |
| www.korea.ac.kr | 0 | ac.kr | none | not third | ok |
| www.stanford.edu | 1 | netlifyglobalcdn.com | third | third | ok |
| www.bbc.co.uk | 2 | fastly.net | third | third | ok |
| www.spotify.com | 1 | fastly.net | third | third | ok |
| www.github.com | 1 | github.com | own | not third | ok |
| www.wikipedia.org | 1 | wikimedia.org | own | third | **wrong** |
| www.nytimes.com | 3 | fastly.net | third | third | ok |

## Where the rule was wrong

- **www.wikipedia.org** ends at `dyna.wikimedia.org`. The rule says *third*, but it is *own*: dyna.wikimedia.org - the Wikimedia Foundation runs Wikipedia. Same owner, different domain name.
- Latent: `www.bbc.co.uk` has last two labels `co.uk`, which is a public suffix, not an owner. Had its chain stopped at `pri.bbc.co.uk` the rule would treat every `.co.uk` site as the same owner.
- Blind spot: a site behind an anycast CDN with no CNAME would be called *not third*; the rule only reads names, never who owns the addresses.

## Steering

CDN-hosted sites (own or third-party CDN): N = 11

- **8 of 11** sites answered differently to a different resolver on the same network: www.microsoft.com, www.adobe.com, www.cnn.com, www.apple.com, www.bbc.co.uk, www.spotify.com, www.github.com, www.nytimes.com
- **0 of 11** sites answered differently on a different network (system resolver, hotspot vs wifi): -
- **8 of 11** differed in at least one way

## Raw answers

- www.microsoft.com: hotspot/system=23.49.206.40; hotspot/google=23.49.206.40; hotspot/quad9=23.51.61.225; wifi/system=23.49.206.40; wifi/google=23.49.206.40; wifi/quad9=23.51.61.225
- www.netflix.com: hotspot/system=207.45.72.1,207.45.73.1; hotspot/google=207.45.72.1,207.45.73.1; hotspot/quad9=207.45.72.1,207.45.73.1; wifi/system=207.45.72.1,207.45.73.1; wifi/google=207.45.72.1,207.45.73.1; wifi/quad9=207.45.72.1,207.45.73.1
- www.adobe.com: hotspot/system=23.76.153.115,23.76.153.121; hotspot/google=23.76.153.115,23.76.153.121; hotspot/quad9=23.208.31.169,23.208.31.173; wifi/system=23.76.153.115,23.76.153.121; wifi/google=23.76.153.115,23.76.153.121; wifi/quad9=23.48.167.111,23.48.167.80
- www.cnn.com: hotspot/system=146.75.51.5; hotspot/google=151.101.131.5,151.101.195.5,151.101.3.5,151.101.67.5; hotspot/quad9=151.101.131.5,151.101.195.5,151.101.3.5,151.101.67.5; wifi/system=146.75.51.5; wifi/google=151.101.131.5,151.101.195.5,151.101.3.5,151.101.67.5; wifi/quad9=151.101.131.5,151.101.195.5,151.101.3.5,151.101.67.5
- www.apple.com: hotspot/system=23.49.205.28; hotspot/google=23.49.205.28; hotspot/quad9=184.29.44.235; wifi/system=23.49.205.28; wifi/google=23.49.205.28; wifi/quad9=23.217.180.246
- www.korea.ac.kr: hotspot/system=163.152.6.10; hotspot/google=163.152.6.10; hotspot/quad9=163.152.6.10; wifi/system=163.152.6.10; wifi/google=163.152.6.10; wifi/quad9=163.152.6.10
- www.stanford.edu: hotspot/system=15.197.167.90,3.33.186.135; hotspot/google=15.197.167.90,3.33.186.135; hotspot/quad9=15.197.167.90,3.33.186.135; wifi/system=15.197.167.90,3.33.186.135; wifi/google=15.197.167.90,3.33.186.135; wifi/quad9=15.197.167.90,3.33.186.135
- www.bbc.co.uk: hotspot/system=146.75.48.81; hotspot/google=151.101.0.81,151.101.128.81,151.101.192.81,151.101.64.81; hotspot/quad9=151.101.0.81,151.101.128.81,151.101.192.81,151.101.64.81; wifi/system=146.75.48.81; wifi/google=151.101.0.81,151.101.128.81,151.101.192.81,151.101.64.81; wifi/quad9=151.101.0.81,151.101.128.81,151.101.192.81,151.101.64.81
- www.spotify.com: hotspot/system=146.75.51.42; hotspot/google=151.101.131.42,151.101.195.42,151.101.3.42,151.101.67.42; hotspot/quad9=151.101.131.42,151.101.195.42,151.101.3.42,151.101.67.42; wifi/system=146.75.51.42; wifi/google=151.101.131.42,151.101.195.42,151.101.3.42,151.101.67.42; wifi/quad9=151.101.131.42,151.101.195.42,151.101.3.42,151.101.67.42
- www.github.com: hotspot/system=20.200.245.247; hotspot/google=20.200.245.247; hotspot/quad9=20.27.177.113; wifi/system=20.200.245.247; wifi/google=20.200.245.247; wifi/quad9=20.27.177.113
- www.wikipedia.org: hotspot/system=103.102.166.224; hotspot/google=103.102.166.224; hotspot/quad9=103.102.166.224; wifi/system=103.102.166.224; wifi/google=103.102.166.224; wifi/quad9=103.102.166.224
- www.nytimes.com: hotspot/system=146.75.49.164; hotspot/google=151.101.1.164,151.101.129.164,151.101.193.164,151.101.65.164; hotspot/quad9=151.101.1.164,151.101.129.164,151.101.193.164,151.101.65.164; wifi/system=146.75.49.164; wifi/google=151.101.1.164,151.101.129.164,151.101.193.164,151.101.65.164; wifi/quad9=151.101.1.164,151.101.129.164,151.101.193.164,151.101.65.164

## Part A · capture

Captured on my own Wi-Fi interface while running `python task1_resolve.py www.netflix.com`, then exported only `dns.flags.recdesired == 0` (my resolver's non-recursive queries) so no other app's lookups are in the file. 20 packets: 10 queries and 10 responses.

- A2: packet 1 is a query for www.netflix.com with transaction ID 0x0eb4 (sent to root 198.41.0.4); packet 2 is its response with the same ID 0x0eb4.
- A3: packet 2 is a delegation: Answer RRs 0, 13 NS records in the authority section, 11 glue records in the additional section. Packet 6 is an answer: Answer RRs 1 (the CNAME to www.prod.ftl.netflix.com) from the authoritative server 205.251.192.81. Packet 12 is a delegation with no glue at all (authority 2, additional 0): it points at e.ns.nflxso.net without an address, which is why packets 13-18 are a separate walk to resolve that name. Same message format every time, only the sections that are filled differ.
- A4: the largest response is packet 8, 544 bytes on the wire, a referral from root server 198.41.0.4. It is large because the root lists 13 `.com` TLD nameservers (authority) and attaches 11 glue address records for them (additional). The final answers (packets 18, 20) are only 121 and 161 bytes.
