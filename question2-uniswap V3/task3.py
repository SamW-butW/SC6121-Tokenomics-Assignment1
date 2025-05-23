from web3 import Web3
import math
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ─── 配置 ────────────────────────────────────────────────────────
RPC_URL      = "https://eth-mainnet.g.alchemy.com/v2/R8R1RiTNWjf95C2-ZnRsYyoP11ysBLwa"
POOL_ADDR    = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
START_BLOCK  = 17618642
END_BLOCK    = 17618742
START_TICK   = 200530
END_TICK     = 200580
TICK_LOWER   = 200540
TICK_UPPER   = 200560
FEE_RATE     = 0.003  # 0.3%

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# ─── ABI ─────────────────────────────────────────────────────────
TICKS_ABI = [{
    "inputs":[{"internalType":"int24","name":"tick","type":"int24"}],
    "name":"ticks","outputs":[
      {"internalType":"uint128","name":"liquidityGross","type":"uint128"},
      {"internalType":"int128","name":"liquidityNet","type":"int128"}],
    "stateMutability":"view","type":"function"}]

SLOT0_ABI =[{
    "inputs": [], "name": "slot0", "outputs":[
      {"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},
      {"internalType":"int24","name":"tick","type":"int24"},
      {"internalType":"uint16","name":"observationIndex","type":"uint16"},
      {"internalType":"uint16","name":"observationCardinality","type":"uint16"},
      {"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},
      {"internalType":"uint8","name":"feeProtocol","type":"uint8"},
      {"internalType":"bool","name":"unlocked","type":"bool"}],
    "stateMutability":"view","type":"function"}]

SWAP_ABI = [{
    "anonymous": False,
    "inputs": [
      {"indexed":True,  "internalType":"address","name":"sender","type":"address"},
      {"indexed":True,  "internalType":"address","name":"recipient","type":"address"},
      {"indexed":False, "internalType":"int256",  "name":"amount0","type":"int256"},
      {"indexed":False, "internalType":"int256",  "name":"amount1","type":"int256"},
      {"indexed":False, "internalType":"uint160", "name":"sqrtPriceX96","type":"uint160"},
      {"indexed":False, "internalType":"uint128", "name":"liquidity","type":"uint128"},
      {"indexed":False, "internalType":"int24",   "name":"tick","type":"int24"}],
    "name":"Swap","type":"event"}]

pool_ticks = w3.eth.contract(address=POOL_ADDR, abi=TICKS_ABI)
pool_slot0 = w3.eth.contract(address=POOL_ADDR, abi=SLOT0_ABI)
pool_swap  = w3.eth.contract(address=POOL_ADDR, abi=SWAP_ABI)

# ─── 辅助函数 ─────────────────────────────────────────────────────

def fetch_tick_liquidity(block: int):
    data = {}
    for t in range(START_TICK, END_TICK+1):
        lg, _ = pool_ticks.functions.ticks(t).call(block_identifier=block)
        data[t] = lg
    return data

def get_sqrtPriceX96(block: int) -> int:
    return pool_slot0.functions.slot0().call(block_identifier=block)[0]

def get_price_usdc_per_weth(block: int) -> float:
    sqX96 = get_sqrtPriceX96(block)
    raw   = sqX96 / 2**96
    price_raw = raw * raw
    return (1 / price_raw) * 1e12

def compute_L_our(block: int) -> int:
    P0       = get_price_usdc_per_weth(block)
    weth_amt = 50_000.0 / P0
    amount1  = int(weth_amt * 1e18)
    sqrtP0   = get_sqrtPriceX96(block)
    sqrtL    = int((1.0001**(TICK_LOWER/2)) * 2**96)
    return amount1 * 2**96 // (sqrtP0 - sqrtL)

def raw_sqrt_to_tick(raw_sqrt: float) -> int:
    return int(math.log(raw_sqrt*raw_sqrt) / math.log(1.0001))

# ─── 主流程：Task 3 ─────────────────────────────────────────────────

# 1) 全局 & 头寸流动性 & 权重
global_liq = fetch_tick_liquidity(START_BLOCK)
L_our      = compute_L_our(START_BLOCK)
our_liq    = {t: (L_our if TICK_LOWER <= t <= TICK_UPPER else 0) for t in global_liq}
weight     = {t: (our_liq[t]/global_liq[t]) if global_liq[t] > 0 else 0 for t in global_liq}

# 2) 拉日志：正确签名
swap_sig    = "Swap(address,address,int256,int256,uint160,uint128,int24)"
event_topic = w3.keccak(text=swap_sig).hex()

logs = w3.eth.get_logs({
    "fromBlock": START_BLOCK,
    "toBlock":   END_BLOCK,
    "address":   POOL_ADDR,
    "topics":    [event_topic]
})
print("🔍 raw logs count:", len(logs))

# 3) 解码：用 process_log
events = [pool_swap.events.Swap.process_log(lg) for lg in logs]
print("✅ decoded swap events count:", len(events))

# 4) 累计平均分配手续费
fee0 = {t: 0 for t in global_liq}  # USDC fees (raw)
fee1 = {t: 0 for t in global_liq}  # WETH fees (raw)

for ev in events:
    args = ev["args"]
    blk  = ev["blockNumber"]
    pre_raw   = get_sqrtPriceX96(blk-1) / 2**96
    post_raw  = args["sqrtPriceX96"] / 2**96
    pre_tick  = raw_sqrt_to_tick(pre_raw)
    post_tick = raw_sqrt_to_tick(post_raw)
    low, high = sorted((pre_tick, post_tick))
    crossed   = [t for t in range(low, high+1) if START_TICK <= t <= END_TICK]
    if not crossed: continue

    f0   = abs(args["amount0"]) * FEE_RATE
    f1   = abs(args["amount1"]) * FEE_RATE
    per0 = f0 / len(crossed)
    per1 = f1 / len(crossed)

    for t in crossed:
        fee0[t] += per0 * weight[t]
        fee1[t] += per1 * weight[t]

# 5) 分别作图
ticks = list(global_liq.keys())

# USDC 图（Raw → USDC 单位）
usdc_vals = [fee0[t] / 1e6 for t in ticks]
plt.figure(figsize=(8,4))
plt.plot(ticks, usdc_vals, linestyle='-', linewidth=2)           # 去掉 marker
plt.xlabel("Tick Number")
plt.ylabel("Accumulated USDC Fees")
plt.title(f"USDC Fee per Tick (Blocks {START_BLOCK}–{END_BLOCK})")
plt.gca().yaxis.set_major_formatter(
    ticker.FuncFormatter(lambda x, _: f"{x:,.2f}")
)
plt.tight_layout()
plt.show()

# WETH 图（Raw → WETH 单位）
weth_vals = [fee1[t] / 1e18 for t in ticks]
plt.figure(figsize=(8,4))
plt.plot(ticks, weth_vals, color='orange', linestyle='-', linewidth=2)  # 同样去掉 marker
plt.xlabel("Tick Number")
plt.ylabel("Accumulated WETH Fees")
plt.title(f"WETH Fee per Tick (Blocks {START_BLOCK}–{END_BLOCK})")
plt.gca().yaxis.set_major_formatter(
    ticker.FuncFormatter(lambda x, _: f"{x:,.6f}")
)
plt.tight_layout()
plt.show()


total_weth_fee = sum(fee1.values()) / 1e18
print(f"Total WETH fee earned: {total_weth_fee:.6f} WETH")
print(f"Max WETH fee on a single tick: {max(fee1.values()) / 1e18:.6f} WETH")