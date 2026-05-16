"""Build cei_biblio.ipynb programmatically."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []

# ── Cell 0: Markdown preamble ─────────────────────────────────────────────────
cells.append(nbf.v4.new_markdown_cell("""\
# CEI Bibliometric Analysis — Universidad de Talca

This notebook compares the research article output of the **Center for Integrative Ecology
(Centro de Ecología Integrativa — CEI)** against seven other academic units of
Universidad de Talca (Chile) using data from the [OpenAlex](https://openalex.org) open
bibliometric API.

## Units compared
| Label | Spanish / English names |
|-------|------------------------|
| **CEI** | Centro de Ecología Integrativa / Center for Integrative Ecology |
| CBSM | Centro de Bioinformática, Simulación y Modelado / Center for Bioinformatics, Simulations and Modelling |
| Fac. Ciencias de la Salud | Facultad de Ciencias de la Salud / Faculty of Health Sciences |
| Inst. Ciencias Biológicas | Instituto de Ciencias Biológicas / Institute of Biological Sciences |
| Fac. Ciencias Agrarias | Facultad de Ciencias Agrarias / Faculty of Agrarian Sciences |
| Inst. Química R. Naturales | Instituto de Química de Recursos Naturales |
| Inst. Matemáticas | Instituto de Matemáticas / Institute of Mathematics |
| Fac. Medicina | Escuela / Facultad de Medicina / School of Medicine |
| Fac. Ingeniería | Facultad de Ingeniería / Faculty of Engineering |

## Scope
- **Date range**: 2020 – present
- **Work type**: journal articles
- **Attribution rule**: if a paper has *any* CEI author it is counted exclusively as CEI
  (no double-counting with other units)

## Data source
OpenAlex API (https://api.openalex.org) — no API key required.
Data retrieved via cursor pagination; cached locally to `openalex_cache.json`.
"""))

# ── Cell 1: Install dependencies (needed in Colab) ───────────────────────────
cells.append(nbf.v4.new_code_cell("""\
# Install pyalex if not already present (required in Google Colab)
import importlib, subprocess, sys
if importlib.util.find_spec("pyalex") is None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pyalex"])
"""))

# ── Cell 2: Imports and configuration ────────────────────────────────────────
cells.append(nbf.v4.new_code_cell("""\
import re
import time
import json
import pathlib
from collections import defaultdict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from tqdm.auto import tqdm
import pyalex
from pyalex import Works, config

# ── Polite pool — set your email here ────────────────────────────────────────
config.email = "castronallar@gmail.com"
config.max_retries = 5
config.retry_backoff_factor = 0.5
config.retry_http_codes = [429, 500, 503]

# ── Institution (ID resolved dynamically in next cell) ───────────────────────
UTALCA_ID = None   # set automatically by the institution lookup cell below
YEAR_MIN   = 2020

# ── CEI / CBSM detection patterns (research-center names are unique ─────────
# enough to imply UTalca affiliation regardless of how OpenAlex parsed
# the authorship's institutions array — so we scan ALL authorship raw
# strings for these, not just UTalca-tagged ones)
_CEI_PATTERNS = [
    r"centro\\s+de\\s+ecolog[íi]a\\s+integrativa",
    r"center\\s+for\\s+integrative\\s+ecology",
    r"\\bCEI\\b",
]
CEI_RE = re.compile("|".join(_CEI_PATTERNS), re.IGNORECASE)

_CBSM_PATTERNS = [
    r"centro\\s+de\\s+bioinform[áa]tica",
    r"center\\s+for\\s+bioinformatics",
    r"bioinformatics?,?\\s+simulations?\\s+and\\s+modell?ing",
    r"\\bCBSM\\b",
]
CBSM_RE = re.compile("|".join(_CBSM_PATTERNS), re.IGNORECASE)

# ── Target unit patterns (order matters: first match wins) ───────────────────
# Faculties / institutes: only matched against UTalca-tagged authorships,
# since "Faculty of Engineering" on a foreign author would be a false hit.
UNIT_LABEL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ciencias\\s+de\\s+la\\s+salud|health\\s+sciences|faculty\\s+of\\s+health", re.I),
     "Fac. Ciencias de la Salud"),
    (re.compile(r"ciencias\\s+biol[oó]gicas|biological\\s+sciences|instituto\\s+de\\s+ciencias\\s+biol", re.I),
     "Inst. Ciencias Biológicas"),
    (re.compile(r"ciencias\\s+agrarias|agrarian\\s+sciences|agronomy|agronom[ií]a|faculty\\s+of\\s+agri", re.I),
     "Fac. Ciencias Agrarias"),
    (re.compile(r"qu[íi]mica\\s+de\\s+recursos\\s+naturales|natural\\s+resources\\s+chemistry|instituto\\s+de\\s+qu[íi]mica", re.I),
     "Inst. Química R. Naturales"),
    (re.compile(r"matem[aá]ticas|mathematics|instituto\\s+de\\s+matem", re.I),
     "Inst. Matemáticas"),
    (re.compile(r"medicina|medicine|escuela\\s+de\\s+medicina|faculty\\s+of\\s+medicine", re.I),
     "Fac. Medicina"),
    (re.compile(r"ingenier[íi]a|engineering|faculty\\s+of\\s+engineering", re.I),
     "Fac. Ingeniería"),
]

