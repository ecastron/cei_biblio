# CEI Bibliometric Analysis — Universidad de Talca

Compares the research output of the **Center for Integrative Ecology (Centro de Ecología Integrativa — CEI)** against seven other academic units of Universidad de Talca using data from the [OpenAlex](https://openalex.org) open bibliometric database.

## Units compared

| Unit |
|------|
| Center for Integrative Ecology (CEI) |
| Center for Bioinformatics, Simulations and Modelling (CBSM) |
| Facultad de Ciencias de la Salud |
| Instituto de Ciencias Biológicas |
| Facultad de Ciencias Agrarias |
| Instituto de Química de Recursos Naturales |
| Instituto de Matemáticas |
| Escuela / Facultad de Medicina |
| Facultad de Ingeniería |

## What the notebook produces

- **Publication counts over time** — articles per year per unit (2020–present)
- **Citation impact** — h-index, mean and total citations per unit
- **Journal distribution** — top journals per unit and a cross-unit heatmap
- **Journal impact** — each paper is enriched with its journal's
  *2-year mean citedness* from OpenAlex (an open analog of JCR Impact
  Factor, **not** Clarivate's paywalled IF); per-unit mean and median
  are included in `docs/data.json`

## Run in Google Colab (recommended for iPad / browser)

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ecastron/cei_biblio/blob/main/cei_biblio.ipynb)

1. Click the badge above, or go to [colab.research.google.com](https://colab.research.google.com) → **File → Open notebook → GitHub** → `ecastron/cei_biblio`
2. Select `cei_biblio.ipynb`
3. **Runtime → Run all**

The first cell installs `pyalex` automatically. Data is fetched from OpenAlex and cached locally so subsequent runs are instant.

## Run locally

```bash
git clone https://github.com/ecastron/cei_biblio.git
cd cei_biblio
pip install -r requirements.txt
jupyter notebook cei_biblio.ipynb
```

## Interactive website

After running the notebook, a `docs/data.json` file is generated. The interactive site at `docs/index.html` reads it and provides three views — publications over time, citation impact, and journal distribution — all filterable by unit.

**To publish via GitHub Pages:**
1. Go to your repository → **Settings → Pages**
2. Set source to **Deploy from a branch**, branch `main` (or your working branch), folder **`/docs`**
3. The site will be live at `https://ecastron.github.io/cei_biblio/`

**To preview locally:**
```bash
python -m http.server 8000 --directory docs/
# then open http://localhost:8000
```

## Data source

[OpenAlex](https://openalex.org) — open, free bibliometric database covering 200M+ scholarly works.  
No API key required. Uses the [polite pool](https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication) via a registered email address.

## Attribution rule

If any author on a paper is affiliated with CEI, the paper is counted **exclusively as CEI** and not attributed to any other unit. This prevents double-counting and gives a clean picture of CEI's distinct contribution.
