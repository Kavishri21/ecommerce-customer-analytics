"""Render three Matplotlib charts from the verified Olist analysis outputs."""

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator, PercentFormatter
import pandas as pd

from src.analysis.cohort_retention import RATES_PATH
from src.analysis.rfm import RESULT_PATH, load_order_spend, load_qualifying_orders
from src.ingestion.explore_dataset import ROOT


FIGURES = ROOT / "docs" / "figures"
BLUE = "#245b91"
TEAL = "#007c70"
INK = "#18324a"
MUTED = "#526677"
GRID = "#e1e8ee"


def style_axis(axis):
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.spines["bottom"].set_color(GRID)
    axis.tick_params(length=0, labelcolor=MUTED)
    axis.set_axisbelow(True)


def save_chart(figure, filename):
    figure.savefig(FIGURES / filename, dpi=160, bbox_inches="tight", pad_inches=0.2)
    plt.close(figure)


def plot_segments(customers):
    sizes = customers["segment"].value_counts()
    fig, ax = plt.subplots(figsize=(9.2, 4.3), layout="constrained")
    fig.suptitle("RFM customer segments", x=0.01, ha="left", fontsize=19, weight="bold", color=INK)
    ax.set_title(f"{len(customers):,} customers with qualifying purchases", loc="left", color=MUTED, pad=14)
    bars = ax.barh(sizes.index, sizes, color=BLUE, height=0.57)
    ax.bar_label(bars, labels=[f"{size:,}  ({size / len(customers):.1%})" for size in sizes],
                 padding=7, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, sizes.max() * 1.28)
    ax.set_xlabel("Customers")
    ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value / 1000:g}k" if value else "0"))
    style_axis(ax)
    ax.grid(axis="x", color=GRID)
    save_chart(fig, "rfm_segments.png")


def monthly_summary(orders, order_spend):
    purchases = orders.join(order_spend, on="order_id", validate="one_to_one")
    months = purchases["purchase_date"].dt.to_period("M")
    calendar = pd.period_range(months.min(), months.max(), freq="M")
    return purchases.groupby(months).agg(
        customers=("customer_unique_id", "nunique"),
        merchandise_cents=("monetary_cents", "sum"),
    ).reindex(calendar, fill_value=0)


def plot_monthly_sales(monthly):
    dates = monthly.index.to_timestamp()
    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(10, 6), layout="constrained")
    fig.suptitle("Monthly customers and merchandise value", x=0.01, ha="left",
                 fontsize=19, weight="bold", color=INK)
    series = (
        (monthly["customers"], "Distinct customers per month", BLUE, 1000, "k"),
        (monthly["merchandise_cents"] / 100, "Merchandise value excluding freight", TEAL, 1000000, "M"),
    )
    for ax, (values, title, color, unit, suffix) in zip(axes, series):
        ax.plot(dates, values, color=color, linewidth=2, marker="o", markersize=3)
        ax.fill_between(dates, values, color=color, alpha=0.09)
        ax.set_title(title, loc="left", color=INK)
        ax.set_ylim(0, values.max() * 1.2)
        ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.yaxis.set_major_formatter(
            FuncFormatter(lambda value, _, unit=unit, suffix=suffix: f"{value / unit:g}{suffix}" if value else "0")
        )
        ax.grid(axis="y", color=GRID)
        style_axis(ax)
    axes[-1].set_xticks(dates[::3].union(dates[-1:]))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    axes[-1].set_xlabel("Purchase month")
    save_chart(fig, "monthly_customer_sales.png")


def plot_cohort_retention(rates):
    months = rates.filter(regex=r"^month_[1-9][0-9]*$")
    labels = [f"{month}   ({size:,})" for month, size in zip(rates["cohort_month"], rates["cohort_size"])]
    fig, ax = plt.subplots(figsize=(10.5, 7.5), layout="constrained")
    fig.suptitle("Monthly cohort retention", x=0.01, ha="left",
                 fontsize=19, weight="bold", color=INK)
    ax.set_title("Gray cells are outside the observation window. Color saturates at 1%.",
                 loc="left", color=MUTED, pad=12)
    colors = plt.colormaps["Blues"].with_extremes(bad="#d6dce1")
    image = ax.imshow(months.to_numpy(dtype=float), cmap=colors, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(months.columns)), labels=[name.removeprefix("month_") for name in months])
    ax.set_yticks(range(len(labels)), labels=labels)
    ax.set_xlabel("Months after first purchase")
    ax.set_ylabel("Cohort start (customers)")
    style_axis(ax)
    colorbar = fig.colorbar(image, ax=ax, extend="max", shrink=0.82, pad=0.025)
    colorbar.set_label("Customers who returned")
    colorbar.ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=2))
    colorbar.outline.set_visible(False)
    save_chart(fig, "cohort_retention_heatmap.png")


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    customers = pd.read_csv(RESULT_PATH, usecols=["segment"])
    rates = pd.read_csv(RATES_PATH)
    orders = load_qualifying_orders()
    monthly = monthly_summary(orders, load_order_spend(orders))
    plot_segments(customers)
    plot_monthly_sales(monthly)
    plot_cohort_retention(rates)
    print(f"Saved three Matplotlib charts to {FIGURES}")


if __name__ == "__main__":
    main()
