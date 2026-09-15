import json
import logging
from pathlib import Path

import requests
from django.conf import settings

from ludia.contacts.models import Contact, ContactType, LanguageChoices, Person, Source

logger = logging.getLogger(__name__)

EXPORT_URL = "https://cit.uniba.sk/kontakty/index.php/exports_v2/get_export"
EXPORT_DOWNLOAD_LIST = [
    "users",
    "relations",
    "contacts",
]
CONTACT_MAPPING = {
    "2": "email",
    "1": "phone",
    "6": "room",
}
LANGUAGE_MAPPING = {"sk_SK": LanguageChoices.SK, "en_EN": LanguageChoices.EN}


def download_exports(store_path: Path):
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
    import_keys = [
        "login",
        "first_name",
        "middle_name",
        "last_name",
        "title_before",
        "title_after",
    ]

    with (store_path / "users.json").open() as f:
        users: dict = json.load(f)

    for user in users.values():
        Person.objects.update_or_create(
            university_id=user["uoc"],
            defaults={key: (user[key] or "").strip() for key in import_keys},
        )

    # TODO: handle orphaned Person objects


def _get_cit_id_to_login_mapping(store_path: Path) -> dict[int, str]:
    """
    Returns mapping of CIT user IDs to UNIBA UIDs (login).
    """
    cit_id_to_login: dict[int, str] = {}

    with (store_path / "users.json").open() as f:
        users: dict = json.load(f)

    for user in users.values():
        cit_id_to_login[user["id"]] = user["login"]

    return cit_id_to_login


def _get_workplace_user_id_to_person_id_mapping(store_path: Path) -> dict[int, int]:
    """
    Returns mapping of CIT `workplace_user_id` to our `Person` IDs.
    """
    cit_id_to_login = _get_cit_id_to_login_mapping(store_path)
    login_to_person_id = {p.login: p.id for p in Person.objects.all()}

    workplace_user_id_to_person_id: dict[int, int] = {}
    with (store_path / "relations.json").open() as f:
        relations: dict = json.load(f)
    for relation in relations.values():
        login = cit_id_to_login.get(int(relation["user_id"]))
        if not login:
            logger.warning(
                f"CIT user {relation['user_id']} is present in relations.json, but not in users.json."
            )
            continue

        person_id = login_to_person_id.get(login)
        if not person_id:
            logger.warning(f"User with login {login} not found in our database.")
            continue

        workplace_user_id_to_person_id[relation["id"]] = person_id

    return workplace_user_id_to_person_id


def import_contacts(store_path: Path):
    contact_keys = ["text", "varchar"]
    # Note: contacts.json also contains int and double keys, but they are empty and sadly lists instead of dicts.

    source, _ = Source.objects.get_or_create(identifier="cit")
    wuser_id_to_person_id = _get_workplace_user_id_to_person_id_mapping(store_path)
    contact_type_map = {c.identifier: c.id for c in ContactType.objects.all()}

    with (store_path / "contacts.json").open() as f:
        contacts: dict = json.load(f)

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

            Contact.objects.update_or_create(
                person_id=person_id,
                source=source,
                source_identifier=str(contact["id"]),
                defaults={
                    "contact_type_id": contact_type_id,
                    "value": value,
                    "language": language,
                },
            )

    # TODO: handle orphaned Contact objects
