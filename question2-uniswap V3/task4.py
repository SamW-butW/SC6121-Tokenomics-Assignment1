from web3 import Web3
import math
import pandas as pd

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
    d={}
    for t in range(START_TICK, END_TICK+1):
        lg,_ = pool_ticks.functions.ticks(t).call(block_identifier=block)
        d[t]=lg
    return d

def get_sqrtPriceX96(block:int)->int:
    return pool_slot0.functions.slot0().call(block_identifier=block)[0]

def get_price_usdc_per_weth(block:int)->float:
    s = get_sqrtPriceX96(block)/2**96
    return (1/(s*s))*1e12

def compute_L_our(block:int)->int:
    P0 = get_price_usdc_per_weth(block)
    weth_amt = 50000.0/P0
    amt1 = int(weth_amt*1e18)
    sqrtP0 = get_sqrtPriceX96(block)
    sqrtL  = int((1.0001**(TICK_LOWER/2))*2**96)
    return amt1*2**96//(sqrtP0-sqrtL)

def raw_sqrt_to_tick(r:float)->int:
    return int(math.log(r*r)/math.log(1.0001))

def get_position_amounts(L:int, block:int, lower:int, upper:int):
    sqrtP = get_sqrtPriceX96(block)
    sqrtL = int((1.0001**(lower/2))*2**96)
    sqrtU = int((1.0001**(upper/2))*2**96)
    # WETH raw
    amt1 = L*(sqrtP-sqrtL)//(2**96)
    # USDC raw
    num = L*(sqrtU-sqrtP)*(2**96)
    den = sqrtP*sqrtU
    amt0 = num//den
    return amt0, amt1

# ─── 主流程 ──────────────────────────────────────────────────────

# 1) 全局 & 权重
global_liq = fetch_tick_liquidity(START_BLOCK)
L_our      = compute_L_our(START_BLOCK)
our_liq    = {t:(L_our if TICK_LOWER<=t<=TICK_UPPER else 0) for t in global_liq}
weight     = {t:our_liq[t]/global_liq[t] if global_liq[t]>0 else 0 for t in global_liq}

# 2) 拉 Swap 日志
topic = w3.keccak(text="Swap(address,address,int256,int256,uint160,uint128,int24)").hex()
logs  = w3.eth.get_logs({
    "fromBlock":START_BLOCK,"toBlock":END_BLOCK,
    "address":POOL_ADDR,"topics":[topic]
})
events = [pool_swap.events.Swap.process_log(lg) for lg in logs]

# 3) 累计手续费分配
fee0={t:0 for t in global_liq}
fee1={t:0 for t in global_liq}
for ev in events:
    a0, a1 = abs(ev["args"]["amount0"]), abs(ev["args"]["amount1"])
    pre = get_sqrtPriceX96(ev["blockNumber"]-1)/2**96
    post= ev["args"]["sqrtPriceX96"]/2**96
    t0, t1 = sorted((raw_sqrt_to_tick(pre), raw_sqrt_to_tick(post)))
    crossed=[t for t in range(t0,t1+1) if START_TICK<=t<=END_TICK]
    if not crossed: continue
    tot0, tot1 = a0*FEE_RATE, a1*FEE_RATE
    per0,per1 = tot0/len(crossed), tot1/len(crossed)
    for t in crossed:
        fee0[t]+= per0*weight[t]
        fee1[t]+= per1*weight[t]

# 4) 计算 Task4

# 4.1 我们赚到的手续费
total_fee_usdc = sum(fee0.values())/1e6
total_fee_weth = sum(fee1.values())/1e18

# 4.2 头寸末值（Task1 中逻辑）
a0_raw, a1_raw = get_position_amounts(L_our, END_BLOCK, TICK_LOWER, TICK_UPPER)
amount0_usdc = a0_raw/1e6
amount1_weth = a1_raw/1e18

# 4.3 最终价值与 PnL
P1 = get_price_usdc_per_weth(END_BLOCK)
lp_value = amount0_usdc + amount1_weth*P1
fees_value = total_fee_usdc + total_fee_weth*P1
initial   = 100000.0
pnl       = lp_value + fees_value - initial

# —— 输出结果 —— 
print(f"Estimated fees earned: {total_fee_usdc:.4f} USDC, {total_fee_weth:.6f} WETH")
print(f"Position at block {END_BLOCK}: {amount0_usdc:.6f} USDC, {amount1_weth:.6f} WETH")
print(f"LP value (ex-cl fees): {lp_value:.2f} USDC")
print(f"Fees value:            {fees_value:.2f} USDC")
print(f"-> Portfolio PnL:      {pnl:.2f} USDC")
