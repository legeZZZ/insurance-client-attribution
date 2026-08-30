import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from daimon_runtime import setup_plot

sns.set_theme(style="whitegrid")
setup_plot()

data = json.loads(Path("outputs/benchmark_metrics.json").read_text())
seeds = pd.DataFrame(data["per_seed"])
seeds["场景"] = seeds["mismatched"].map({False: "同构", True: "错配"})
seeds["seed"] = seeds["seed"].astype(str)

fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))

# 1) 核心准确率（聚合）
agg = pd.DataFrame(
    [
        ("Recall@5", 1.0, 0.80),
        ("决策准确率", 1.0, 0.80),
        ("HTE 方向", 1.0, 0.80),
        ("CrI 覆盖率", 1.0, 0.95),
        ("因子还原", 1.0, 0.80),
        ("线B 未注册召回", 1.0, 0.70),
    ],
    columns=["指标", "实测", "阈值"],
)
sns.barplot(data=agg, y="指标", x="实测", ax=axes[0], color="#4C9AFF")
for i, r in agg.iterrows():
    axes[0].plot([r["阈值"], r["阈值"]], [i - 0.4, i + 0.4], color="#E45756", lw=2)
axes[0].set_xlim(0, 1.1)
axes[0].set_title("核心指标 vs 阈值（红线=阈值）")
axes[0].set_xlabel("实测值")
axes[0].set_ylabel("")

# 2) 每种子 ATE 误差与 Brier
axes[1].bar(
    seeds["seed"],
    seeds["bundle_ate_error"],
    color=["#72B7B2" if not m else "#F58518" for m in seeds["mismatched"]],
)
axes[1].axhline(0, color="#333", lw=1)
axes[1].set_title("逐种子 ATE 估计误差（RMSE 0.0010）")
axes[1].set_xlabel("seed")
axes[1].set_ylabel("ATE 误差")
ax2 = axes[1].twinx()
ax2.plot(seeds["seed"], seeds["brier"], "o--", color="#B279A2", label="Brier")
ax2.set_ylabel("Brier", color="#B279A2")
ax2.tick_params(axis="y", labelcolor="#B279A2")

# 3) 收缩消融
abl = pd.DataFrame(
    [
        ("同构", "朴素合并", 0.004807),
        ("同构", "多层收缩", 0.004162),
        ("错配", "朴素合并", 0.005795),
        ("错配", "多层收缩", 0.004867),
    ],
    columns=["场景", "方法", "调节RMSE"],
)
sns.barplot(
    data=abl,
    x="场景",
    y="调节RMSE",
    hue="方法",
    ax=axes[2],
    palette=["#BAB0AC", "#59A14F"],
)
axes[2].set_title("多层收缩消融（越低越好）")
for c in axes[2].containers:
    axes[2].bar_label(c, fmt="%.4f", fontsize=9)

fig.suptitle(
    "基准实测（线A 7 seeds + 线B 5 seeds · 门禁通过率 1.00 / 误报率 0.00）", fontsize=14
)
fig.savefig("outputs/v3_benchmark.png", dpi=180, bbox_inches="tight")
print("saved", Path("outputs/v3_benchmark.png").stat().st_size)
