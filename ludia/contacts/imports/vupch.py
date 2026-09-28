import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.db import transaction

from ludia.contacts.models import Person, Publication

EXAMPLE = "https://ais2.uniba.sk/repo2/repository/default/ais/zamestnanec/FMFI/SK/suppa1.uniba.sk.xml"
REPO_ROOT = "https://ais2.uniba.sk/repo2/repository/default/ais/zamestnanec/"
REQUEST_TIMEOUT = 30
DOI_PATTERN = re.compile(r"10.\d{4,9}/[-._;()/:A-Z0-9]+(?<!\.)", re.IGNORECASE)
ORCID_PATTERN = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b", re.IGNORECASE)

logger = logging.getLogger(__name__)


@dataclass
class VUPCHData:
    orcid: str
    publications: list[str]


def _strip_html(value: str) -> str:
    """Convert a VUPCH HTML fragment to normalized plain text."""
    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    return " ".join(text.split())


def _find_section(entries: list[ET.Element], code: str) -> int | None:
    """Return the index of a VUPCH section entry identified by its code."""
    for index, entry in enumerate(entries):
        if entry.findtext("kod") == code:
            return index
    return None


def parse_vupch(contents: str) -> VUPCHData:
    """Extract an ORCID and selected creative-output publications from VUPCH XML."""
    root = ET.fromstring(contents)
    entries = root.findall("popisOsoby")

    orcid_index = _find_section(entries, "I.11")
    orcid = (
        _extract_orcid(entries[orcid_index].findtext("text") or "")
        if orcid_index is not None
        else ""
    )

    section_index = _find_section(entries, "VI.3")
    if section_index is None:
        section_index = _find_section(entries, "VI.2")

    publications: list[str] = []
    if section_index is not None:
        for entry in entries[section_index + 1 :]:
            if entry.find("kod") is not None:
                break
            if text := entry.findtext("text"):
                if publication := _strip_html(text):
                    publications.append(publication)

    return VUPCHData(orcid=orcid, publications=publications)


def _directory_links(url: str) -> list[tuple[str, str]]:
    """Fetch a repository directory listing and return its link labels and URLs."""
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    page = BeautifulSoup(response.text, "html.parser")
    return [
        (link.get_text(strip=True), urljoin(url, href))
        for link in page.find_all("a")
        if (href := link.get("href"))
    ]


def _extract_login(url: str) -> str | None:
    """Derive a person's login from a ``<login>.uniba.sk.xml`` URL."""
    filename = urlparse(url).path.rsplit("/", maxsplit=1)[-1]
    suffix = ".uniba.sk.xml"
    if not filename.endswith(suffix):
        return None
    return filename.removesuffix(suffix)


def _extract_doi(publication: str) -> str:
    """Return the first DOI found in a publication citation, if any."""
    match = DOI_PATTERN.search(publication)
    return match.group() if match else ""


def _extract_orcid(value: str) -> str:
    """Return an ORCID identifier from a bare value or an ORCID URL."""
    match = ORCID_PATTERN.search(value)
    return match.group() if match else ""


def _import_person_vupch(person, data: VUPCHData, vupch_url: str):
    """Synchronize one person's ORCID, VUPCH URL, and publications."""

    with transaction.atomic():
        person.orcid = data.orcid
        person.vupch_url = vupch_url
        person.save(update_fields=["orcid", "vupch_url"])

        publication_ids = set()
        for raw_text in data.publications:
            publication, _ = Publication.objects.update_or_create(
                person=person,
                raw_text=raw_text,
                defaults={"doi": _extract_doi(raw_text)},
            )
            publication_ids.add(publication.id)

        Publication.objects.filter(person=person).exclude(
            id__in=publication_ids
        ).delete()


def _list_faculty_urls() -> list[str]:
    """List the faculty directories directly below the VUPCH repository root."""
    try:
        return [url for name, url in _directory_links(REPO_ROOT) if name != ".."]
    except requests.RequestException:
        logger.exception("Could not fetch VUPCH repository root.")
        return []


def _list_user_xml_urls(faculty_url: str) -> list[str]:
    """List VUPCH XML files in a faculty's Slovak-language directory."""
    try:
        faculty_links = _directory_links(faculty_url)
    except requests.RequestException:
        logger.exception("Could not fetch VUPCH faculty directory %s.", faculty_url)
        return []

    sk_url = next(
        (url for name, url in faculty_links if name == "SK"),
        None,
    )
    if not sk_url:
        logger.warning("VUPCH faculty directory %s has no SK directory.", faculty_url)
        return []

    try:
        user_links = _directory_links(sk_url)
    except requests.RequestException:
        logger.exception("Could not fetch VUPCH SK directory %s.", sk_url)
        return []

    return [url for _, url in user_links if urlparse(url).path.endswith(".xml")]


def _import_vupch_file(xml_url: str):
    """Download, parse, and persist VUPCH data from one user XML file."""
    login = _extract_login(xml_url)
    if not login:
        return

    person = Person.objects.filter(login=login).first()
    if not person:
        logger.warning("VUPCH user %s does not exist in the local database.", login)
        return

    try:
        response = requests.get(xml_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = parse_vupch(response.text)
    except (ET.ParseError, requests.RequestException):
        logger.exception("Could not import VUPCH XML %s.", xml_url)
        return

    vupch_url = xml_url.removesuffix(".xml") + ".html"
    _import_person_vupch(person, data, vupch_url)


def import_vupch():
    """Import VUPCH data for people available in the local database."""
    seen_logins: set[str] = set()

    for faculty_url in _list_faculty_urls():
        for xml_url in _list_user_xml_urls(faculty_url):
            login = _extract_login(xml_url)
            if not login or login in seen_logins:
                continue
            seen_logins.add(login)

            _import_vupch_file(xml_url)
