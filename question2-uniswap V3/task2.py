import pandas as pd
import matplotlib.pyplot as plt

# 从之前脚本输出中抄入数据
ticks = list(range(200530, 200581))
global_liq = [
    8151361812842047647, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    129145973139416183, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    8174698218376832778, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    631520865104068728, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    92961962089749322, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    8840534690793920
]

# 你头寸在 200540–200560 tick 区间内的流动性
L_our = 2202082411454851840
our_liq = [L_our if 200540 <= t <= 200560 else 0 for t in ticks]

# 构造 DataFrame
df = pd.DataFrame({
    'tick': ticks,
    'global_liquidity': global_liq,
    'our_liquidity': our_liq
})

# 画图
plt.figure()
plt.plot(df['tick'], df['global_liquidity'], label='Total Pool Liquidity')
plt.plot(df['tick'], df['our_liquidity'], label='Our Position Liquidity')
plt.xlabel('Tick')
plt.ylabel('Liquidity')
plt.title('Liquidity Distribution @ Block 17618642')
plt.legend()
plt.show()