TARGET_UNITS = [label for _, label in UNIT_LABEL_PATTERNS]
ALL_UNITS    = ["CEI", "CBSM"] + TARGET_UNITS

print("Configuration loaded.")
print(f"Comparing CEI against {len(TARGET_UNITS)} units, articles from {YEAR_MIN}+")
"""))

# ── Cell 2: Cache helpers ─────────────────────────────────────────────────────
cells.append(nbf.v4.new_code_cell("""\
CACHE_FILE = pathlib.Path("openalex_cache.json")
SOURCES_CACHE_FILE = pathlib.Path("sources_cache.json")

def save_cache(works: list, path: pathlib.Path = CACHE_FILE) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(works, f)
    print(f"Cached {len(works):,} works → {path}")

def load_cache(path: pathlib.Path = CACHE_FILE) -> list | None:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Loaded {len(data):,} works from cache ({path})")
        return data
    return None

def save_sources_cache(sources: dict, path: pathlib.Path = SOURCES_CACHE_FILE) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sources, f)
    print(f"Cached {len(sources):,} sources → {path}")

def load_sources_cache(path: pathlib.Path = SOURCES_CACHE_FILE) -> dict | None:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Loaded {len(data):,} sources from cache ({path})")
        return data
    return None
"""))

# ── Cell 3: Verify institution ID ─────────────────────────────────────────────
cells.append(nbf.v4.new_code_cell("""\
from pyalex import Institutions

results = Institutions().search("Universidad de Talca").get()
print("Matches for 'Universidad de Talca' in OpenAlex:")
for r in results:
    print(f"  {r['id']}  |  {r['display_name']}  |  ROR: {r.get('ror','—')}  |  Works: {r.get('works_count',0):,}")

# Auto-select the first match if only one result
if len(results) == 1:
    UTALCA_ID = results[0]["id"]
    print(f"\\nUsing: {UTALCA_ID}")
else:
    # If multiple hits, pick the one with the most works (most likely the right one)
    best = max(results, key=lambda r: r.get("works_count", 0))
    UTALCA_ID = best["id"]
    print(f"\\nAuto-selected best match: {UTALCA_ID}  ({best['display_name']})")
"""))

# ── Cell 4: Fetch ─────────────────────────────────────────────────────────────
cells.append(nbf.v4.new_code_cell("""\
def fetch_utalca_works() -> list:
    query = (
        Works()
        .filter(authorships={"institutions": {"id": UTALCA_ID}})
        .filter(type="article")
        .filter(publication_year=f">{YEAR_MIN - 1}")
    )
    all_works = []
    pages = query.paginate(method="cursor", per_page=200, n_max=50_000)
    for page in tqdm(pages, desc="Fetching from OpenAlex"):
        all_works.extend(list(page))
        time.sleep(0.12)
    return all_works

raw_works = load_cache()
if not raw_works:
    raw_works = fetch_utalca_works()
    save_cache(raw_works)

print(f"Total works: {len(raw_works):,}")
"""))

# ── Cell 4b: Journal-source enrichment (impact factor proxy) ─────────────────
cells.append(nbf.v4.new_markdown_cell("""\
### Journal-source enrichment

