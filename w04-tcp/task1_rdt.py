#!/usr/bin/env python3
"""Week 4 · Task 1 — Build reliable delivery on top of an unreliable channel.

Textbook §3.4 (reliable data transfer) and §3.5 (TCP's sequence numbers).

`UnreliableChannel` below loses packets, reorders them, duplicates them, and
delays them. It is the network as §3.4 models it. Your job is to move a file
across it and have the bytes arrive intact and in order.

That is the whole of TCP's reliability story with the congestion control taken
out, and it is worth building once by hand before you ever trust a socket again.

    python3 task1_rdt.py --verify
"""
import argparse, hashlib, random

PAYLOAD = 8            # bytes per packet - small, so you see the sequencing


class UnreliableChannel:
    """Loses 10%, duplicates 3%, reorders, and delays. Deterministic by seed.

    You may not make it nicer. You may not read its internals. It is the only
    way your sender can reach your receiver.
    """

    def __init__(self, seed=246, loss=0.10, dup=0.03, reorder=0.10):
        self.rng = random.Random(seed)
        self.loss, self.dup, self.reorder = loss, dup, reorder
        self.wire = []          # packets in flight, in no particular order
        self.stats = {"sent": 0, "lost": 0, "duplicated": 0, "delivered": 0}

    def send(self, packet):
        """Hand a packet to the network. It may never come out."""
        self.stats["sent"] += 1
        if self.rng.random() < self.loss:
            self.stats["lost"] += 1
            return
        copies = 2 if self.rng.random() < self.dup else 1
        self.stats["duplicated"] += copies - 1
        for _ in range(copies):
            if self.rng.random() < self.reorder and self.wire:
                self.wire.insert(self.rng.randrange(len(self.wire)), packet)
            else:
                self.wire.append(packet)

    def receive(self):
        """Take the next packet out, or None if the network has nothing."""
        if not self.wire:
            return None
        self.stats["delivered"] += 1
        return self.wire.pop(0)


class Sender:
    """Selective repeat: a window of packets in flight, each ACKed on its own.

    Packets are ("D", seq, payload). ACKs are ("A", seq) and name the one
    packet they confirm, so a duplicate or stale ACK can only ever mark a
    packet that really was received - it can never skip one.
    """

    WINDOW = 8          # packets allowed in flight
    TIMEOUT = 40        # steps to wait for an ACK before sending again

    def __init__(self, data_channel, ack_channel, data):
        self.up, self.down = data_channel, ack_channel
        self.chunks = [data[i:i + PAYLOAD] for i in range(0, len(data), PAYLOAD)]
        self.acked = set()          # seqs the receiver has confirmed
        self.sent_at = {}           # seq -> step it was last sent, if unacked
        self.base = 0               # lowest seq not yet acked
        self.next_seq = 0           # next seq never sent
        self.now = 0

    def step(self):
        self.now += 1

        # 1) read at most one ACK, and only trust the number written on it
        pkt = self.down.receive()
        if pkt is not None and pkt[0] == "A" and pkt[1] < len(self.chunks):
            self.acked.add(pkt[1])
            self.sent_at.pop(pkt[1], None)
        while self.base in self.acked:
            self.base += 1

        if self.base >= len(self.chunks):
            return False            # everything confirmed

        # 2) send one packet: the oldest timed-out one, else a new one
        late = [s for s, t in self.sent_at.items() if self.now - t >= self.TIMEOUT]
        if late:
            seq = min(late)
        elif self.next_seq < len(self.chunks) and self.next_seq < self.base + self.WINDOW:
            seq = self.next_seq
            self.next_seq += 1
        else:
            return True
        self.up.send(("D", seq, self.chunks[seq]))
        self.sent_at[seq] = self.now
        return True


class Receiver:
    """Keeps every packet by sequence number and ACKs each one it sees."""

    def __init__(self, data_channel, ack_channel):
        self.up, self.down = data_channel, ack_channel
        self.got = {}               # seq -> payload; a duplicate just overwrites itself

    def step(self):
        pkt = self.up.receive()
        if pkt is None or pkt[0] != "D":
            return
        _, seq, payload = pkt
        self.got[seq] = payload
        self.down.send(("A", seq))  # ACK duplicates too: the first ACK may have been lost

    def data(self):
        """Only the contiguous prefix: bytes in order with no hole before them."""
        out, seq = [], 0
        while seq in self.got:
            out.append(self.got[seq])
            seq += 1
        return b"".join(out)

# ------------------------------------------------------------------- harness
def verify(seed=246, size=2000, max_steps=200_000):
    original = bytes(random.Random(seed).getrandbits(8) for _ in range(size))
    up, down = UnreliableChannel(seed), UnreliableChannel(seed + 1)

    # Data goes out over `up`, ACKs come back over `down`. Both are unreliable.
    sender = Sender(up, down, original)
    receiver = Receiver(up, down)

    for _ in range(max_steps):
        alive = sender.step()
        receiver.step()
        if not alive and len(receiver.data() or b"") >= size:
            break

    got = receiver.data() or b""
    ok = hashlib.sha256(got).hexdigest() == hashlib.sha256(original).hexdigest()
    print(f"  bytes    sent {size}   received {len(got)}")
    print(f"  channel  {up.stats}")
    print(f"  result   {'IDENTICAL' if ok else 'CORRUPTED OR INCOMPLETE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify", action="store_true")
    p.add_argument("--seed", type=int, default=246)
    a = p.parse_args()
    raise SystemExit(verify(a.seed) if a.verify else p.print_help())
