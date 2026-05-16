"""
Generate 4 publication-quality figures from pubmed_data.csv.
"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import numpy as np
import os

CSV_PATH = "/home/user/cei_biblio/pubmed_data.csv"
OUT_DIR = "/home/user/cei_biblio/"

# Color palette
PALETTE = {
    "CEI": "#1f77b4",
    "Fac. Ciencias de la Salud": "#ff7f0e",
    "Inst. Ciencias Biológicas": "#2ca02c",
    "Fac. Ciencias Agrarias": "#d62728",
    "Inst. Química R. Naturales": "#9467bd",
    "Inst. Matemáticas": "#8c564b",
    "Fac. Medicina": "#e377c2",
    "Fac. Ingeniería": "#bcbd22",
}

df = pd.read_csv(CSV_PATH)
df["year"] = df["year"].astype(int)

units = sorted(df["unit"].unique())
print(f"Units found: {units}")
print(f"Year range: {df['year'].min()} - {df['year'].max()}")

# ──────────────────────────────────────────────────────────────
# FIG 1: Line chart — paper count per year per unit
# ──────────────────────────────────────────────────────────────
fig1, ax1 = plt.subplots(figsize=(10, 6))

all_years = sorted(df["year"].unique())
yearly = df.groupby(["unit", "year"]).size().reset_index(name="count")

for unit in units:
    udata = yearly[yearly["unit"] == unit].set_index("year")["count"]
    # Reindex to all years so gaps show as 0
    udata_full = udata.reindex(all_years, fill_value=0)
    color = PALETTE.get(unit, "gray")
    lw = 3.0 if unit == "CEI" else 1.5
    zorder = 5 if unit == "CEI" else 2
    ax1.plot(
        udata_full.index,
        udata_full.values,
        marker="o",
        markersize=5 if unit == "CEI" else 4,
        linewidth=lw,
        color=color,
        label=unit,
        zorder=zorder,
    )

ax1.set_title("Publications per Year by Unit (2020–present)", fontsize=14, fontweight="bold")
ax1.set_xlabel("Year", fontsize=12)
ax1.set_ylabel("Number of Publications", fontsize=12)
ax1.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
ax1.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
ax1.legend(loc="upper left", fontsize=9, framealpha=0.9)
ax1.grid(axis="y", linestyle="--", alpha=0.5)
plt.tight_layout()
fig1.savefig(os.path.join(OUT_DIR, "fig1_publication_counts.png"), dpi=150)
plt.close(fig1)
print("fig1 saved.")

# ──────────────────────────────────────────────────────────────
# FIG 2: Horizontal bar — total papers 2020-present per unit
# ──────────────────────────────────────────────────────────────
totals = df.groupby("unit").size().reset_index(name="total").sort_values("total", ascending=True)

colors_bar = [PALETTE.get(u, "gray") for u in totals["unit"]]

fig2, ax2 = plt.subplots(figsize=(10, 6))
bars = ax2.barh(totals["unit"], totals["total"], color=colors_bar, edgecolor="white", linewidth=0.5)
for bar, val in zip(bars, totals["total"]):
    ax2.text(val + 0.2, bar.get_y() + bar.get_height() / 2,
             str(val), va="center", ha="left", fontsize=10)

ax2.set_title("Total Publications 2020–present by Unit", fontsize=14, fontweight="bold")
ax2.set_xlabel("Number of Publications", fontsize=12)
ax2.set_ylabel("")
ax2.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
ax2.grid(axis="x", linestyle="--", alpha=0.4)
plt.tight_layout()
fig2.savefig(os.path.join(OUT_DIR, "fig2_total_papers.png"), dpi=150)
plt.close(fig2)
print("fig2 saved.")

# ──────────────────────────────────────────────────────────────
# FIG 3: Horizontal bar — top 10 journals for CEI
# ──────────────────────────────────────────────────────────────
cei_df = df[df["unit"] == "CEI"]
top10 = (
    cei_df.groupby("journal")
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=True)
    .tail(10)
)

fig3, ax3 = plt.subplots(figsize=(11, 6))
ax3.barh(top10["journal"], top10["count"],
         color=PALETTE["CEI"], edgecolor="white", linewidth=0.5)
for i, (jname, cnt) in enumerate(zip(top10["journal"], top10["count"])):
    ax3.text(cnt + 0.05, i, str(cnt), va="center", ha="left", fontsize=10)

ax3.set_title("Top 10 Journals for CEI (2020–present)", fontsize=14, fontweight="bold")
ax3.set_xlabel("Number of Publications", fontsize=12)
ax3.set_ylabel("")
ax3.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
ax3.grid(axis="x", linestyle="--", alpha=0.4)
plt.tight_layout()
fig3.savefig(os.path.join(OUT_DIR, "fig3_top_journals_cei.png"), dpi=150)
plt.close(fig3)
print("fig3 saved.")

# ──────────────────────────────────────────────────────────────
# FIG 4: Heatmap — units × top CEI journals (CEI ≥2 papers)
# ──────────────────────────────────────────────────────────────
cei_journals = (
    cei_df.groupby("journal")
    .size()
    .reset_index(name="count")
)
cei_journals_ge2 = cei_journals[cei_journals["count"] >= 2]["journal"].tolist()
print(f"CEI journals with >=2 papers: {len(cei_journals_ge2)} -> {cei_journals_ge2}")

if len(cei_journals_ge2) == 0:
    # Fallback: use all CEI journals
    cei_journals_ge2 = cei_journals.sort_values("count", ascending=False).head(10)["journal"].tolist()
    print(f"Fallback: using top {len(cei_journals_ge2)} CEI journals")

# Build pivot: units × cei_journals_ge2
df_hm = df[df["journal"].isin(cei_journals_ge2)]
pivot = (
    df_hm.groupby(["unit", "journal"])
    .size()
    .reset_index(name="count")
    .pivot(index="unit", columns="journal", values="count")
    .fillna(0)
    .astype(int)
)

# Sort columns by CEI count descending
cei_order = (
    cei_df[cei_df["journal"].isin(cei_journals_ge2)]
    .groupby("journal").size()
    .sort_values(ascending=False)
    .index.tolist()
)
# Keep only columns present in pivot
cei_order = [j for j in cei_order if j in pivot.columns]
pivot = pivot[cei_order]

# Sort rows: CEI first, then alphabetically
row_order = ["CEI"] + sorted([u for u in pivot.index if u != "CEI"])
pivot = pivot.reindex(row_order)

fig4, ax4 = plt.subplots(figsize=(max(10, len(cei_order) * 1.3), max(6, len(pivot) * 0.8)))
sns.heatmap(
    pivot,
    annot=True,
    fmt="d",
    cmap="Blues",
    linewidths=0.5,
    linecolor="white",
    ax=ax4,
    cbar_kws={"label": "Publication count"},
)
ax4.set_title("Publications per Unit × CEI Top Journals (2020–present)", fontsize=13, fontweight="bold")
ax4.set_xlabel("Journal", fontsize=11)
ax4.set_ylabel("Unit", fontsize=11)
ax4.tick_params(axis="x", rotation=45, labelsize=8)
ax4.tick_params(axis="y", rotation=0, labelsize=9)
plt.tight_layout()
fig4.savefig(os.path.join(OUT_DIR, "fig4_journal_heatmap.png"), dpi=150, bbox_inches="tight")
plt.close(fig4)
print("fig4 saved.")

print("\nAll 4 figures created successfully.")
