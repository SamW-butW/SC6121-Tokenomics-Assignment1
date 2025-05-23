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

pool_slot0 = w3.eth.contract(address=POOL_ADDR, abi=SLOT0_ABI)

def get_sqrtPriceX96(block: int) -> int:
    sqX96, *_ = pool_slot0.functions.slot0().call(block_identifier=block)
    return sqX96

def get_price_usdc_per_weth(block: int) -> float:
    sqX96 = get_sqrtPriceX96(block)
    raw = sqX96 / 2**96
    price_raw = raw * raw
    return (1 / price_raw) * 1e12

def get_L_our(block:int) -> int:
    P0 = get_price_usdc_per_weth(block)
    print(f"P0 (USDC per WETH) at block {block}: {P0:.6f}")
    W0 = 50_000.0 / P0
    amount1 = int(W0 * 1e18)
    print(f"Initial WETH to deposit: {W0:.6f} WETH ({amount1} wei)")
    sqrtP0 = get_sqrtPriceX96(block)
    print(f"sqrtPriceX96 at block {block}: {sqrtP0}")
    raw_sqrtP0 = sqrtP0 / 2**96
    print(f"raw_sqrtP0 (√(res1/res0)) : {raw_sqrtP0:.6e}")
    sqrtL = int((1.0001**(200540/2)) * 2**96)
    raw_sqrtL = sqrtL / 2**96
    print(f"sqrtLowerX96 (tick 200540): {sqrtL}, raw_sqrtLower: {raw_sqrtL:.6e}")
    L = amount1 * 2**96 // (sqrtP0 - sqrtL)
    print(f"Calculated L_our (int): {L}")
    print(f"Calculated L_our (scientific): {L:.6e}")
    return L

def get_position_amounts(L: int, block:int, lower:int, upper:int):
    sqrtP = get_sqrtPriceX96(block)
    raw_sqrtP = sqrtP / 2**96
    sqrtL  = int((1.0001**(lower/2)) * 2**96)
    sqrtU  = int((1.0001**(upper/2)) * 2**96)
    raw_sqrtL = sqrtL / 2**96
    raw_sqrtU = sqrtU / 2**96
    print(f"\nsqrtPriceX96 at block {block}: {sqrtP}, raw_sqrtP: {raw_sqrtP:.6e}")
    print(f"sqrtLowerX96: {sqrtL}, raw_sqrtLower: {raw_sqrtL:.6e}")
    print(f"sqrtUpperX96: {sqrtU}, raw_sqrtUpper: {raw_sqrtU:.6e}")
    amount1 = L * (sqrtP - sqrtL) // (2**96)
    num     = L * (sqrtU - sqrtP) * (2**96)
    denom   = sqrtP * sqrtU
    amount0 = num // denom
    print(f"Raw amount1 (WETH wei): {amount1}")
    print(f"Raw amount0 (USDC units): {amount0}")
    return amount0, amount1

if __name__ == "__main__":
    BLOCK0 = 17618642
    BLOCK1 = 17618742
    LOWER, UPPER = 200540, 200560

    # 计算并打印 L_our
    L_our = get_L_our(BLOCK0)

    # 取出头寸并打印
    a0, a1 = get_position_amounts(L_our, BLOCK1, LOWER, UPPER)
    amount0_usdc = a0 / 1e6
    amount1_weth = a1 / 1e18
    print(f"\nPosition at block {BLOCK1}: {amount0_usdc:.6f} USDC, {amount1_weth:.6f} WETH")

    # HODL vs LP
    P1 = get_price_usdc_per_weth(BLOCK1)
    print(f"P1 (USDC per WETH) at block {BLOCK1}: {P1:.6f}")
    W0 = 50_000.0 / get_price_usdc_per_weth(BLOCK0)
    hodl_val = 50_000.0 + W0 * P1
    lp_val   = amount0_usdc + amount1_weth * P1
    print(f"HODL value: {hodl_val:.2f} USDC")
    print(f"LP   value: {lp_val:.2f} USDC")
    print(f"Impermanent Loss: {hodl_val - lp_val:.2f} USDC")
