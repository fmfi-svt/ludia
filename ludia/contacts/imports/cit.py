import json
import logging
from pathlib import Path

import requests
from django.conf import settings

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
    "2": "email",
    "1": "phone",
    "6": "room",
}
LANGUAGE_MAPPING = {"sk_SK": LanguageChoices.SK, "en_EN": LanguageChoices.EN}
FMFI_WORKPLACE_ID = 506


def download_exports(store_path: Path):
    """
    Downloads latest exports from CIT API.
    """
    resp = requests.post(
        EXPORT_URL,
        auth=(settings.CIT_API_USERNAME, settings.CIT_API_PASSWORD),
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

        resp = requests.get(url)
        resp.raise_for_status()
        with (store_path / f"{export}.json").open("wb") as f:
            for chunk in resp.iter_content(chunk_size=512):
                f.write(chunk)


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
    for key in contact_keys:
        for contact in contacts[key].values():
            language = LANGUAGE_MAPPING.get(contact["language"], "")
            value = str(contact["value"])

            person_id = wuser_id_to_person_id.get(int(contact["workplace_user_id"]))
            if not person_id:
                logger.warning(
                    f"CIT workplace_user_id {contact['workplace_user_id']} does not have a related Person."
                )
                continue

            contact_type_identifier = CONTACT_MAPPING.get(contact["contact_type_id"])
            if not contact_type_identifier:
                continue

            contact_type_id = contact_type_map.get(contact_type_identifier)
            if not contact_type_id:
                logger.warning(
                    f"Contact type {contact_type_identifier} not found in our database."
                )
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

    to_delete = Contact.objects.filter(source=source).exclude(id__in=present_ids)
    if count := to_delete.count():
        logger.warning(f"Deleting {count} orphaned Contact objects.")
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
        titles[title["id"]] = {
            "en": title["localization"].get("en_EN", {}).get("long_job_title", ""),
            "sk": title["localization"]
            .get("sk_SK", {})
            .get("long_job_title", sap_title),
        }

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
            logger.warning(
                f"User {relation['user_id']} does not have valid workplace for ID {relation['workplace_id']}."
            )
            continue

        person_id = cit_id_to_person_id.get(int(relation["user_id"]))
        if not person_id:
            logger.warning(
                f"CIT user {relation['user_id']} found in relations.json but not in users.json"
            )
            continue

        title = titles.get(int(relation["job_title_id"]), {})
        obj, _ = Relation.objects.update_or_create(
            person_id=person_id,
            cit_id=relation["id"],
            defaults={
                "workplace_id": workplace_id,
                "job_title_sk": title.get("sk", ""),
                "job_title_en": title.get("en", ""),
            },
        )
        present_ids.add(obj.id)

    to_delete = Relation.objects.exclude(id__in=present_ids)
    if count := to_delete.count():
        logger.warning(f"Deleting {count} orphaned Relation objects.")
        to_delete.delete()


def import_workplaces(store_path: Path):
    """
    Imports Workplace objects from CIT data.
    """
    workplace_cit_to_id = {w.cit_id: w.id for w in Workplace.objects.all()}

    with (store_path / "workplaces.json").open() as f:
        workplaces: dict[str, CIT_Workplace] = json.load(f)

    for workplace in workplaces.values():
        workplace_id = workplace["id"]
        tree_path = list(map(int, workplace["treePath"].split(",")[::-1]))

        allowed_path_length = 2
        if FMFI_WORKPLACE_ID in tree_path:
            allowed_path_length = 3

        if len(tree_path) > allowed_path_length:
            continue

        parent = None
        if workplace["parent"]:
            parent = workplace_cit_to_id.get(int(workplace["parent"]))
            if not parent:
                logger.warning(
                    f"Workplace {workplace['id']} does not have parent in our DB."
                )

        obj, _ = Workplace.objects.update_or_create(
            cit_id=workplace_id,
            defaults={
                "name_en": workplace["localization"].get("en_EN", {}).get("title", ""),
                "name_sk": workplace["localization"].get("sk_SK", {}).get("title", ""),
                "parent_id": parent,
            },
        )
        workplace_cit_to_id[obj.cit_id] = obj.id
