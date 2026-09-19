import logging
import os

from multiqc.base_module import BaseMultiqcModule, ModuleNoSamplesFound

from multiqc.modules.fgbio.collect_duplex_seq_metrics import run_collect_duplex_seq_metrics
from multiqc.modules.fgbio.error_rate_by_read_position import error_rate_by_read_position
from multiqc.modules.fgbio.group_reads_by_umi import run_group_reads_by_umi

log = logging.getLogger(__name__)


class MultiqcModule(BaseMultiqcModule):
    """
    The module currently supports the following tool outputs:

    - [CollectDuplexSeqMetrics](http://fulcrumgenomics.github.io/fgbio/tools/latest/CollectDuplexSeqMetrics.html)
    - [ErrorRateByReadPosition](http://fulcrumgenomics.github.io/fgbio/tools/latest/ErrorRateByReadPosition.html)
    - [GroupReadsByUmi](http://fulcrumgenomics.github.io/fgbio/tools/latest/GroupReadsByUmi.html)
    """

    def __init__(self):
        super().__init__(
            name="fgbio",
            anchor="fgbio",
            target="fgbio",
            href="http://fulcrumgenomics.github.io/fgbio/",
            info="Processing and evaluating data containing UMIs",
            # No publication / DOI // doi=
            license="MIT License",
            license_url="https://github.com/fulcrumgenomics/fgbio/blob/master/LICENSE",
        )

        self.css = {
            "assets/css/multiqc_fgbio.css": os.path.join(
                os.path.dirname(__file__), "assets", "css", "multiqc_fgbio.css"
            )
        }
        self.js = {
            "assets/js/multiqc_fgbio.js": os.path.join(
                os.path.dirname(__file__), "assets", "js", "multiqc_fgbio.js"
            )
        }

        n = dict()

        n["collectduplexseqmetrics"] = run_collect_duplex_seq_metrics(self)
        if n["collectduplexseqmetrics"] > 0:
            log.info(f"Found {n['collectduplexseqmetrics']} collectduplexseqmetrics reports")

        n["errorratebyreadposition"] = error_rate_by_read_position(self)
        if n["errorratebyreadposition"] > 0:
            log.info(f"Found {n['errorratebyreadposition']} errorratebyreadposition reports")

        n["groupreadsbyumi"] = run_group_reads_by_umi(self)
        if n["groupreadsbyumi"] > 0:
            log.info(f"Found {n['groupreadsbyumi']} groupreadsbyumi reports")

        # Exit if we didn't find anything
        if sum(n.values()) == 0:
            raise ModuleNoSamplesFound
