# Week 5 · Task 2 report

Two networks, labelled in `addresses.json` as `wifi` (this is the Korea University campus Wi-Fi: the public address 163.152.233.8 is inside 163.152.0.0/16, the same block as www.korea.ac.kr = 163.152.6.10 in Week 3) and `tethering` (my phone's hotspot). Both read off the raw `ipconfig /all` output by hand.

## Part A and B · the two addresses

| | wifi (campus) | tethering (phone) |
|---|---|---|
| A1 interface address | 172.16.8.29 | 10.209.134.205 |
| A1 mask | 255.255.255.0 (/24) | 255.255.255.0 (/24) |
| A2 subnet (by hand, then checked with my Task 1 `network_range`) | 172.16.8.0/24: first 172.16.8.1, last 172.16.8.254, broadcast 172.16.8.255 | 10.209.134.0/24: first 10.209.134.1, last 10.209.134.254, broadcast 10.209.134.255 |
| A3 default gateway | 172.16.8.1, inside the range | 10.209.134.18, inside the range |
| A4 public address seen outside | 163.152.233.8 | 106.101.3.243 |
| A1 private (RFC 1918)? | yes, 172.16.0.0/12 | yes, 10.0.0.0/8 |
| DHCP server / DNS | server 192.168.98.23, DNS 163.152.213.9, 168.126.63.1/2 | server 10.209.134.18 (the gateway), DNS 10.209.134.18 |
| lease | 14:46:31 to 15:16:32 = 30 min | 14:48:29 to 15:48:27 = 1 hour |

**A2/A3.** The gateway has to be inside the subnet because my machine delivers to it directly at layer 2 (ARP for its MAC). A next hop that is not on my own subnet could only be reached through yet another router, which is circular: the default gateway is the very first router.

**A5 · how many NATs.** On the campus Wi-Fi my address is private (172.16.8.29) and the world sees 163.152.233.8, so there is at least one NAT. A traceroute to 8.8.8.8 from the campus Wi-Fi shows where it is: hop 1 172.16.0.2 and hop 2 192.168.98.132 are private, and hop 3 is 163.152.233.129, in the same public /24 as my outside address, so the translation happens between hop 2 and hop 3 at the campus edge. Hops 5 and 6 are private again (10.103.0.142, 10.222.25.128) but those are the ISP routing internally, not another translation of my source address, since the address the server sees is still the campus one. So: one NAT on campus. On the hotspot the laptop's 10.209.134.205 differs from the public 106.101.3.243, so at least one NAT again (the phone). I saw no 100.64.0.0/10 address anywhere, which would be the sign of carrier-grade NAT, but I did not run a traceroute on the hotspot, so I cannot rule out a second layer there. One NAT versus two can be told apart by the hops: a private or 100.64.x hop beyond the first router means a second translator; or by comparing the phone's own address with what the world sees.

**B3 · what changed.** Everything about the private side changed (172.16.8.29 -> 10.209.134.205, gateway 172.16.8.1 -> 10.209.134.18, DNS, DHCP server, lease length) because a different DHCP server gave it to me out of a different pool; the mask (/24) happened to be the same. The public address changed too (163.152.233.8 -> 106.101.3.243), because the world sees the NAT's address and the two NATs belong to different organisations (Korea University vs my phone carrier). Both are private-to-public translations, so the private address tells you nothing about the public one.

## Part C · DHCP in the capture (`dhcp.pcapng`, my machine only: one MAC in the whole file)

| pkt | message | IP src -> dst | Ethernet dst | notes |
|---|---|---|---|---|
| 1 | Release | 172.16.8.29 -> 192.168.98.23 | 00-00-0C-07-AC-FA (gateway) | from my `ipconfig /release`, unicast to the server |
| 2 | **Discover** | **0.0.0.0 -> 255.255.255.255** | FF-FF-FF-FF-FF-FF | UDP 68 -> 67, xid 0xd08ede6c |
| 3 | Offer | 172.16.0.7 -> 172.16.8.29 | my MAC | yiaddr 172.16.8.29, lease 1800 s, router 172.16.8.1 |
| 4 | Request | 0.0.0.0 -> 255.255.255.255 | FF-FF-FF-FF-FF-FF | names server 192.168.98.23 |
| 5 | Ack | 172.16.0.7 -> 172.16.8.29 | my MAC | lease 1800 s |
| 6, 7 | Request, Ack | as above | | Windows asking again 4 s later (lease 1796 s left) |

- **C2.** Discover goes from 0.0.0.0 to 255.255.255.255. The source is 0.0.0.0 because I do not have an address yet, and I am asking for one, so there is nothing else I could put there. The destination has to be the limited broadcast because I also do not know any server's address: the only way to reach "whoever runs DHCP here" is to shout to everybody on the link (Ethernet FF-FF-FF-FF-FF-FF).
- **C3.** The lease the server offered is 1800 seconds = 30 minutes (it matches 14:46:31 to 15:16:32 in `ipconfig`). The packet carries no renewal timers, so the defaults of RFC 2131 apply: I will try to renew at half the lease (T1, 900 s) by asking the same server directly, and rebind by broadcast at 87.5% (T2, 1575 s).
- **C4.** The Offer and the Ack were not broadcast: the Ethernet destination is my own MAC and the IP destination is 172.16.8.29, the address being offered. What changed is that after the Discover the server knows who I am (my hardware address is in the message) and has picked an address for me, so it can address me directly even though I have not configured it yet. My Discover also had the broadcast flag clear, i.e. it told the server unicast replies are fine. The Request, by contrast, goes out as a broadcast again, so every server that made an offer learns which one I accepted. Also note the Offer came from 172.16.0.7 while the server identifier inside is 192.168.98.23, which is not on my subnet, so a relay on campus is passing the messages along.
