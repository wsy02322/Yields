"""Lido EarnETH: clean deposit→withdraw round-trips vs oracle share-price path.

Mellow async queues (not sync ERC4626):
  DepositRequested → DepositRequestClaimed (shares)
  RedeemRequested  → RedeemRequestClaimed (assets in queue asset, typically wstETH)

A = eth_out / eth_in - 1
B = p1 / p0 * (1 - redeem_fee) - 1   # redeem_fee = 0 on-chain
p  = eth_per_share = 1e36 / oracle.getReport(ETH).priceD18
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from eth_abi import decode
from eth_utils import keccak, to_checksum_address
from web3 import Web3

from src import eth_call, retry_call
from src.calculators.apy import annualize as annualize_apy
from src.fetchers.earneth import ETH_SENTINEL, eth_per_share_wei, get_oracle_report

VAULT = "0x6a37725ca7f4CE81c004c955f7280d5C704a249e"
ORACLE = "0xAda1f4c24603aB2fe5aBd35BCD12370e98A20358"
SHARE_TOKEN = "0xBBFC8683C8fE8cF73777feDE7ab9574935fea0A4"
WSTETH = "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
REDEEM_FEE = 0.0

# QueueCreated(queue, asset, isDeposit) on vault — discovered WP0
ETH_DEPOSIT_QUEUES = [
    "0x1db7094Ef0D994B0b62f6Cd67dB801ad194999A8",
    "0x4a1d5dd96d6AA2Ba82e748E941d4425cb117dE84",
    "0xb99394f8b95d426Cb2F013B857C74aCC924b20D5",
]
WETH_DEPOSIT_QUEUES = [
    "0x3Fc48660d02e59fBedD0a5Cc18a5580D1f8dD6A4",
    "0x3B374Be4c02D7367a1fDDCcDbc2EAA708BB220a0",
    "0xCe6C2505fEF74d2dE10FCF1d534cB73eCc837976",
]
WSTETH_DEPOSIT_QUEUES = [
    "0xe39EED9A454C4918F8d0682062777cB251cd513F",
    "0xD39ceac8EAfc9c8dBf52319B900CA6623730d4BA",
    "0xECD2Bfe725fa14f5Ed86e9bDcc0eA4b34A4ed522",
]
REDEEM_QUEUE_WSTETH = "0x095bFAca9f1c6F2B063Cd67C6d6bfcd0c3aaB7b4"

QUEUE_CREATED_TOPIC = "0x" + keccak(text="QueueCreated(address,address,bool)").hex()
DEP_REQ_TOPIC = "0x" + keccak(text="DepositRequested(address,address,uint224,uint32)").hex()
DEP_CLAIM_TOPIC = "0x" + keccak(text="DepositRequestClaimed(address,uint256,uint32)").hex()
RED_REQ_TOPIC = "0x" + keccak(text="RedeemRequested(address,uint256,uint256)").hex()
RED_CLAIM_TOPIC = (
    "0x" + keccak(text="RedeemRequestClaimed(address,address,uint256,uint32)").hex()
)


@dataclass
class QueueEvent:
    kind: str  # dep_req | dep_claim | red_req | red_claim
    queue: str
    asset: str  # ETH | WETH | wstETH
    block: int
    timestamp: int  # block timestamp
    tx_hash: str
    log_index: int
    owner: str
    amount: float  # assets (req/claim redeem) or shares (dep claim / red req)
    request_ts: int  # event-encoded request timestamp for matching
    receiver: str | None = None
    referral: str | None = None


def _addr_from_topic(topic) -> str:
    h = topic.hex() if hasattr(topic, "hex") else str(topic)
    h = h[2:] if h.startswith("0x") else h
    return to_checksum_address("0x" + h[-40:])


def eth_per_share(w3: Web3, block: int | str, oracle: str = ORACLE) -> float:
    price_d18, _, _ = get_oracle_report(w3, oracle, ETH_SENTINEL, block=block)
    return eth_per_share_wei(price_d18) / 1e18


def wsteth_to_eth(w3: Web3, wsteth_amount: float, block: int | str) -> float:
    """Convert wstETH → stETH≈ETH via getStETHByWstETH at block."""
    if wsteth_amount <= 0:
        return 0.0
    wei = int(wsteth_amount * 1e18)
    (steth_wei,) = eth_call(
        w3,
        WSTETH,
        "getStETHByWstETH(uint256)",
        ["uint256"],
        [wei],
        ["uint256"],
        block=block,
    )
    return int(steth_wei) / 1e18


def assets_to_eth(
    w3: Web3, *, asset: str, amount: float, block: int | str
) -> float:
    if asset in ("ETH", "WETH"):
        return amount
    if asset == "wstETH":
        return wsteth_to_eth(w3, amount, block)
    raise ValueError(f"unsupported asset {asset}")


def _get_logs_chunked(
    w3: Web3,
    *,
    address: str,
    topic: str,
    from_block: int,
    to_block: int,
    chunk: int = 2000,
) -> list:
    out: list = []
    a = from_block
    cur_chunk = chunk
    while a <= to_block:
        b = min(a + cur_chunk - 1, to_block)

        def _run(fb=a, tb=b, addr=address, top=topic):
            return w3.eth.get_logs(
                {
                    "fromBlock": fb,
                    "toBlock": tb,
                    "address": to_checksum_address(addr),
                    "topics": [top],
                }
            )

        try:
            logs = retry_call(_run, retries=6, base_sleep=1.0)
            out.extend(logs)
            a = b + 1
            time.sleep(0.05)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if cur_chunk > 400 and (
                "400" in msg or "Too Many" in msg or "429" in msg or "crashed" in msg
            ):
                cur_chunk = max(400, cur_chunk // 2)
                time.sleep(1.5)
                continue
            # skip stubborn window
            a = b + 1
            time.sleep(0.5)
    return out


def _block_ts_getter(w3: Web3):
    cache: dict[int, int] = {}

    def get(bn: int) -> int:
        if bn not in cache:
            cache[bn] = int(w3.eth.get_block(bn)["timestamp"])
        return cache[bn]

    return get


def discover_queues_from_vault(
    w3: Web3, *, from_block: int, to_block: int | None = None, vault: str = VAULT
) -> list[dict[str, Any]]:
    tip = int(w3.eth.block_number) if to_block is None else to_block
    logs = _get_logs_chunked(
        w3,
        address=vault,
        topic=QUEUE_CREATED_TOPIC,
        from_block=from_block,
        to_block=tip,
        chunk=3000,
    )
    rows = []
    for lg in logs:
        queue = _addr_from_topic(lg["topics"][1])
        asset = _addr_from_topic(lg["topics"][2])
        is_deposit = bool(int.from_bytes(lg["data"][-32:], "big"))
        asset_label = {
            ETH_SENTINEL.lower(): "ETH",
            WETH.lower(): "WETH",
            WSTETH.lower(): "wstETH",
        }.get(asset.lower(), asset)
        rows.append(
            {
                "queue": queue,
                "asset": asset,
                "asset_label": asset_label,
                "is_deposit": is_deposit,
                "block": int(lg["blockNumber"]),
                "tx": lg["transactionHash"].hex(),
            }
        )
    return rows


def fetch_queue_events(
    w3: Web3,
    *,
    from_block: int,
    to_block: int | None = None,
    eth_only_deposits: bool = False,
) -> tuple[list[QueueEvent], list[QueueEvent], list[QueueEvent], list[QueueEvent]]:
    tip = int(w3.eth.block_number) if to_block is None else to_block
    get_ts = _block_ts_getter(w3)

    dep_queues: list[tuple[str, str]] = [(q, "ETH") for q in ETH_DEPOSIT_QUEUES]
    if not eth_only_deposits:
        dep_queues += [(q, "WETH") for q in WETH_DEPOSIT_QUEUES]
        dep_queues += [(q, "wstETH") for q in WSTETH_DEPOSIT_QUEUES]

    dep_reqs: list[QueueEvent] = []
    dep_claims: list[QueueEvent] = []
    for queue, asset in dep_queues:
        for lg in _get_logs_chunked(
            w3,
            address=queue,
            topic=DEP_REQ_TOPIC,
            from_block=from_block,
            to_block=tip,
        ):
            # DepositRequested(account, referral, assets, timestamp)
            owner = _addr_from_topic(lg["topics"][1])
            referral = (
                _addr_from_topic(lg["topics"][2]) if len(lg["topics"]) > 2 else None
            )
            assets_u, req_ts = decode(["uint224", "uint32"], bytes(lg["data"]))
            bn = int(lg["blockNumber"])
            dep_reqs.append(
                QueueEvent(
                    kind="dep_req",
                    queue=queue,
                    asset=asset,
                    block=bn,
                    timestamp=get_ts(bn),
                    tx_hash=lg["transactionHash"].hex(),
                    log_index=int(lg["logIndex"]),
                    owner=owner,
                    amount=int(assets_u) / 1e18,
                    request_ts=int(req_ts),
                    referral=referral,
                )
            )
        for lg in _get_logs_chunked(
            w3,
            address=queue,
            topic=DEP_CLAIM_TOPIC,
            from_block=from_block,
            to_block=tip,
        ):
            owner = _addr_from_topic(lg["topics"][1])
            shares, req_ts = decode(["uint256", "uint32"], bytes(lg["data"]))
            bn = int(lg["blockNumber"])
            dep_claims.append(
                QueueEvent(
                    kind="dep_claim",
                    queue=queue,
                    asset=asset,
                    block=bn,
                    timestamp=get_ts(bn),
                    tx_hash=lg["transactionHash"].hex(),
                    log_index=int(lg["logIndex"]),
                    owner=owner,
                    amount=int(shares) / 1e18,
                    request_ts=int(req_ts),
                )
            )

    red_reqs: list[QueueEvent] = []
    red_claims: list[QueueEvent] = []
    rq = REDEEM_QUEUE_WSTETH
    for lg in _get_logs_chunked(
        w3, address=rq, topic=RED_REQ_TOPIC, from_block=from_block, to_block=tip
    ):
        owner = _addr_from_topic(lg["topics"][1])
        shares, req_ts = decode(["uint256", "uint256"], bytes(lg["data"]))
        bn = int(lg["blockNumber"])
        red_reqs.append(
            QueueEvent(
                kind="red_req",
                queue=rq,
                asset="wstETH",
                block=bn,
                timestamp=get_ts(bn),
                tx_hash=lg["transactionHash"].hex(),
                log_index=int(lg["logIndex"]),
                owner=owner,
                amount=int(shares) / 1e18,
                request_ts=int(req_ts),
            )
        )
    for lg in _get_logs_chunked(
        w3, address=rq, topic=RED_CLAIM_TOPIC, from_block=from_block, to_block=tip
    ):
        # RedeemRequestClaimed(account, receiver, assets, timestamp)
        owner = _addr_from_topic(lg["topics"][1])
        receiver = (
            _addr_from_topic(lg["topics"][2]) if len(lg["topics"]) > 2 else None
        )
        if len(lg["topics"]) >= 3:
            assets, req_ts = decode(["uint256", "uint32"], bytes(lg["data"]))
        else:
            receiver_d, assets, req_ts = decode(
                ["address", "uint256", "uint32"], bytes(lg["data"])
            )
            receiver = to_checksum_address(receiver_d)
        bn = int(lg["blockNumber"])
        red_claims.append(
            QueueEvent(
                kind="red_claim",
                queue=rq,
                asset="wstETH",
                block=bn,
                timestamp=get_ts(bn),
                tx_hash=lg["transactionHash"].hex(),
                log_index=int(lg["logIndex"]),
                owner=owner,
                amount=int(assets) / 1e18,
                request_ts=int(req_ts),
                receiver=receiver,
            )
        )

    for xs in (dep_reqs, dep_claims, red_reqs, red_claims):
        xs.sort(key=lambda e: (e.block, e.log_index))
    return dep_reqs, dep_claims, red_reqs, red_claims


def _pair_deposit_claims(
    dep_reqs: list[QueueEvent], dep_claims: list[QueueEvent]
) -> list[dict[str, Any]]:
    """Join deposit request (assets) with claim (shares) by owner+request_ts."""
    req_index: dict[tuple[str, int], list[QueueEvent]] = {}
    for r in dep_reqs:
        req_index.setdefault((r.owner.lower(), r.request_ts), []).append(r)

    paired: list[dict[str, Any]] = []
    for c in dep_claims:
        key = (c.owner.lower(), c.request_ts)
        cands = req_index.get(key) or []
        if not cands:
            continue
        r = cands.pop(0)
        paired.append(
            {
                "owner": c.owner,
                "asset": r.asset,
                "assets_in_raw": r.amount,
                "shares": c.amount,
                "request_ts": c.request_ts,
                "dep_req": r,
                "dep_claim": c,
            }
        )
    return paired


def match_clean_full_round_trips(
    dep_reqs: list[QueueEvent],
    dep_claims: list[QueueEvent],
    red_reqs: list[QueueEvent],
    red_claims: list[QueueEvent],
    *,
    min_days: float = 0.01,
    share_tol: float = 1e-9,
) -> list[dict[str, Any]]:
    """One deposit claim → one full redeem (same shares) → one redeem claim."""
    paired = _pair_deposit_claims(dep_reqs, dep_claims)

    by_owner_deps: dict[str, list[dict[str, Any]]] = {}
    for p in paired:
        by_owner_deps.setdefault(p["owner"].lower(), []).append(p)

    by_owner_red_req: dict[str, list[QueueEvent]] = {}
    for r in red_reqs:
        by_owner_red_req.setdefault(r.owner.lower(), []).append(r)

    by_owner_red_claim: dict[str, list[QueueEvent]] = {}
    for c in red_claims:
        by_owner_red_claim.setdefault(c.owner.lower(), []).append(c)

    legs: list[dict[str, Any]] = []
    for owner, deps in by_owner_deps.items():
        if len(deps) != 1:
            continue
        dep = deps[0]
        rreqs = by_owner_red_req.get(owner) or []
        rclaims = by_owner_red_claim.get(owner) or []
        if len(rreqs) != 1 or len(rclaims) != 1:
            continue
        rr, rc = rreqs[0], rclaims[0]
        if abs(rr.amount - dep["shares"]) > share_tol:
            continue
        # redeem claim should match request timestamp
        if rc.request_ts != rr.request_ts and abs(rc.request_ts - rr.request_ts) > 0:
            # still allow if only one each
            pass
        if rr.block < dep["dep_claim"].block:
            continue
        if rc.block < rr.block:
            continue
        days = (rc.timestamp - dep["dep_claim"].timestamp) / 86400.0
        if days < min_days:
            continue
        assets_out_raw = rc.amount  # wstETH
        assets_in_raw = dep["assets_in_raw"]
        legs.append(
            {
                "owner": dep["owner"],
                "deposit_asset": dep["asset"],
                "deposit_request_tx": dep["dep_req"].tx_hash,
                "deposit_claim_tx": dep["dep_claim"].tx_hash,
                "redeem_tx": rr.tx_hash,
                "withdraw_claim_tx": rc.tx_hash,
                "deposit_block": dep["dep_claim"].block,
                "withdraw_block": rc.block,
                "deposit_ts": dep["dep_claim"].timestamp,
                "withdraw_ts": rc.timestamp,
                "days": days,
                "shares": dep["shares"],
                "assets_in_raw": assets_in_raw,
                "assets_out_raw": assets_out_raw,
                "assets_out_asset": "wstETH",
                "sample": "clean_full",
            }
        )
    legs.sort(key=lambda x: -x["days"])
    return legs


def enrich_legs_with_share_path(
    w3: Web3,
    legs: list[dict[str, Any]],
    *,
    redeem_fee: float = REDEEM_FEE,
    oracle: str = ORACLE,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for leg in legs:
        eth_in = assets_to_eth(
            w3,
            asset=leg["deposit_asset"],
            amount=float(leg["assets_in_raw"]),
            block=leg["deposit_block"],
        )
        eth_out = assets_to_eth(
            w3,
            asset="wstETH",
            amount=float(leg["assets_out_raw"]),
            block=leg["withdraw_block"],
        )
        p0 = eth_per_share(w3, leg["deposit_block"], oracle=oracle)
        p1 = eth_per_share(w3, leg["withdraw_block"], oracle=oracle)
        tx_ret = eth_out / eth_in - 1.0 if eth_in > 0 else float("nan")
        share_hold = p1 / p0 - 1.0 if p0 > 0 else float("nan")
        share_exit = p1 / p0 * (1.0 - redeem_fee) - 1.0 if p0 > 0 else float("nan")
        days = float(leg["days"])
        tx_apy = annualize_apy(tx_ret, days) if days > 0 else None
        share_apy_hold = annualize_apy(share_hold, days) if days > 0 else None
        share_apy_exit = annualize_apy(share_exit, days) if days > 0 else None
        gap = (tx_ret - share_exit) * 100.0
        gap_apy = None
        if tx_apy is not None and share_apy_exit is not None:
            gap_apy = (tx_apy - share_apy_exit) * 100.0
        row = {
            **leg,
            "assets_in": eth_in,
            "assets_out": eth_out,
            "tx_return": tx_ret,
            "tx_apy": tx_apy,
            "p0": p0,
            "p1": p1,
            "share_return_hold": share_hold,
            "share_return_after_exit": share_exit,
            "share_apy_hold": share_apy_hold,
            "share_apy_after_exit": share_apy_exit,
            "gap_return_pp": gap,
            "gap_apy_pp": gap_apy,
            "redeem_fee": redeem_fee,
        }
        out.append(row)
        time.sleep(0.02)
    return out


def round_trip_to_row(leg: dict[str, Any]) -> dict[str, Any]:
    def iso(ts: int) -> str:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

    return {
        "owner": leg["owner"],
        "deposit_asset": leg.get("deposit_asset"),
        "deposit_request_tx": leg.get("deposit_request_tx"),
        "deposit_claim_tx": leg.get("deposit_claim_tx"),
        "redeem_tx": leg.get("redeem_tx"),
        "withdraw_claim_tx": leg.get("withdraw_claim_tx"),
        "deposit_block": leg["deposit_block"],
        "withdraw_block": leg["withdraw_block"],
        "deposit_ts": leg["deposit_ts"],
        "withdraw_ts": leg["withdraw_ts"],
        "deposit_date": iso(int(leg["deposit_ts"])),
        "withdraw_date": iso(int(leg["withdraw_ts"])),
        "days": leg["days"],
        "shares": leg["shares"],
        "assets_in": leg.get("assets_in"),
        "assets_out": leg.get("assets_out"),
        "assets_in_raw": leg.get("assets_in_raw"),
        "assets_out_raw": leg.get("assets_out_raw"),
        "tx_return": leg.get("tx_return"),
        "tx_apy": leg.get("tx_apy"),
        "p0": leg.get("p0"),
        "p1": leg.get("p1"),
        "share_return_hold": leg.get("share_return_hold"),
        "share_return_after_exit": leg.get("share_return_after_exit"),
        "share_apy_hold": leg.get("share_apy_hold"),
        "share_apy_after_exit": leg.get("share_apy_after_exit"),
        "gap_return_pp": leg.get("gap_return_pp"),
        "gap_apy_pp": leg.get("gap_apy_pp"),
        "sample": leg.get("sample", "clean_full"),
    }


def summarize_round_trips(legs: list[dict[str, Any]]) -> dict[str, Any]:
    import statistics

    gaps = [abs(float(r["gap_return_pp"])) for r in legs if r.get("gap_return_pp") is not None]
    gap_apys = [
        abs(float(r["gap_apy_pp"])) for r in legs if r.get("gap_apy_pp") is not None
    ]

    def pctile(xs: list[float], p: float) -> float | None:
        if not xs:
            return None
        xs = sorted(xs)
        i = min(len(xs) - 1, max(0, int(round((p / 100.0) * (len(xs) - 1)))))
        return xs[i]

    def bucket(pred):
        sub = [r for r in legs if pred(float(r["days"]))]
        g = [abs(float(r["gap_return_pp"])) for r in sub if r.get("gap_return_pp") is not None]
        apys = [float(r["tx_apy"]) * 100 for r in sub if r.get("tx_apy") is not None]
        return {
            "n": len(sub),
            "median_abs_gap_return_pp": statistics.median(g) if g else None,
            "median_tx_apy_pct": statistics.median(apys) if apys else None,
        }

    return {
        "n": len(legs),
        "sample": "clean_full",
        "sample_definition": (
            "one deposit request+claim → one full redeem (same shares) → "
            "one redeem claim; ETH-equivalent via wstETH→stETH"
        ),
        "redeem_fee": REDEEM_FEE,
        "abs_gap_return_pp": {
            "median": statistics.median(gaps) if gaps else None,
            "p90": pctile(gaps, 90),
            "max": max(gaps) if gaps else None,
        },
        "abs_gap_apy_pp": {
            "median": statistics.median(gap_apys) if gap_apys else None,
            "p90": pctile(gap_apys, 90),
            "max": max(gap_apys) if gap_apys else None,
        },
        "buckets": {
            "lt_7d": bucket(lambda d: d < 7),
            "d7_30": bucket(lambda d: 7 <= d < 30),
            "d30_90": bucket(lambda d: 30 <= d < 90),
            "ge_90d": bucket(lambda d: d >= 90),
        },
    }
