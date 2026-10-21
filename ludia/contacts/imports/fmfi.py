import csv
from typing import TextIO

from ludia.contacts.models import Contact, ContactType, Person, Source


def import_contacts(reader: TextIO) -> None:
    """Import FMFI contacts from an open CSV text stream."""
    people = Person.objects.in_bulk(field_name="login")
    contact_types = {
        contact_type.identifier: contact_type.id
        for contact_type in ContactType.objects.filter(
            identifier__in=("phone", "email", "room", "website")
        )
    }
    source, _ = Source.objects.get_or_create(identifier="fmfi")
    present_ids = set()

    for row in csv.DictReader(reader):
        login = (row["log"] or "").strip()
        if not login or (person := people.get(login)) is None:
            continue

        pavilion = (row["pavil"] or "").strip()
        room_number = (row["miestn"] or "").strip()
        values = {
            "phone": (row["klapka"] or "").strip(),
            "email": (row["email"] or "").strip(),
            "room": f"{pavilion} - {room_number}" if pavilion and room_number else "",
            "website": (row["web"] or "").strip(),
        }
        for identifier, value in values.items():
            if not value:
                continue
            contact, _ = Contact.objects.update_or_create(
                person=person,
                source=source,
                source_identifier=f"{identifier}:{value}",
                defaults={"contact_type_id": contact_types[identifier], "value": value},
            )
            present_ids.add(contact.id)

    Contact.objects.filter(source=source).exclude(id__in=present_ids).delete()
