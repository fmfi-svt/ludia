import json
import logging
from collections import Counter
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import CommandError

from ludia.contacts.imports.cit_types import (
    CIT_Contact,
    CIT_JobTitle,
    CIT_Relation,
    CIT_SAPJobTitle,
    CIT_User,
    CIT_Workplace,
)
from ludia.contacts.models import (
    Contact,
    ContactType,
    LanguageChoices,
    Person,
    Relation,
    Source,
    Workplace,
)

logger = logging.getLogger(__name__)

EXPORT_URL = "https://cit.uniba.sk/kontakty/index.php/exports_v2/get_export"
EXPORT_DOWNLOAD_LIST = [
    "users",
    "relations",
    "contacts",
    "workplaces",
    "job_titles",
    "sap_job_titles",
]
CONTACT_MAPPING = {
    "1": "phone",
    "2": "email",
    "3": None,  # poznámka
    "4": None,  # fotka
    "6": "room",
    "7": "website",
    "8": "website",  # social
    "9": "phone",  # voip
    "10": None,  # consultation_hours
    "11": "phone",  # uniba_voip
}
LANGUAGE_MAPPING = {"sk_SK": LanguageChoices.SK, "en_EN": LanguageChoices.EN}
WORKPLACE_KEYWORDS = ["fakulta", "katedra", "centrum", "univerzita"]
WORKPLACE_TITLES = ["dekanát"]
DOCTORAL_JOB_TYPE_ID = "5"
SAP_JOB_TITLE_REWRITES = [
    ("profesor", "profesor", "professor"),
    ("docent", "docent", "associate professor"),
    ("vedecký", "vedecký pracovník", "researcher"),
    ("odborný asistent", "odborný asistent", "assistant professor"),
    ("technický asistent", "technický asistent", "technical assistant"),
    ("sekretár", "administratívny pracovník", "administrative worker"),
    ("tajomník", "tajomník", "secretary"),
    (
        "dekan, prodekan",
        "vedenie fakulty (prodekani, dekan)",
        "faculty leadership (vice-deans, dean)",
    ),
]


