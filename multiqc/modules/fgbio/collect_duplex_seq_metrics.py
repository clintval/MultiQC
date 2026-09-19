import json
import logging
import math
from typing import Dict, List

from multiqc import BaseMultiqcModule, report

log = logging.getLogger(__name__)


def run_collect_duplex_seq_metrics(module: BaseMultiqcModule) -> int:
    """Parse output from fgbio CollectDuplexSeqMetrics (family_sizes.txt)."""
    data = _parse_family_sizes(module)
    if not data:
        return 0

    _add_family_size_section(module, data)
    _add_general_stats(module, data)
    return len(data)


def _parse_family_sizes(module: BaseMultiqcModule) -> Dict[str, List[Dict]]:
    """Parse family_sizes.txt files produced by CollectDuplexSeqMetrics.

    Each row has columns: family_size, cs_count, cs_fraction, ...,
    ss_count, ss_fraction, ..., ds_count, ds_fraction, ...

    Orphaned SSCS count = ss_count - ds_count (single-strand families
    that have no duplex partner).
    """
    parsed: Dict[str, List[Dict]] = {}

    for f in module.find_log_files("fgbio/collectduplexseqmetrics_familysizes"):
        module.add_data_source(f)
        s_name = f["s_name"]
        rows: List[Dict] = []
        for line in f["f"].splitlines():
            if line.startswith("family_size"):
                continue
            fields = line.split("\t")
            if len(fields) < 10:
                continue
            family_size = int(fields[0])
            ss_count = int(float(fields[4]))
            ds_count = int(float(fields[7]))
            orphan_count = max(0, ss_count - ds_count)
            rows.append({
                "family_size": family_size,
                "ss_count": ss_count,
                "ds_count": ds_count,
                "orphan_count": orphan_count,
            })

        if rows:
            parsed[s_name] = rows
        module.add_software_version(None, s_name)

    parsed = module.ignore_samples(parsed)
    return parsed


def _compute_max_family_size(data: Dict[str, List[Dict]]) -> int:
    """Compute the 95th percentile family size across all samples.

    Uses cumulative sums to avoid materializing per-read lists.
    """
    fs_counts: Dict[int, int] = {}
    for rows in data.values():
        for r in rows:
            count = r["ds_count"] + r["orphan_count"]
            fs = r["family_size"]
            fs_counts[fs] = fs_counts.get(fs, 0) + count
    if not fs_counts:
        return 20
    total = sum(fs_counts.values())
    threshold = math.ceil(0.95 * total)
    cumulative = 0
    for fs in sorted(fs_counts.keys()):
        cumulative += fs_counts[fs]
        if cumulative >= threshold:
            return max(fs, 5)
    return max(max(fs_counts.keys()), 5)


