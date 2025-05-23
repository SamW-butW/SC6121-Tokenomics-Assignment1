def get_amount_out(amount_in: int, reserve_in: int, reserve_out: int, fee: float) -> int:
    fee_numerator = int((1 - fee) * 1000)
    fee_denominator = 1000
    amount_in_with_fee = amount_in * fee_numerator
    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in * fee_denominator + amount_in_with_fee
    return numerator // denominator

def main():
    print("=== Uniswap V2 Swap Simulation ===\n")
    amount_in = int(input("1) Enter amount_in (raw units): "))
    token_in  = input("2) Enter token_in symbol: ")
    token0    = input("3) Enter symbol of token0: ")
    token1    = input("4) Enter symbol of token1: ")
    reserve0  = int(input(f"5) Enter reserve0 for {token0}: "))
    reserve1  = int(input(f"6) Enter reserve1 for {token1}: "))
    fee       = float(input("7) Enter fee rate (e.g. 0.003): "))

    if token_in == token0:
        reserve_in, reserve_out = reserve0, reserve1
        token_out = token1
    elif token_in == token1:
        reserve_in, reserve_out = reserve1, reserve0
        token_out = token0
    else:
        print(f"Error: token_in ({token_in}) must be {token0} or {token1}.")
        return

    amount_out = get_amount_out(amount_in, reserve_in, reserve_out, fee)
    print(f"\nSimulation result: Output {token_out} = {amount_out}")

if __name__ == "__main__":
    main()
