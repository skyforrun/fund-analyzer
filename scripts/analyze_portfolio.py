"""用户持仓基金量化评分分析脚本"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import date
import warnings
warnings.filterwarnings('ignore')

print("=" * 70)
print("        基金持仓量化评分分析报告")
print(f"        日期: {date.today()}")
print("=" * 70)

# 用户持有的基金
funds = {
    '016665': {'name': '天弘全球高端制造混合(QDII)C', 'amount': 6062.24, 'profit': 619.30, 'pct': 11.38},
    '021662': {'name': '国富亚洲机会股票(QDII)C', 'amount': 5135.38, 'profit': 135.38, 'pct': 2.71},
    '016742': {'name': '华安大中华升级股票(QDII)C', 'amount': 5073.84, 'profit': 73.84, 'pct': 1.48},
    '513310': {'name': '华泰柏瑞中韩半导体ETF(QDII)', 'amount': 313.76, 'profit': 13.76, 'pct': 4.59},
    '018036': {'name': '长城全球新能源汽车(QDII-LOF)C', 'amount': 3949.44, 'profit': -50.56, 'pct': -1.26},
    '018147': {'name': '建信新兴市场优选混合(QDII)C', 'amount': 5900.18, 'profit': -99.82, 'pct': -1.66},
}

# 获取净值数据
print("\n正在获取基金净值数据...")
nav_data = {}
for code, info in funds.items():
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator='单位净值走势')
        df.columns = ['date', 'nav', 'daily_return']
        df['date'] = pd.to_datetime(df['date'])
        df['nav'] = df['nav'].astype(float)
        df = df.sort_values('date').reset_index(drop=True)
        nav_data[code] = df
        print(f"  {info['name']}: {len(df)} 条净值记录")
    except Exception as e:
        print(f"  {info['name']}: 获取失败 - {e}")


def calc_metrics(df, windows=[20, 60, 120, 250]):
    """计算核心量化指标"""
    if df is None or len(df) < 20:
        return None

    navs = df['nav'].values
    returns = np.diff(navs) / navs[:-1]

    metrics = {}

    # 不同窗口的收益率
    for w in windows:
        if len(navs) >= w:
            ret = (navs[-1] / navs[-w] - 1) * 100
            metrics[f'return_{w}d'] = ret

    # 年化收益率
    if len(navs) >= 250:
        metrics['return_1y'] = (navs[-1] / navs[-250] - 1) * 100

    # 最大回撤
    peak = np.maximum.accumulate(navs)
    drawdown = (navs - peak) / peak
    metrics['max_drawdown'] = np.min(drawdown) * 100

    # 近60日最大回撤
    if len(navs) >= 60:
        recent_navs = navs[-60:]
        peak60 = np.maximum.accumulate(recent_navs)
        dd60 = (recent_navs - peak60) / peak60
        metrics['max_drawdown_60d'] = np.min(dd60) * 100

    # 波动率 (年化)
    if len(returns) >= 20:
        vol = np.std(returns[-min(250, len(returns)):]) * np.sqrt(250) * 100
        metrics['volatility'] = vol

    # 夏普比率 (无风险利率1.5%)
    rf = 0.015 / 250
    if len(returns) >= 60:
        excess_returns = returns[-min(250, len(returns)):] - rf
        if np.std(excess_returns) > 0:
            metrics['sharpe'] = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(250)

    # Calmar比率
    if 'return_1y' in metrics and metrics['max_drawdown'] < 0:
        metrics['calmar'] = metrics['return_1y'] / abs(metrics['max_drawdown'])

    # Sortino比率
    if len(returns) >= 60:
        downside = returns[returns < 0]
        if len(downside) > 0 and np.std(downside) > 0:
            metrics['sortino'] = (np.mean(returns[-min(250, len(returns)):]) - rf) / np.std(downside) * np.sqrt(250)

    # 动量得分 (多窗口加权)
    momentum_score = 0
    momentum_weights = {20: 0.4, 60: 0.35, 120: 0.25}
    for w, weight in momentum_weights.items():
        key = f'return_{w}d'
        if key in metrics:
            momentum_score += metrics[key] * weight
    metrics['momentum_score'] = momentum_score

    # 趋势强度
    if len(navs) >= 20:
        x = np.arange(min(60, len(navs)))
        y = navs[-min(60, len(navs)):]
        slope = np.polyfit(x, y, 1)[0]
        metrics['trend_slope'] = slope / navs[-1] * 100

    return metrics


def composite_score(m):
    """综合评分 (0-100)"""
    score = 50

    # 1. 收益因子 (±10)
    ret_score = 0
    if 'return_60d' in m:
        r60 = m['return_60d']
        if r60 > 10: ret_score += 10
        elif r60 > 5: ret_score += 7
        elif r60 > 0: ret_score += 4
        elif r60 > -5: ret_score += 1
    if 'return_120d' in m:
        r120 = m['return_120d']
        if r120 > 20: ret_score += 10
        elif r120 > 10: ret_score += 7
        elif r120 > 0: ret_score += 4
        elif r120 > -10: ret_score += 1
    score += ret_score - 10

    # 2. 风控因子
    if m['max_drawdown'] > -5: score += 8
    elif m['max_drawdown'] > -10: score += 5
    elif m['max_drawdown'] > -20: score += 2
    elif m['max_drawdown'] > -30: score -= 2
    else: score -= 5

    if 'max_drawdown_60d' in m:
        if m['max_drawdown_60d'] > -3: score += 5
        elif m['max_drawdown_60d'] > -5: score += 3
        elif m['max_drawdown_60d'] > -10: score += 1
        else: score -= 3

    # 3. 夏普/Sortino
    if 'sharpe' in m:
        s = m['sharpe']
        if s > 2: score += 10
        elif s > 1.5: score += 8
        elif s > 1: score += 6
        elif s > 0.5: score += 3
        elif s > 0: score += 1
        else: score -= 3

    if 'sortino' in m:
        s = m['sortino']
        if s > 3: score += 5
        elif s > 2: score += 3
        elif s > 1: score += 2
        elif s > 0: score += 1
        else: score -= 2

    # 4. 动量/趋势
    mom = m.get('momentum_score', 0)
    if mom > 15: score += 8
    elif mom > 10: score += 6
    elif mom > 5: score += 4
    elif mom > 0: score += 2
    elif mom > -5: score += 0
    else: score -= 3

    if 'trend_slope' in m:
        ts = m['trend_slope']
        if ts > 0.5: score += 5
        elif ts > 0.2: score += 3
        elif ts > 0: score += 1
        else: score -= 2

    # 波动率惩罚
    if 'volatility' in m:
        vol = m['volatility']
        if vol > 30: score -= 5
        elif vol > 25: score -= 3
        elif vol > 20: score -= 1

    return max(0, min(100, score))


def get_signal(score):
    if score >= 75:
        return 'BUY  (加仓)'
    elif score >= 60:
        return 'HOLD (持有)'
    elif score >= 45:
        return 'WEAK (观望)'
    else:
        return 'SELL (减仓)'


# 计算所有基金指标
print("\n" + "=" * 70)
print("                    量化指标汇总")
print("=" * 70)

all_metrics = {}
for code in funds:
    if code in nav_data:
        m = calc_metrics(nav_data[code])
        if m:
            all_metrics[code] = m

# 打印详细指标
for code, info in funds.items():
    if code not in all_metrics:
        continue
    m = all_metrics[code]
    print(f"\n{'─' * 60}")
    print(f"  {info['name']} ({code})")
    print(f"  持有金额: {info['amount']:.2f}  持有收益: {info['profit']:+.2f} ({info['pct']:+.2f}%)")
    print(f"{'─' * 60}")

    for key, label in [
        ('return_20d', '近20日收益'), ('return_60d', '近60日收益'),
        ('return_120d', '近120日收益'), ('return_1y', '近1年收益'),
    ]:
        if key in m:
            print(f"  {label}: {m[key]:+.2f}%")

    print(f"  历史最大回撤: {m['max_drawdown']:.2f}%")
    if 'max_drawdown_60d' in m:
        print(f"  近60日最大回撤: {m['max_drawdown_60d']:.2f}%")
    if 'volatility' in m:
        print(f"  年化波动率: {m['volatility']:.2f}%")
    if 'sharpe' in m:
        print(f"  夏普比率: {m['sharpe']:.2f}")
    if 'calmar' in m:
        print(f"  Calmar比率: {m['calmar']:.2f}")
    if 'sortino' in m:
        print(f"  Sortino比率: {m['sortino']:.2f}")
    print(f"  动量得分: {m['momentum_score']:.2f}")
    if 'trend_slope' in m:
        print(f"  趋势强度: {m['trend_slope']:.4f}")


# 综合评分
print("\n" + "=" * 70)
print("                    综合量化评分")
print("=" * 70)

results = []
for code, info in funds.items():
    if code not in all_metrics:
        continue
    m = all_metrics[code]
    score = composite_score(m)
    signal = get_signal(score)
    results.append((code, info, score, signal, m))

results.sort(key=lambda x: x[2], reverse=True)

print(f"\n  {'基金名称':<26} {'评分':>4}  {'信号':<14} {'动量':>6} {'夏普':>6} {'回撤':>8}")
print("  " + "─" * 76)
for code, info, score, signal, m in results:
    name = info['name'][:24]
    sharpe = f"{m.get('sharpe', 0):.2f}"
    mom = f"{m.get('momentum_score', 0):.1f}"
    dd = f"{m['max_drawdown']:.1f}%"
    print(f"  {name:<26} {score:>4}    {signal}  {mom:>6} {sharpe:>6} {dd:>8}")


# 操作建议
print("\n" + "=" * 70)
print("                    操作建议")
print("=" * 70)

for code, info, score, signal, m in results:
    name = info['name']
    profit_pct = info['pct']
    amount = info['amount']

    print(f"\n  [{score}分] {name}")

    if score >= 75:
        if profit_pct > 10:
            print(f"    -> 评分高 + 盈利{profit_pct:+.1f}% -> 可继续持有，但建议设止盈线(如+15%)")
        else:
            print(f"    -> 评分高，趋势向好 -> 可适当加仓")
    elif score >= 60:
        if profit_pct > 8:
            print(f"    -> 评分中等 + 盈利较大 -> 建议部分止盈(1/3~1/2)")
        elif profit_pct > 0:
            print(f"    -> 评分中等 -> 继续持有观察")
        else:
            print(f"    -> 评分中等 + 亏损中 -> 持有等待，关注趋势变化")
    elif score >= 45:
        if profit_pct > 5:
            print(f"    -> 评分偏弱 + 盈利 -> 建议逢高减仓，锁定利润")
        elif profit_pct < -3:
            print(f"    -> 评分偏弱 + 亏损 -> 建议止损或减仓")
        else:
            print(f"    -> 评分偏弱 -> 观望，不建议加仓")
    else:
        print(f"    -> 评分低 -> 建议减仓或清仓")

    if amount < 500:
        print(f"    !! 仓位仅{amount:.0f}元，过小无实际意义，建议加仓至有意义仓位或清掉")

# 总结
total = sum(info['amount'] for info in funds.values())
total_profit = sum(info['profit'] for info in funds.values())
print(f"\n{'─' * 60}")
print(f"  持仓总额: {total:,.2f}元")
print(f"  总收益:   {total_profit:+,.2f}元 ({total_profit/total*100:+.2f}%)")
print(f"  持仓数量: {len(funds)} 只 (全部为QDII)")
print(f"\n  !! 风险提示: 持仓全部集中在QDII海外基金，")
print(f"     缺乏A股、债券等配置，建议适当分散")
print("=" * 70)