def _add_family_size_section(module: BaseMultiqcModule, data: Dict[str, List[Dict]]) -> None:
    """Add a heatmap + stacked bar chart section (FastQC Per Base Sequence Content style).

    Default view: canvas heatmap with samples as rows and family sizes as columns,
    colored by total read fraction intensity.
    Click a row: Plotly stacked bar chart for that sample (duplex vs orphaned SSCS).
    """
    max_fs = _compute_max_family_size(data)

    plot_data: Dict[str, Dict[int, Dict[str, float]]] = {}
    for s_name, rows in data.items():
        total_reads = sum(
            (r["ds_count"] + r["orphan_count"]) * r["family_size"]
            for r in rows
        )
        if total_reads == 0:
            continue

        sample_plot = {}
        for row in rows:
            fs = row["family_size"]
            if fs > max_fs:
                continue
            duplex_reads = row["ds_count"] * fs
            orphan_reads = row["orphan_count"] * fs
            sample_plot[fs] = {
                "duplex_frac": duplex_reads / total_reads,
                "orphan_frac": orphan_reads / total_reads,
            }
        plot_data[s_name] = sample_plot

    if not plot_data:
        return

    anchor = report.save_htmlid(f"{module.anchor}_family_size_heatmap_plot")
    dump = json.dumps([module.anchor, plot_data])
    html = f"""<div id="fgbio_family_size_plot_div">
        <div class="alert alert-info">
           <span class="material-symbols-outlined" style="font-size:16px;vertical-align:text-bottom;">touch_app</span>
           Click a sample row to see a stacked bar chart for that dataset.
        </div>
        <h5><span class="s_name text-primary">Rollover for sample name</span></h5>
        <div class="fgbio_family_size_heatmap_key">
            Family Size: <span id="fgbio_heatmap_key_pos">-</span>
            <div><span id="fgbio_heatmap_key_duplex"> Duplex: <span>-</span></span></div>
            <div><span id="fgbio_heatmap_key_orphan"> Orphan: <span>-</span></span></div>
        </div>
        <div id="fgbio_family_size_heatmap_div" class="fgbio-overlay-plot">
            <div id="{anchor}" class="fgbio_family_size_heatmap_plot hc-plot has-custom-export">
                <canvas id="fgbio_family_size_heatmap" height="100%" width="800px" style="width:100%;"></canvas>
            </div>
        </div>
        <div class="fgbio_family_size_legend">
            <span class="fgbio-legend-swatch" style="background:#1b3a5c;"></span> High read fraction
            <span style="margin-left:16px;"></span>
            <span class="fgbio-legend-swatch" style="background:#ffffff;border:1px solid #ccc;"></span> Low read fraction
        </div>
        <div class="clearfix"></div>
    </div>
    <script type="application/json" class="fgbio_family_size_data">{dump}</script>
    """

    module.add_section(
        name="CollectDuplexSeqMetrics: Family Sizes",
        anchor="fgbio-collectduplexseqmetrics-familysizes",
        description=(
            "Distribution of raw reads across SSCS family sizes from "
            "<code>CollectDuplexSeqMetrics</code>. Hover to see values; click a "
            "sample to see its stacked bar chart."
        ),
        helptext="""
        The heatmap shows the fraction of total raw reads at each family size,
        with one row per sample. Darker colors indicate a higher fraction of
        reads at that family size. Click a sample to see a detailed stacked
        bar chart.

        In the per-sample bar chart, each bar is split into two stacked
        components:

        - **Duplex SSCS** (dark navy): families where both strands (AB and BA)
          are present, forming a complete duplex consensus.
        - **Orphaned SSCS** (teal): families where only one strand is present,
          so no duplex consensus can be formed.

        The family size is the number of raw reads grouped to form a single
        SSCS. Peak annotations mark the family size with the highest read
        fraction.
        """,
        content=html,
    )

    module.write_data_file(
        {s: {r["family_size"]: r for r in rows} for s, rows in data.items()},
        "fgbio_duplex_family_sizes",
    )


def _add_general_stats(module: BaseMultiqcModule, data: Dict[str, List[Dict]]) -> None:
    """Add duplex rate and mean family size to the general stats table."""
    stats = {}
    for s_name, rows in data.items():
        total_ss = sum(r["ss_count"] for r in rows)
        total_ds = sum(r["ds_count"] for r in rows)
        duplex_rate = total_ds / total_ss if total_ss > 0 else 0.0

        weighted_sum = sum(r["ss_count"] * r["family_size"] for r in rows)
        mean_family_size = weighted_sum / total_ss if total_ss > 0 else 0.0

        stats[s_name] = {
            "duplex_rate": duplex_rate,
            "mean_family_size": mean_family_size,
        }

    headers = {
        "duplex_rate": {
            "title": "Duplex Rate",
            "description": "Fraction of SSCS families that are part of a duplex consensus",
            "min": 0,
            "max": 1,
            "scale": "RdYlGn",
            "format": "{:,.3f}",
        },
        "mean_family_size": {
            "title": "Mean Fam. Size",
            "description": "Mean SSCS family size (weighted by family count)",
            "min": 0,
            "scale": "Blues",
            "format": "{:,.1f}",
        },
    }
    module.general_stats_addcols(stats, headers)
