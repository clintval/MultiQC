"""Parse riker `error` outputs (error-mismatch.txt, error-indel.txt, error-overlap.txt).

Each file has one row per (stratifier, covariate) combination, e.g. error rate by base
quality ('bq') or by read cycle. The row where both are 'all' holds the overall metrics for
the sample, and is one reported in general stats. When the `read_num,cycle` or `cycle`
stratifier is present, the mismatch rate is also plotted by cycle, and the first cycle is
summarised against the cycles after it.

"""

import logging
from collections import defaultdict

from multiqc.plots import linegraph

from .util import read_tsv, to_float, to_int

log = logging.getLogger(__name__)

# Cycles pooled as the baseline that the first cycle is compared against.
_BASELINE_CYCLES = range(2, 11)


def parse_reports(module):
    parsed_samples = set()
    parsed_samples |= _parse_mismatch(module)
    # TODO: parse error-indel.txt and error-overlap.txt
    return parsed_samples


def _is_overall_row(row) -> bool:
    """The `all / all` row holds the overall (unstratified) metrics for a sample."""
    return row.get("stratifier") == "all" and row.get("covariate") == "all"


def _cycle_key(row) -> tuple[str | None, int] | None:
    """Return `(read, cycle)` for a `read_num,cycle` or `cycle` row, with read `None` for the latter."""
    stratifier = row.get("stratifier")
    covariate = row.get("covariate", "")
    try:
        if stratifier == "read_num,cycle":
            read, _, cycle = covariate.partition(",")
            return read, to_int(cycle)
        if stratifier == "cycle":
            return None, to_int(covariate)
    except ValueError:
        return None
    return None


def _parse_mismatch(module) -> set:
    data_by_sample: dict[str, dict[str, float | None]] = {}
    # counts_by_sample[sample][read][cycle] = (total_bases, error_bases)
    counts_by_sample: dict[str, dict[str | None, dict[int, tuple[int, int]]]] = {}

    for f in module.find_log_files("riker/error_mismatch", filehandles=True):
        counts_in_file: dict[str, dict[str | None, dict[int, tuple[int, int]]]] = defaultdict(lambda: defaultdict(dict))
        for row in read_tsv(f["f"], source=f["fn"]):
            sample = row.get("sample")
            if not sample:
                continue
            key = _cycle_key(row)
            if key is not None:
                try:
                    counts_in_file[sample][key[0]][key[1]] = (to_int(row["total_bases"]), to_int(row["error_bases"]))
                except (KeyError, TypeError, ValueError) as e:
                    log.warning(f"riker: skipping row in {f['fn']} for sample {sample}: {e}")
                continue
            # skip the other stratified rows, only the overall row is used for the General Stats table.
            if not _is_overall_row(row):
                continue
            s_name = module.clean_s_name(sample, f)
            try:
                data_by_sample[s_name] = {
                    "total_bases": to_int(row["total_bases"]),
                    "error_bases": to_int(row["error_bases"]),
                    "frac_error": to_float(row["frac_error"]),
                    "q_score": to_float(row["q_score"]),
                }
            except (KeyError, TypeError, ValueError) as e:
                log.warning(f"riker: skipping row in {f['fn']} for sample {sample}: {e}")
                continue
            module.add_data_source(f, s_name, section="error_mismatch")

        for sample, by_read in counts_in_file.items():
            s_name = module.clean_s_name(sample, f)
            # Prefer read 1 / read 2 rows over the pooled `cycle` rows when riker wrote both.
            reads = {r: c for r, c in by_read.items() if r is not None} or dict(by_read)
            counts_by_sample[s_name] = reads

    data_by_sample = module.ignore_samples(data_by_sample)
    if not data_by_sample:
        return set()

    module.add_software_version(None)

    for s_name, data in data_by_sample.items():
        data.update(_first_cycle_summary(counts_by_sample.get(s_name, {})))

    headers = {
        "frac_error": {
            "title": "Mismatch rate",
            "description": "Percentage of aligned bases that mismatch the reference (riker error)",
            "min": 0,
            "suffix": "%",
            # riker reports a fraction and shows it as a percentage
            "modify": lambda x: x * 100 if x is not None else None,
            "format": "{:,.3f}",
            "scale": "OrRd",
        },
        "q_score": {
            "title": "Mismatch Q",
            "description": "Mismatch error rate as a Phred-scaled quality score (higher is better)",
            "min": 0,
            "format": "{:,.1f}",
            "scale": "RdYlGn",
            # same information as the mismatch rate, so it is hidden by default.
            "hidden": True,
        },
        "cycle1_frac_error": {
            "title": "Cycle 1 mismatch",
            "description": "Percentage of bases at the first cycle of each read that mismatch the reference",
            "min": 0,
            "suffix": "%",
            "modify": lambda x: x * 100 if x is not None else None,
            "format": "{:,.3f}",
            "scale": "OrRd",
            "hidden": True,
        },
        "cycle1_fold": {
            "title": "Cycle 1 fold",
            "description": "Mismatch rate at cycle 1 divided by the pooled mismatch rate at cycles 2 to 10",
            "min": 0,
            "suffix": "x",
            "format": "{:,.2f}",
            "scale": "OrRd",
            "hidden": True,
        },
    }
    module.general_stats_addcols(data_by_sample, headers, namespace="error")
    module.write_data_file(data_by_sample, f"multiqc_{module.anchor}_error_mismatch")
    _add_by_cycle_section(module, {s: counts_by_sample[s] for s in data_by_sample if s in counts_by_sample})
    return set(data_by_sample.keys())