For each unique primary-source (journal) referenced by our works, fetch the
source's `summary_stats["2yr_mean_citedness"]` from the OpenAlex *Sources*
endpoint. This is OpenAlex's open analog of a 2-year Journal Impact Factor
(it is **not** Clarivate's JCR IF, which is paywalled). The values are
cached to `sources_cache.json` so re-runs are instant.
"""))

cells.append(nbf.v4.new_code_cell("""\
from pyalex import Sources

def collect_source_ids(works: list) -> list[str]:
    ids: set[str] = set()
    for w in works:
        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}
        sid = src.get("id")
        if sid:
            ids.add(sid)
    return sorted(ids)

def _short_id(full_id: str) -> str:
    return full_id.rsplit("/", 1)[-1]

def fetch_sources(source_ids: list[str]) -> dict:
    \"\"\"Fetch sources in batches of 50 via OpenAlex; return {id: source_dict}.

    Uses the openalex_id filter with pipe-OR (per OpenAlex docs). Falls back
    to per-id fetch on batch errors so a single bad ID doesn't break a run.
    \"\"\"
    out: dict[str, dict] = {}
    batch_size = 50
    batches = [source_ids[i:i+batch_size] for i in range(0, len(source_ids), batch_size)]
    for batch in tqdm(batches, desc="Fetching sources from OpenAlex"):
        short_ids = [_short_id(s) for s in batch]
        try:
            results = Sources().filter(openalex_id="|".join(short_ids)).get(per_page=batch_size)
            got = {s["id"]: s for s in results if s.get("id")}
            # If the filter returned fewer than requested (e.g. some IDs invalid),
            # fall back to per-id for the missing ones.
            missing = [sid for sid in batch if sid not in got]
            for sid in missing:
                try:
                    out[sid] = Sources()[_short_id(sid)]
                except Exception:
                    pass
                time.sleep(0.05)
            out.update(got)
        except Exception as e:
            print(f"  ! batch error ({len(batch)} ids), falling back per-id: {e}")
            for sid in batch:
                try:
                    out[sid] = Sources()[_short_id(sid)]
                except Exception:
                    pass
                time.sleep(0.05)
        time.sleep(0.12)
    return out

sources_cache = load_sources_cache() or {}
needed_ids = [sid for sid in collect_source_ids(raw_works) if sid not in sources_cache]
if needed_ids:
    print(f"Fetching {len(needed_ids):,} new sources (cached: {len(sources_cache):,})")
    fresh = fetch_sources(needed_ids)
    sources_cache.update(fresh)
    save_sources_cache(sources_cache)
else:
    print(f"All {len(sources_cache):,} sources already cached")

# Build {source_id → 2yr_mean_citedness} lookup
JOURNAL_2YR_IF: dict[str, float] = {}
for sid, src in sources_cache.items():
    stats = src.get("summary_stats") or {}
    val = stats.get("2yr_mean_citedness")
    if val is not None:
        JOURNAL_2YR_IF[sid] = float(val)

print(f"Journals with 2-year mean citedness: {len(JOURNAL_2YR_IF):,} / {len(sources_cache):,}")
"""))

# ── Cell 4: Classification helpers ───────────────────────────────────────────
cells.append(nbf.v4.new_code_cell("""\
def normalize_unit(raw: str) -> str:
    for pattern, label in UNIT_LABEL_PATTERNS:
        if pattern.search(raw):
            return label
    return "Other UTalca"

def classify_work(work: dict) -> set:
    \"\"\"Return the set of unit labels for this work.

    CEI takes exclusive ownership. CEI / CBSM are detected on ANY
    authorship's raw affiliation strings (these names imply UTalca
    even if OpenAlex parsed the institution as a separate entity).
    Other faculties / institutes are only credited when the authorship
    is parsed as UTalca-affiliated, to avoid attributing a foreign
    author's "Faculty of Engineering" to UTalca's.
    \"\"\"
    all_raws = [
        raw
        for a in work.get("authorships", [])
        for raw in a.get("raw_affiliation_strings", [])
    ]
    if any(CEI_RE.search(r) for r in all_raws):
        return {"CEI"}

    units: set[str] = set()
    if any(CBSM_RE.search(r) for r in all_raws):
        units.add("CBSM")

    for authorship in work.get("authorships", []):
        inst_ids = [i.get("id", "") for i in authorship.get("institutions", [])]
        if not any(UTALCA_ID in iid for iid in inst_ids):
            continue
        for raw in authorship.get("raw_affiliation_strings", []):
            unit = normalize_unit(raw)
            if unit != "Other UTalca":
                units.add(unit)
    return units or {"Other UTalca"}
