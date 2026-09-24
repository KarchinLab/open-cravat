"""Fallback category assignments for result viewer widgets.

Widget JavaScript can provide its own ``categories`` for each result level. These
assignments are sent with the widget list only as a fallback for older widgets
that do not yet declare categories themselves.
"""


WIDGET_CATEGORIES = {
    "allele_frequency": [
        "wgabraom",
        "wgallelefrequency",
        "wgesp6500",
        "wgexac_gene",
        "wggnomad",
        "wggnomad3",
        "wggnomad_gene",
        "wgthousandgenomes",
        "wgthousandgenomes_ad_mixed_american",
        "wgthousandgenomes_african",
        "wgthousandgenomes_east_asian",
        "wgthousandgenomes_european",
        "wgthousandgenomes_south_asian",
        "wguk10k_cohort",
    ],
    "cancer": [
        "wgcancer_genome_interpreter",
        "wgcancer_hotspots",
        "wgcivic",
    ],
    "drugs": [
        "wgcancer_genome_interpreter",
        "wgcivic",
        "wgdgi",
        "wgpharmgkb",
        "wgtarget",
    ],
    "evolution": ["wgphastcons", "wgphylop"],
    "gene": [
        "wgintact",
        "wgncbigene",
        "wgaloft",
        "wgbiogrid",
        "wgclingen",
        "wggo",
        "wghpo",
        "wgpangalodb",
    ],
    "gwas": ["wggrasp", "wggwas_catalog"],
    "haplotypes": [
        "wghaploreg_afr",
        "wghaploreg_amr",
        "wghaploreg_asn",
        "wghaploreg_eur",
        "wghaplotypes",
    ],
    "home": ["wgbase"],
    "igv": ["wgigv"],
    "mendellian_disease": ["wgcgd", "wgclinvar"],
    "non_coding_regulation": ["wgencode_tfbs", "wgenhancer", "wggtex"],
    "predictor": [
        "wgalphamissense",
        "wgbayesdel",
        "wgcadd",
        "wgcadd_exome",
        "wgchasmplus",
        "wgdann",
        "wgdann_coding",
        "wgditto",
        "wgesm1b",
        "wgfathmm",
        "wgfathmm_mkl",
        "wgfathmm_xf_coding",
        "wgfunseq2",
        "wgmutation_assessor",
        "wgmutationtaster",
        "wgmutpred1",
        "wgphdsnpg",
        "wgpolyphen2",
        "wgprimateai",
        "wgprovean",
        "wgrevel",
        "wgsift",
        "wgsiphy",
        "wgvarity_r",
        "wgvest",
    ],
    "protein": [
        "wglollipop",
        "wginterpro",
        "wgswissprot_binding",
        "wgswissprot_domains",
        "wgswissprot_ptm",
    ],
}


def get_widget_categories(widget_name):
    """Return all fallback categories assigned to a widget module."""
    return [
        category
        for category, widget_names in WIDGET_CATEGORIES.items()
        if widget_name in widget_names
    ]
