from web3 import Web3

RPC_URL = "https://eth-mainnet.g.alchemy.com/v2/R8R1RiTNWjf95C2-ZnRsYyoP11ysBLwa"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

POOL_ADDR = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
POOL_ABI = [
    {
        "inputs":[{"internalType":"int24","name":"tick","type":"int24"}],
        "name":"ticks",
        "outputs":[
            {"internalType":"uint128","name":"liquidityGross","type":"uint128"},
            {"internalType":"int128","name":"liquidityNet","type":"int128"}
        ],
        "stateMutability":"view",
        "type":"function"
    }
]

pool = w3.eth.contract(address=POOL_ADDR, abi=POOL_ABI)

def fetch_tick_liquidity(start_tick: int, end_tick: int, block: int):
    result = {}
    for tick in range(start_tick, end_tick + 1):
        info = pool.functions.ticks(tick).call(block_identifier=block)
        result[tick] = info[0]
    return result

if __name__ == "__main__":
    START, END = 200530, 200580
    BLOCK = 17618642
    data = fetch_tick_liquidity(START, END, BLOCK)
    for t, liq in data.items():
        print(f"Tick {t}: {liq}")