"""))

# ── Cell 5: Build master DataFrame ───────────────────────────────────────────
cells.append(nbf.v4.new_code_cell("""\
def build_records(works: list) -> pd.DataFrame:
    rows = []
    for work in works:
        unit_set = classify_work(work)
        loc = work.get("primary_location") or {}
        src = loc.get("source") or {}
        journal = src.get("display_name", "Unknown Journal")
        journal_id = src.get("id")
        journal_2yr_if = JOURNAL_2YR_IF.get(journal_id) if journal_id else None
        base = {
            "openalex_id":              work.get("id", ""),
            "doi":                      work.get("doi", ""),
            "title":                    work.get("title", ""),
            "year":                     work.get("publication_year"),
            "cited_by_count":           work.get("cited_by_count", 0) or 0,
            "journal":                  journal,
            "journal_id":               journal_id,
            "journal_2yr_mean_citedness": journal_2yr_if,
        }
        for unit in unit_set:
            rows.append({**base, "unit": unit})
    df = pd.DataFrame(rows)
    df["year"]           = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    df["journal_2yr_mean_citedness"] = pd.to_numeric(
        df["journal_2yr_mean_citedness"], errors="coerce"
    )
    return df

df = build_records(raw_works)
print(f"Rows (work×unit): {len(df):,}  |  Unique works: {df['openalex_id'].nunique():,}")
print("\\nPapers per unit:")
print(df.groupby('unit')['openalex_id'].nunique().sort_values(ascending=False).to_string())
"""))

# ── Cell 6: Validation ────────────────────────────────────────────────────────
cells.append(nbf.v4.new_code_cell("""\
assert df["openalex_id"].notna().all(), "Null OpenAlex IDs found"
assert (df["cited_by_count"] >= 0).all(), "Negative citation counts"

cei_n = df[df["unit"] == "CEI"]["openalex_id"].nunique()
assert cei_n > 0, "CEI matched 0 papers — check patterns or institution ID"
print(f"CEI papers : {cei_n:,}")
print(f"Year range : {df['year'].min()} – {df['year'].max()}")
print(f"Null years : {df['year'].isna().sum()}")

# Sample unclassified raw strings for pattern tuning
other_works = [w for w in raw_works if classify_work(w) == {"Other UTalca"}]
sample_raws = []
for w in other_works[:40]:
    for a in w.get("authorships", []):
        if any(UTALCA_ID in i.get("id","") for i in a.get("institutions",[])):
            sample_raws.extend(a.get("raw_affiliation_strings", []))
print(f"\\n'Other UTalca' papers: {len(other_works):,}")
print("Sample unclassified raw strings (first 10 unique):")
for s in list(dict.fromkeys(sample_raws))[:10]:
    print(" •", s)
"""))

# ── Cell 7: Analysis 1 header ────────────────────────────────────────────────
cells.append(nbf.v4.new_markdown_cell("## Analysis 1 — Publication Counts Over Time"))

# ── Cell 8: Publication counts ────────────────────────────────────────────────
cells.append(nbf.v4.new_code_cell("""\
FOCUS_UNITS = ALL_UNITS   # CEI + 7 named units

pub = (
    df[df["unit"].isin(FOCUS_UNITS)]
    .groupby(["unit", "year"])["openalex_id"]
    .nunique()
    .rename("count")
    .reset_index()
)

years = sorted(df["year"].dropna().unique())
pivot = (
    pub.pivot(index="year", columns="unit", values="count")
    .reindex(years)
    .fillna(0)
)

