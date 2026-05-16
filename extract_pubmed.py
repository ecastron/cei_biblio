"""
Extract PubMed metadata from 7 JSON files, apply CEI exclusivity rule,
filter year >= 2020, and save to CSV.
"""
import json
import csv
import os

FILES = [
    ("/root/.claude/projects/-home-user-cei-biblio/f7cb6df4-7d2f-469b-840b-297b4e066da2/tool-results/mcp-ac045379-1568-4a96-9085-db64693aa329-get_article_metadata-1778940921608.txt", "CEI"),
    ("/root/.claude/projects/-home-user-cei-biblio/f7cb6df4-7d2f-469b-840b-297b4e066da2/tool-results/mcp-ac045379-1568-4a96-9085-db64693aa329-get_article_metadata-1778940924618.txt", "Fac. Ciencias de la Salud"),
    ("/root/.claude/projects/-home-user-cei-biblio/f7cb6df4-7d2f-469b-840b-297b4e066da2/tool-results/mcp-ac045379-1568-4a96-9085-db64693aa329-get_article_metadata-1778940933449.txt", "Inst. Ciencias Biológicas"),
    ("/root/.claude/projects/-home-user-cei-biblio/f7cb6df4-7d2f-469b-840b-297b4e066da2/tool-results/mcp-ac045379-1568-4a96-9085-db64693aa329-get_article_metadata-1778940943006.txt", "Fac. Ciencias Agrarias"),
    ("/root/.claude/projects/-home-user-cei-biblio/f7cb6df4-7d2f-469b-840b-297b4e066da2/tool-results/mcp-ac045379-1568-4a96-9085-db64693aa329-get_article_metadata-1778940953705.txt", "Inst. Química R. Naturales"),
    ("/root/.claude/projects/-home-user-cei-biblio/f7cb6df4-7d2f-469b-840b-297b4e066da2/tool-results/mcp-ac045379-1568-4a96-9085-db64693aa329-get_article_metadata-1778940961268.txt", "Fac. Medicina"),
    ("/root/.claude/projects/-home-user-cei-biblio/f7cb6df4-7d2f-469b-840b-297b4e066da2/tool-results/mcp-ac045379-1568-4a96-9085-db64693aa329-get_article_metadata-1778940965502.txt", "Fac. Ingeniería"),
]

OUTPUT_CSV = "/home/user/cei_biblio/pubmed_data.csv"

def extract_articles(filepath, unit):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = []
    for art in data.get("articles", []):
        # Get pmid
        identifiers = art.get("identifiers", {})
        pmid = identifiers.get("pmid", "")
        if not pmid:
            continue

        # Get year
        pub_date = art.get("publication_date", {})
        year_str = pub_date.get("year", "")
        try:
            year = int(year_str)
        except (ValueError, TypeError):
            continue

        # Get journal name
        journal_info = art.get("journal", {})
        journal_name = journal_info.get("title", "Unknown")

        rows.append({
            "pmid": pmid,
            "unit": unit,
            "year": year,
            "journal": journal_name,
        })
    return rows


def main():
    # First pass: collect all CEI pmids
    cei_pmids = set()
    all_unit_rows = []

    for filepath, unit in FILES:
        rows = extract_articles(filepath, unit)
        all_unit_rows.append((unit, rows))
        if unit == "CEI":
            for r in rows:
                cei_pmids.add(r["pmid"])

    print(f"CEI PMIDs collected: {len(cei_pmids)}")

    # Second pass: apply CEI exclusivity rule + filter year >= 2020
    final_rows = []
    for unit, rows in all_unit_rows:
        for r in rows:
            if unit != "CEI" and r["pmid"] in cei_pmids:
                continue  # Remove PMIDs that belong to CEI
            if r["year"] >= 2020:
                final_rows.append(r)

    print(f"Total rows after filtering: {len(final_rows)}")

    # Count per unit
    unit_counts = {}
    for r in final_rows:
        unit_counts[r["unit"]] = unit_counts.get(r["unit"], 0) + 1
    for u, c in sorted(unit_counts.items()):
        print(f"  {u}: {c}")

    # Write CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["pmid", "unit", "year", "journal"])
        writer.writeheader()
        writer.writerows(final_rows)

    print(f"\nCSV saved to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
