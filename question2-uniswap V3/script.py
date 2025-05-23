from web3 import Web3
import math

RPC_URL = "https://eth-mainnet.g.alchemy.com/v2/R8R1RiTNWjf95C2-ZnRsYyoP11ysBLwa"
w3 = Web3(Web3.HTTPProvider(RPC_URL))
POOL_ADDR = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"

TICKS_ABI = [{
    "inputs":[{"internalType":"int24","name":"tick","type":"int24"}],
    "name":"ticks",
    "outputs":[
        {"internalType":"uint128","name":"liquidityGross","type":"uint128"},
        {"internalType":"int128","name":"liquidityNet","type":"int128"}
    ],
    "stateMutability":"view","type":"function"
}]
SLOT0_ABI = [{
    "inputs": [], "name": "slot0",
    "outputs": [
        {"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},
        {"internalType":"int24","name":"tick","type":"int24"},
        {"internalType":"uint16","name":"observationIndex","type":"uint16"},
        {"internalType":"uint16","name":"observationCardinality","type":"uint16"},
        {"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},
        {"internalType":"uint8","name":"feeProtocol","type":"uint8"},
        {"internalType":"bool","name":"unlocked","type":"bool"}
    ],
    "stateMutability":"view","type":"function"
}]

pool_ticks = w3.eth.contract(address=POOL_ADDR, abi=TICKS_ABI)
pool_slot0 = w3.eth.contract(address=POOL_ADDR, abi=SLOT0_ABI)

def fetch_tick_liquidity(start_tick:int, end_tick:int, block:int):
    data = {}
    for tick in range(start_tick, end_tick+1):
        lg, _ = pool_ticks.functions.ticks(tick).call(block_identifier=block)
        data[tick] = lg
    return data

def get_price_usdc_per_weth(block:int) -> float:
    # 1) 读 on-chain sqrtPriceX96
    sqrtPriceX96, *_ = pool_slot0.functions.slot0().call(block_identifier=block)
    # 2) Q64.96 转浮点 raw_sqrtP = sqrt(reserve1/reserve0)
    raw_sqrtP = sqrtPriceX96 / 2**96
    # 3) price_raw = WETH per USDC
    price_raw = raw_sqrtP**2
    # 4) 倒数并调精度（18-6）
    return (1 / price_raw) * 1e12

if __name__ == "__main__":
    START_TICK, END_TICK = 200530, 200580
    BLOCK = 17618642
    LOWER, UPPER = 200540, 200560

    # 全局流动性
    ticks_liq = fetch_tick_liquidity(START_TICK, END_TICK, BLOCK)
    print("=== Global tick liquidity ===")
    for t, liq in ticks_liq.items():
        print(f"Tick {t}: {liq}")

    # 计算价格和 WETH 数量
    P = get_price_usdc_per_weth(BLOCK)
    print(f"\nPrice P (USDC per WETH): {P:.6f}")
    usdc_amt = 50_000.0
    weth_amt = usdc_amt / P
    amount1 = int(weth_amt * 1e18)  # WETH → wei
    print(f"WETH to pair 50k USDC: {weth_amt:.6f} (~{amount1} wei)")

    # 计算 raw_sqrtP 和 raw_sqrtLower（Q64.96）
    sqrtPriceX96, *_ = pool_slot0.functions.slot0().call(block_identifier=BLOCK)
    raw_sqrtP = sqrtPriceX96 / 2**96
    raw_sqrtLower = 1.0001 ** (LOWER / 2)
    sqrtLowerX96 = int(raw_sqrtLower * 2**96)

    print(f"\nraw_sqrtP: {raw_sqrtP:.6e}")
    print(f"raw_sqrtLower: {raw_sqrtLower:.6e}")

    # 计算 L_our
    # amount1 = L * (raw_sqrtP - raw_sqrtLower)
    # → L = amount1 / (raw_sqrtP - raw_sqrtLower)
    L_our = amount1 / (raw_sqrtP - raw_sqrtLower)
    print(f"\nCalculated liquidity L_our (float): {L_our:.6e}")
    # 如果需要整数形式 (uint128)
    L_our_int = int(L_our)
    print(f"L_our as int: {L_our_int}")






initial = 100000.0
pnl     = lp_value + fees_value - initial
print(f"→ Portfolio PnL:      {pnl:.2f} USDC")