palette = {
    "CEI":                       "#1f77b4",
    "CBSM":                      "#17becf",
    "Fac. Ciencias de la Salud": "#ff7f0e",
    "Inst. Ciencias Biológicas": "#2ca02c",
    "Fac. Ciencias Agrarias":    "#d62728",
    "Inst. Química R. Naturales":"#9467bd",
    "Inst. Matemáticas":         "#8c564b",
    "Fac. Medicina":             "#e377c2",
    "Fac. Ingeniería":           "#bcbd22",
}

fig, axes = plt.subplots(1, 2, figsize=(16, 5))

# Left: line chart — CEI bold, others thinner
ax1 = axes[0]
for unit in FOCUS_UNITS:
    if unit not in pivot.columns:
        continue
    lw   = 2.8 if unit == "CEI" else 1.4
    ms   = 5   if unit == "CEI" else 3
    zord = 5   if unit == "CEI" else 2
    ax1.plot(pivot.index, pivot[unit],
             label=unit, color=palette.get(unit, "gray"),
             linewidth=lw, marker="o", markersize=ms, zorder=zord)
ax1.set_title("Annual Publications — CEI vs Academic Units (2020+)")
ax1.set_xlabel("Year")
ax1.set_ylabel("Publications")
ax1.legend(fontsize=8, loc="upper left")
ax1.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

# Right: grouped bar chart per year
ax2 = axes[1]
bar_data = pivot[[u for u in FOCUS_UNITS if u in pivot.columns]]
bar_data.plot(kind="bar", ax=ax2, color=[palette.get(u,"gray") for u in bar_data.columns],
              width=0.75, edgecolor="white")
ax2.set_title("Annual Publications — Grouped Bar")
ax2.set_xlabel("Year")
ax2.set_ylabel("Publications")
ax2.legend(fontsize=7, loc="upper left")
ax2.tick_params(axis="x", rotation=45)

plt.tight_layout()
plt.savefig("fig1_publication_counts.png", dpi=150, bbox_inches="tight")
plt.show()
print("Saved fig1_publication_counts.png")
"""))

# ── Cell 9: Analysis 2 header ────────────────────────────────────────────────
cells.append(nbf.v4.new_markdown_cell("## Analysis 2 — Citation Impact"))

# ── Cell 10: Citation impact ──────────────────────────────────────────────────
cells.append(nbf.v4.new_code_cell("""\
def h_index(series: pd.Series) -> int:
    counts = sorted(series.dropna().astype(int), reverse=True)
    h = 0
    for i, c in enumerate(counts, 1):
        if c >= i:
            h = i
        else:
            break
    return h

# Deduplicate per work×unit before aggregating citations
work_unit = df[df["unit"].isin(FOCUS_UNITS)].drop_duplicates(subset=["openalex_id","unit"])

impact = (
    work_unit.groupby("unit")["cited_by_count"]
    .agg(
        total_citations="sum",
        mean_citations="mean",
        median_citations="median",
        paper_count="count",
        h_index=h_index,
    )
    .reset_index()
    .sort_values("h_index", ascending=False)
    .reset_index(drop=True)
)

fig, axes = plt.subplots(1, 3, figsize=(18, 6))

metrics = [
    ("h_index",        "h-index",               "h-index"),
    ("mean_citations", "Mean Citations / Paper", "Mean citations"),
    ("total_citations","Total Citations",         "Total citations"),
]
for ax, (col, title, xlabel) in zip(axes, metrics):
    colors = [palette.get(u, "#aec7e8") for u in impact["unit"]]
    ax.barh(impact["unit"], impact[col], color=colors, edgecolor="white")
    ax.invert_yaxis()
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    # Highlight CEI bar edge
    cei_idx = impact[impact["unit"]=="CEI"].index
    if len(cei_idx):
        ax.patches[int(cei_idx[0])].set_edgecolor("black")
        ax.patches[int(cei_idx[0])].set_linewidth(1.5)

plt.tight_layout()
plt.savefig("fig2_citation_impact.png", dpi=150, bbox_inches="tight")
plt.show()
print("Saved fig2_citation_impact.png")
display(
    impact.style
    .highlight_max(subset=["total_citations","mean_citations","h_index"], color="#cfe2ff")
    .format({"mean_citations": "{:.2f}", "median_citations": "{:.1f}",
             "total_citations": "{:,.0f}"})
    .set_caption("Citation Impact by Unit")
)
"""))

# ── Cell 11: Analysis 3 header ────────────────────────────────────────────────
cells.append(nbf.v4.new_markdown_cell("## Analysis 3 — Journal Distribution"))

# ── Cell 12: Journal distribution ────────────────────────────────────────────
cells.append(nbf.v4.new_code_cell("""\
TOP_N = 10
journals_df = df[df["unit"].isin(FOCUS_UNITS)].drop_duplicates(subset=["openalex_id","unit"])

