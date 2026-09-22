import xml.etree.ElementTree as ET

import requests

from ludia.contacts.models import Lesson, Person

CANDLE_URL = "https://candle.fmph.uniba.sk/data.xml"
DAYS = {"Po": 0, "Ut": 1, "St": 2, "Št": 3, "Pi": 4, "So": 5, "Ne": 6}


def import_timetables():
    resp = requests.get(CANDLE_URL)
    resp.raise_for_status()

    people = Person.objects.in_bulk(field_name="login")
    present_ids = set()
    for lesson in ET.fromstring(resp.content).findall("lesson"):
        teachers = lesson.findall("teacher")
        defaults = {
            "day_of_week": DAYS[lesson.findtext("day") or ""],
            "start_time": lesson.findtext("start"),
            "end_time": lesson.findtext("end"),
            "teachers": ", ".join(teacher.text for teacher in teachers if teacher.text),
            "type": lesson.findtext("type") or "",
            "room": lesson.findtext("room") or "",
            "subject_name": lesson.findtext("subject") or "",
            "subject_code": lesson.findtext("subject_code") or "",
            "note": lesson.findtext("note") or "",
        }
        for teacher in teachers:
            login = teacher.attrib.get("login")
            if login and (person := people.get(login)):
                obj, _ = Lesson.objects.update_or_create(
                    person=person, candle_id=lesson.attrib["id"], defaults=defaults
                )
                present_ids.add(obj.id)

    Lesson.objects.exclude(id__in=present_ids).delete()
