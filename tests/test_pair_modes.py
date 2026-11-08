"""Revision 2: the partitioned and lazy constructions of the risk relation equal the eager one."""
import random

from taas.contracts import make_contract
from taas.hypergraph import Hypergraph
from taas.policy import Policy

EFFS = [["read(local)"], ["read(web)", "egress(*)"], ["write(fs)"], ["delete(fs)"], ["exec"], ["money"],
        ["read(db)"], ["egress(slack)"]]


def contracts(n, seed):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        c = make_contract(f"s{i % 7}::t{i}", {"q": "query"}, rng.choice(["text", "record:x", "table"]),
                          rng.choice(EFFS), rng.choice(["lex", "ann", "obs", "att"]),
                          source_label="private" if rng.random() < 0.3 else "public")
        out.append(c)
    return out


def build(cs, mode, policy, admin):
    H = Hypergraph(pair_mode=mode)
    for c in cs:
        H.contracts[c.tool] = c
    H.admin_forbidden = dict(admin)
    H.rebuild_pairs(policy)
    return H


def test_pair_modes_equal():
    cs = contracts(160, 3)
    ids = [c.tool for c in cs]
    admin = {tuple(sorted((ids[1], ids[2]))): "admin: never together", tuple(sorted((ids[5], ids[9]))): "admin"}
    for policy in (None, Policy.make("p", forbidden_pairs=(("private_read", "egress_any"), ("effect:write", "effect:exec")))):
        H = {m: build(cs, m, policy, admin) for m in ("eager", "partitioned", "lazy")}
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                e = H["eager"].is_forbidden(a, b)
                assert H["partitioned"].is_forbidden(a, b) == e
                assert H["lazy"].is_forbidden(a, b) == e