def top_journals(unit_name: str, n: int = TOP_N) -> pd.DataFrame:
    return (
        journals_df[journals_df["unit"] == unit_name]
        .groupby("journal")["openalex_id"].count()
        .nlargest(n)
        .rename("count")
        .reset_index()
    )

# ── Fig 3a: CEI top journals ──────────────────────────────────────────────────
cei_j = top_journals("CEI")
fig, ax = plt.subplots(figsize=(10, 5))
ax.barh(cei_j["journal"][::-1], cei_j["count"][::-1], color="#1f77b4")
ax.set_title(f"Top {TOP_N} Journals — CEI")
ax.set_xlabel("Publications")
ax.set_yticklabels(
    [j if len(j) < 45 else j[:42]+"…" for j in cei_j["journal"][::-1]], fontsize=9
)
plt.tight_layout()
plt.savefig("fig3a_cei_journals.png", dpi=150, bbox_inches="tight")
plt.show()

# ── Fig 3b: top journals per comparison unit (small multiples) ────────────────
n_cols = 2
n_rows = (len(TARGET_UNITS) + 1) // 2
fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, n_rows * 4))
axes_flat = axes.flatten()

for i, unit in enumerate(TARGET_UNITS):
    ax = axes_flat[i]
    jdf = top_journals(unit, TOP_N)
    if jdf.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_title(unit)
        continue
    ax.barh(jdf["journal"][::-1], jdf["count"][::-1], color=palette.get(unit,"#aec7e8"))
    ax.set_title(f"Top {TOP_N} Journals — {unit}", fontsize=9)
    ax.set_xlabel("Publications", fontsize=8)
    ax.set_yticklabels(
        [j if len(j) < 38 else j[:35]+"…" for j in jdf["journal"][::-1]], fontsize=7
    )

for j in range(i+1, len(axes_flat)):
    axes_flat[j].set_visible(False)

plt.suptitle("Top Journals by Academic Unit", fontsize=12, y=1.01)
plt.tight_layout()
plt.savefig("fig3b_unit_journals.png", dpi=150, bbox_inches="tight")
plt.show()

# ── Fig 4: heatmap — units × CEI's core journals ─────────────────────────────
cei_core = set(
    journals_df[journals_df["unit"]=="CEI"]
    .groupby("journal")["openalex_id"].count()
    .pipe(lambda s: s[s >= 2]).index
)

shared = journals_df[journals_df["journal"].isin(cei_core)]
hmap = (
    shared.groupby(["unit","journal"])["openalex_id"]
    .count()
    .unstack(fill_value=0)
)

if not hmap.empty:
    fig, ax = plt.subplots(figsize=(max(12, len(hmap.columns)*0.55), max(4, len(hmap)*0.5)))
    sns.heatmap(hmap, annot=True, fmt="d", cmap="YlOrRd",
                linewidths=0.4, linecolor="white", ax=ax)
    ax.set_title("Publications per Unit in CEI's Core Journals (≥2 CEI papers)")
    ax.set_xlabel("Journal")
    ax.set_ylabel("")
    plt.xticks(rotation=40, ha="right", fontsize=7)
    plt.yticks(fontsize=8)
    plt.tight_layout()
    plt.savefig("fig4_journal_heatmap.png", dpi=150, bbox_inches="tight")
    plt.show()
    print("Saved fig4_journal_heatmap.png")
else:
    print("Heatmap skipped — no shared journals found.")