def _first_cycle_summary(by_read: dict[str | None, dict[int, tuple[int, int]]]) -> dict[str, float | None]:
    """Mismatch rate at cycle 1, and its fold over cycles 2 to 10, with every read pooled."""
    pooled: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for by_cycle in by_read.values():
        for cycle, (total, errors) in by_cycle.items():
            pooled[cycle][0] += total
            pooled[cycle][1] += errors

    first_total, first_errors = pooled.get(1, (0, 0))
    first = first_errors / first_total if first_total > 0 else None
    baseline_total = sum(pooled[c][0] for c in _BASELINE_CYCLES if c in pooled)
    baseline_errors = sum(pooled[c][1] for c in _BASELINE_CYCLES if c in pooled)
    baseline = baseline_errors / baseline_total if baseline_total > 0 else None
    return {
        "cycle1_frac_error": first,
        "cycle1_fold": first / baseline if first is not None and baseline else None,
    }


def _add_by_cycle_section(module, counts_by_sample: dict[str, dict[str | None, dict[int, tuple[int, int]]]]) -> None:
    by_cycle: dict[str, dict[int, float]] = {}
    for s_name, by_read in counts_by_sample.items():
        for read, cycles in by_read.items():
            label = s_name if read is None else f"{s_name}_{read}"
            by_cycle[label] = {c: 100 * e / t for c, (t, e) in sorted(cycles.items()) if t > 0}
    by_cycle = {label: rates for label, rates in by_cycle.items() if rates}
    if not by_cycle:
        return

    pconfig = {
        "id": f"{module.anchor}_error_mismatch_by_cycle",
        "title": f"{module.name}: Mismatch rate by cycle",
        "ylab": "Mismatch rate (%)",
        "xlab": "Cycle",
        "x_decimals": False,
        "ymin": 0,
        "tt_label": "<b>cycle {point.x}</b>: {point.y:.4f} %",
    }
    module.add_section(
        name="Mismatch rate by cycle",
        anchor=f"{module.anchor}-error-mismatch-by-cycle",
        description="Percentage of aligned bases that mismatch the reference at each cycle, from riker's `error` tool.",
        helptext="""
            Riker's `error` tool compares every aligned base that passes its mapping and base
            quality filters to the reference. Cycle 1 is the first base of the read as sequenced.
            When riker is run with the `read_num,cycle` stratifier, read 1 and read 2 are shown as
            separate `_R1` / `_R2` samples.

            A spike at the first cycles points to damage or misincorporation at fragment ends, for
            example from end repair or gap filling during library preparation. Known variant sites
            are only excluded when riker was given a VCF, so germline variants add a flat offset to
            every cycle.
        """,
        plot=linegraph.plot(by_cycle, pconfig),
    )
