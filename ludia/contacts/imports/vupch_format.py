import logging

import requests

from ludia.contacts.models import Publication

logger = logging.getLogger(__name__)


def _doi_to_apa(doi: str) -> str | None:
    try:
        resp = requests.get(
            "https://citation.doi.org/format",
            params={"doi": doi, "style": "apa"},
            timeout=5,
        )
        if resp.status_code != 200:
            return None
        return resp.text
    except requests.RequestException:
        logger.exception("Could not convert DOI to APA.")
        return None


def format_doi_publications():
    publications = Publication.objects.exclude(doi="").filter(display_text="")

    for publication in publications:
        doi = publication.doi
        apa = _doi_to_apa(doi)

        if apa is None:
            continue

        publication.doi = doi
        publication.display_text = apa
        publication.save()
