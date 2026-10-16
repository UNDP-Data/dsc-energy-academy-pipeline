from __future__ import annotations

import re

from sea_pipeline.shared.config import PipelineConfig

from .runner import run_auxiliary_stage


EXTRA_SPELLCHECK_WHITELIST = {
    # Acronyms / organizations
    "eda",
    "eesi",
    "esmap",
    "esns",
    "fpic",
    "ghg",
    "gis",
    "hbs",
    "inl",
    "irena",
    "lca",
    "mdbs",
    "ncqg",
    "oecd",
    "pim",
    "rmi",
    "unep",
    "unfccc",
    "unicef",
    # Units / abbreviations
    "hr",
    "kv",
    "pp",
    "px",
    "yr",
    # Technical / domain terms
    "actioned",
    "additionality",
    "aggregators",
    "barangays",
    "biodiesel",
    "cashflows",
    "chatbot",
    "conservoltaic",
    "convolutional",
    "corporates",
    "decarbonisation",
    "disincentivize",
    "distortionary",
    "ecooking",
    "ecovoltaic",
    "explainability",
    "feedstocks",
    "firetube",
    "floatovoltaics",
    "fluorinated",
    "foodgrain",
    "geochemically",
    "geospatially",
    "hydrofluorocarbon",
    "islanding",
    "majeure",
    "microcredits",
    "morbidities",
    "nano",
    "norming",
    "offsite",
    "offtake",
    "offtakers",
    "operationalized",
    "peaker",
    "peatland",
    "snowmelt",
    "snowpack",
    "snowpacks",
    "tallgrass",
    "telecom",
    "unbundling",
    "undergrid",
    "upcycled",
    "watertube",
    "wellbore",
    "woodfuel",
    # British / international English variants
    "analysing",
    "categorised",
    "centralised",
    "contextualised",
    "contextualising",
    "harmonised",
    "honour",
    "industrialisation",
    "materialising",
    "mobilisation",
    "mobilise",
    "modernise",
    "neighbouring",
    "optimisation",
    "penalised",
    "prioritisation",
    "prioritises",
    "standardised",
    "sterilisation",
    "visualisation",
    # Requested proper / domain-specific terms
    "highveld",
    "jaalis",
    "watsonx",
    # Foreign-language terms that appear intentionally in cited titles/names.
    "buen",
    "contor",
    "convoca",
    "cooperativahidroelectrica",
    "dans",
    "desarrollo",
    "historia",
    "humano",
    "multiactor",
    "pacto",
    "poderosa",
    "renouvelables",
    "rurale",
    "sostenible",
    "vivir",
}


URL_PATTERN = re.compile(
    r"""
    https?://\S+ |
    www\.\S+ |
    \b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/\S*)? |
    \b[a-zA-Z]{2,}/@?[A-Za-z0-9._~%-]+(?:/[A-Za-z0-9._~%+-]+)+
    """,
    re.VERBOSE,
)


def strip_urls_from_text(text: str) -> str:
    """Remove URLs and URL-like domain/path fragments before spellchecking."""
    return URL_PATTERN.sub(" ", str(text or ""))


def run_spellcheck_audit(config: PipelineConfig) -> dict[str, object]:
    return run_auxiliary_stage(config, "spellcheck_audit")