def download_exports(store_path: Path):
    """
    Downloads latest exports from CIT API.
    """
    resp = requests.post(
        EXPORT_URL,
        data={
            "username": settings.CIT_API_USERNAME,
            "password": settings.CIT_API_PASSWORD,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data: dict = resp.json()

    assert data["status"]

    for export in EXPORT_DOWNLOAD_LIST:
        url: str = data["data"]["urls"][export]
        url = url.replace(
            "/data/exports_v2//data/exports_v2/", "/data/exports_v2/"
        )  # FIXME: remove after upstream fix

        export_path = store_path / f"{export}.json"
        with requests.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with export_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    f.write(chunk)

        # Validate every export
        try:
            with export_path.open("rb") as f:
                json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CommandError(
                f"CIT export {export}.json is not valid JSON: {exc}."
            ) from exc


def import_people(store_path: Path):
    """
    Creates `Person` object for each user in the CIT export.
    """

    with (store_path / "users.json").open() as f:
        users: dict[str, CIT_User] = json.load(f)

    for user in users.values():
        Person.objects.update_or_create(
            university_id=user["uoc"],
            defaults={
                key: (user[key] or "").strip()
                for key in [
                    "login",
                    "first_name",
                    "middle_name",
                    "last_name",
                    "title_before",
                    "title_after",
                ]
            },
        )

    # TODO: handle orphaned Person objects


def _get_cit_id_to_person_id_mapping(store_path: Path) -> dict[int, int]:
    """
    Returns mapping of CIT user IDs to our `Person` IDs.
    """
    login_to_person_id = {p.login: p.id for p in Person.objects.all()}
    cit_id_to_person: dict[int, int] = {}

    with (store_path / "users.json").open() as f:
        users: dict[str, CIT_User] = json.load(f)

    for user in users.values():
        person_id = login_to_person_id.get(user["login"])
        if not person_id:
            logger.warning(
                f"User with login {user['login']} not found in our database."
            )
            continue

        cit_id_to_person[user["id"]] = person_id

    return cit_id_to_person


def _get_workplace_user_id_to_person_id_mapping(store_path: Path) -> dict[int, int]:
    """
    Returns mapping of CIT `workplace_user_id` to our `Person` IDs.
    """
    cit_id_to_person_id = _get_cit_id_to_person_id_mapping(store_path)

    workplace_user_id_to_person_id: dict[int, int] = {}
    with (store_path / "relations.json").open() as f:
        relations: dict[str, CIT_Relation] = json.load(f)
    for relation in relations.values():
        person_id = cit_id_to_person_id.get(int(relation["user_id"]))
        if not person_id:
            continue

        workplace_user_id_to_person_id[relation["id"]] = person_id

    return workplace_user_id_to_person_id


def import_contacts(store_path: Path):
    """
    Imports `Contact` objects from CIT data.
    """
    contact_keys = ["text", "varchar"]
    # Note: contacts.json also contains int and double keys, but they are empty and sadly lists instead of dicts.

    source, _ = Source.objects.get_or_create(identifier="cit")
    wuser_id_to_person_id = _get_workplace_user_id_to_person_id_mapping(store_path)
    contact_type_map = {c.identifier: c.id for c in ContactType.objects.all()}

    with (store_path / "contacts.json").open() as f:
        contacts: dict[str, dict[str, CIT_Contact]] = json.load(f)

    present_ids = set()
    missing_contact_types: Counter[str] = Counter()
    for key in contact_keys:
        for contact in contacts[key].values():
            language = LANGUAGE_MAPPING.get(contact["language"], "")
            value = str(contact["value"])

            contact_type_identifier = CONTACT_MAPPING.get(contact["contact_type_id"])
            if not contact_type_identifier:
                continue

            person_id = wuser_id_to_person_id.get(int(contact["workplace_user_id"]))
            if not person_id:
                logger.debug(
                    "Skipping CIT contact %s: workplace_user_id %s has no mapped Person.",
                    contact["id"],
                    contact["workplace_user_id"],
                )
                continue

            contact_type_id = contact_type_map.get(contact_type_identifier)
            if not contact_type_id:
                missing_contact_types[contact_type_identifier] += 1
                continue

            obj, _ = Contact.objects.update_or_create(
                person_id=person_id,
                source=source,
                source_identifier=str(contact["id"]),
                defaults={
                    "contact_type_id": contact_type_id,
                    "value": value,
                    "language": language,
                },
            )
            present_ids.add(obj.id)

    for identifier, count in missing_contact_types.items():
        logger.warning(
            "Contact type %s not found in our database; skipped %s CIT contacts.",
            identifier,
            count,
        )

    to_delete = Contact.objects.filter(source=source).exclude(id__in=present_ids)
    if count := to_delete.count():
        logger.info(f"Deleting {count} orphaned Contact objects.")
        to_delete.delete()


def _get_workplace_mapping(store_path: Path) -> dict[int, int]:
    """
    Returns mapping between CIT workplace IDs and our Workplaces.
    """
    known_workplaces = {w.cit_id: w.id for w in Workplace.objects.all()}
    cit_workplaces = {}

    with (store_path / "workplaces.json").open() as f:
        workplaces: dict[str, CIT_Workplace] = json.load(f)

    for workplace in workplaces.values():
        workplace_id = workplace["id"]
        tree_path = map(int, workplace["treePath"].split(",")[::-1])

        for item in tree_path:
            if item in known_workplaces:
                cit_workplaces[workplace_id] = known_workplaces[item]
                break

    return cit_workplaces


def _rewrite_sap_job_title(sap_title: str) -> dict[str, str]:
    for match, title_sk, title_en in SAP_JOB_TITLE_REWRITES:
        if match in sap_title:
            return {"sk": title_sk, "en": title_en}

    return {"sk": sap_title, "en": sap_title}


def _get_job_titles(store_path: Path) -> dict[int, dict[str, str]]:
    """
    Returns mapping between job_title_id and the real job title (both translations).
    """
    sap_titles = {}
    with (store_path / "sap_job_titles.json").open() as f:
        sap_title_data: dict[str, CIT_SAPJobTitle] = json.load(f)

    for sap_title in sap_title_data.values():
        sap_titles[sap_title["sap_text_sha1"]] = sap_title["text"]

    titles = {}
    with (store_path / "job_titles.json").open() as f:
        title_data: dict[str, CIT_JobTitle] = json.load(f)

    for title in title_data.values():
        sap_title = sap_titles.get(title["sap_text_hash"], "")
        title_sk = title["localization"].get("sk_SK", {}).get("long_job_title", "")
        title_en = title["localization"].get("en_EN", {}).get("long_job_title", "")
        if title_sk and title_en:
            titles[title["id"]] = {"sk": title_sk, "en": title_en}
        else:
            titles[title["id"]] = _rewrite_sap_job_title(sap_title)

    return titles


def import_relations(store_path: Path):
    """
    Imports Relation objects from CIT relations data.
    """
    workplace_map = _get_workplace_mapping(store_path)
    cit_id_to_person_id = _get_cit_id_to_person_id_mapping(store_path)
    titles = _get_job_titles(store_path)

    with (store_path / "relations.json").open() as f:
        relations: dict[str, CIT_Relation] = json.load(f)

    present_ids = set()
    for relation in relations.values():
        workplace_id = workplace_map.get(int(relation["workplace_id"]))
        if not workplace_id:
            logger.debug(
                "Skipping CIT relation %s: workplace %s has no mapped Workplace.",
                relation["id"],
                relation["workplace_id"],
            )
            continue

        person_id = cit_id_to_person_id.get(int(relation["user_id"]))
        if not person_id:
            logger.warning(
                f"CIT relation {relation['id']} has a mapped workplace but no mapped Person for user {relation['user_id']}."
            )
            continue

        if relation["job_type_id"] == DOCTORAL_JOB_TYPE_ID:
            title = {"sk": "doktorand", "en": "PhD student"}
        else:
            title = titles.get(int(relation["job_title_id"]), {})
        obj, _ = Relation.objects.update_or_create(
            cit_id=relation["id"],
            defaults={
                "person_id": person_id,
                "workplace_id": workplace_id,
                "job_title_sk": title.get("sk", ""),
                "job_title_en": title.get("en", ""),
            },
        )
        present_ids.add(obj.id)

    to_delete = Relation.objects.exclude(id__in=present_ids)
    if count := to_delete.count():
        logger.info(f"Deleting {count} orphaned Relation objects.")
        to_delete.delete()


def _filter_workplaces(store_path: Path) -> list[CIT_Workplace]:
    with (store_path / "workplaces.json").open() as f:
        workplaces: dict[str, CIT_Workplace] = json.load(f)

    filtered_ids = set()
    for workplace in workplaces.values():
        title = workplace["localization"].get("sk_SK", {}).get("title", "").casefold()
        if any(keyword in title for keyword in WORKPLACE_KEYWORDS):
            filtered_ids.add(workplace["id"])

        if any(full_title == title for full_title in WORKPLACE_TITLES):
            filtered_ids.add(workplace["id"])

    filtered: list[CIT_Workplace] = []
    for workplace in workplaces.values():
        if workplace["id"] not in filtered_ids:
            continue
        tree_path = [
            item
            for item in workplace["treePath"].split(",")
            if int(item) in filtered_ids
        ]
        workplace["parent"] = tree_path[-2] if len(tree_path) > 1 else None
        workplace["treePath"] = ",".join(tree_path)
        filtered.append(workplace)

    return filtered


def import_workplaces(store_path: Path):
    """
    Imports Workplace objects from CIT data.
    """
    workplace_cit_to_id = {w.cit_id: w.id for w in Workplace.objects.all()}
    overriden_ids: set[int] = set(
        Workplace.objects.filter(is_overriden=True).values_list("cit_id", flat=True)
    )

    workplaces = _filter_workplaces(store_path)
    touched_ids = set()
    for workplace in workplaces:
        workplace_id = workplace["id"]

        parent = None
        if workplace["parent"]:
            parent = workplace_cit_to_id.get(int(workplace["parent"]))
            if not parent:
                logger.warning(
                    f"Workplace {workplace['id']} does not have parent in our DB."
                )

        defaults = {"parent_id": parent}
        if workplace_id not in overriden_ids:
            defaults["name_en"] = (
                workplace["localization"].get("en_EN", {}).get("title", "")
            )
            defaults["name_sk"] = (
                workplace["localization"].get("sk_SK", {}).get("title", "")
            )

        obj, _ = Workplace.objects.update_or_create(
            cit_id=workplace_id, defaults=defaults
        )
        workplace_cit_to_id[obj.cit_id] = obj.id
        touched_ids.add(obj.id)

    orphans = Workplace.objects.exclude(id__in=touched_ids).values_list("id", flat=True)
    if orphans:
        logger.info(f"Orphaned Workplace objects: {', '.join(map(str, orphans))}.")