print("Saved fig3a_cei_journals.png  fig3b_unit_journals.png")
"""))

# ── Cell 13: Summary table ────────────────────────────────────────────────────
cells.append(nbf.v4.new_markdown_cell("## Summary Table"))

cells.append(nbf.v4.new_code_cell("""\
summary = (
    work_unit.groupby("unit")
    .agg(
        papers       = ("openalex_id", "nunique"),
        total_cit    = ("cited_by_count", "sum"),
        mean_cit     = ("cited_by_count", "mean"),
        h_index      = ("cited_by_count", h_index),
        mean_if      = ("journal_2yr_mean_citedness", "mean"),
        median_if    = ("journal_2yr_mean_citedness", "median"),
        first_year   = ("year", "min"),
        last_year    = ("year", "max"),
    )
    .sort_values("papers", ascending=False)
    .reset_index()
    .rename(columns={"unit":"Unit","papers":"Papers",
                     "total_cit":"Total Citations","mean_cit":"Mean Cit./Paper",
                     "h_index":"h-index",
                     "mean_if":"Mean Journal IF","median_if":"Median Journal IF",
                     "first_year":"From","last_year":"To"})
)

display(
    summary.style
    .background_gradient(subset=["Papers","Total Citations","h-index"], cmap="Blues")
    .format({
        "Mean Cit./Paper":   "{:.2f}",
        "Total Citations":   "{:,.0f}",
        "Mean Journal IF":   "{:.2f}",
        "Median Journal IF": "{:.2f}",
    }, na_rep="—")
    .set_caption("Bibliometric Summary — Universidad de Talca (2020+)")
)
"""))

# ── Cell 14: Export ───────────────────────────────────────────────────────────
cells.append(nbf.v4.new_code_cell("""\
import datetime

# ── CSV export ────────────────────────────────────────────────────────────────
df.to_csv("works_by_unit.csv", index=False)
summary.to_csv("summary_by_unit.csv", index=False)
print("Exported works_by_unit.csv and summary_by_unit.csv")

# ── Website data export ───────────────────────────────────────────────────────
docs_dir = pathlib.Path("docs")
docs_dir.mkdir(exist_ok=True)

work_unit_export = df[df["unit"].isin(ALL_UNITS)].drop_duplicates(subset=["openalex_id", "unit"])

papers_export = [
    {
        "id":             row["openalex_id"],
        "unit":           row["unit"],
        "year":           int(row["year"]) if pd.notna(row["year"]) else None,
        "journal":        row["journal"],
        "journal_id":     row["journal_id"] if pd.notna(row["journal_id"]) else None,
        "journal_2yr_mean_citedness": (
            round(float(row["journal_2yr_mean_citedness"]), 3)
            if pd.notna(row["journal_2yr_mean_citedness"]) else None
        ),
        "title":          row["title"],
        "doi":            row["doi"] if pd.notna(row["doi"]) and row["doi"] else None,
        "cited_by_count": int(row["cited_by_count"]),
    }
    for _, row in work_unit_export.iterrows()
]

summary_export = [
    {
        "unit":                       row["Unit"],
        "papers":                     int(row["Papers"]),
        "total_citations":            int(row["Total Citations"]),
        "mean_citations":             round(float(row["Mean Cit./Paper"]), 2),
        "h_index":                    int(row["h-index"]),
        "mean_journal_2yr_citedness": (
            round(float(row["Mean Journal IF"]), 2)
            if pd.notna(row["Mean Journal IF"]) else None
        ),
        "median_journal_2yr_citedness": (
            round(float(row["Median Journal IF"]), 2)
            if pd.notna(row["Median Journal IF"]) else None
        ),
        "first_year":      int(row["From"]) if pd.notna(row["From"]) else None,
        "last_year":       int(row["To"])   if pd.notna(row["To"])   else None,
    }
    for _, row in summary.iterrows()
]

site_data = {
    "generated":  datetime.date.today().isoformat(),
    "year_range": [YEAR_MIN, int(df["year"].dropna().max())],
    "units":      ALL_UNITS,
    "papers":     papers_export,
    "summary":    summary_export,
}

with open(docs_dir / "data.json", "w", encoding="utf-8") as fh:
    json.dump(site_data, fh, ensure_ascii=False, indent=2)

print(f"Exported {len(papers_export):,} paper records → docs/data.json")
print("Interactive website ready — open docs/index.html or enable GitHub Pages on the docs/ folder")
"""))

nb.cells = cells
nbf.write(nb, "/home/user/cei_biblio/cei_biblio.ipynb")
print("Notebook written.")
