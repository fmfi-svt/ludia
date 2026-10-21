import json
import shutil
from datetime import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import requests
from django.test import TestCase

from ludia.contacts.imports import candle, cit, fmfi, vupch
from ludia.contacts.models import (
    Contact,
    ContactType,
    Lesson,
    Person,
    Publication,
    Relation,
    Source,
    Workplace,
)

DATA = Path(__file__).with_name("test_data")


class ImportTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.person = Person.objects.create(
            university_id=1001, login="novak", first_name="Jana", last_name="Nováková"
        )
        for identifier in ("phone", "email", "room", "website"):
            ContactType.objects.create(
                identifier=identifier, name_sk=identifier, name_en=identifier
            )

    def stale_contact(self, source_identifier):
        source, _ = Source.objects.get_or_create(identifier=source_identifier)
        return Contact.objects.create(
            person=self.person,
            source=source,
            contact_type=ContactType.objects.get(identifier="email"),
            source_identifier="stale",
            value="stale@example.test",
        )


class CITImportTests(ImportTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Path(directory.name)
        shutil.copytree(DATA / "cit", self.store, dirs_exist_ok=True)

    def change_export(self, name, transform):
        path = self.store / f"{name}.json"
        data = json.loads(path.read_text())
        transform(data)
        path.write_text(json.dumps(data))

    def import_all(self):
        cit.import_people(self.store)
        cit.import_workplaces(self.store)
        cit.import_relations(self.store)
        cit.import_contacts(self.store)

    def test_import_is_repeatable_and_maps_workplace_ancestors(self):
        self.import_all()
        self.import_all()
        self.person.refresh_from_db()
        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(self.person.first_name, "Jana")
        self.assertEqual(self.person.middle_name, "")
        self.assertEqual(Workplace.objects.count(), 2)
        department = Workplace.objects.get(cit_id=507)
        self.assertEqual(department.parent.cit_id, cit.FMFI_CIT_ID)
        relation = Relation.objects.get(person=self.person)
        self.assertEqual(relation.workplace, department)
        self.assertEqual(relation.job_title_sk, "doktorand")
        self.assertEqual(relation.job_title_en, "PhD student")
        self.assertEqual(Contact.objects.count(), 2)
        email = Contact.objects.get(contact_type__identifier="email")
        self.assertEqual(email.value, "jana@example.test")
        self.assertEqual(email.language, "SK")

    def test_all_phd_categories_override_study_program_title(self):
        cit.import_workplaces(self.store)
        for job_type in ("5", "6", "7"):
            with self.subTest(job_type=job_type):
                self.change_export(
                    "relations", lambda data: data["201"].update(job_type_id=job_type)
                )
                cit.import_relations(self.store)
                relation = Relation.objects.get(cit_id=201)
                self.assertEqual(relation.job_title_sk, "doktorand")
                self.assertEqual(relation.job_title_en, "PhD student")

    def test_non_phd_title_and_existing_person_are_updated(self):
        self.import_all()
        self.change_export(
            "relations", lambda data: data["201"].update(job_type_id="4")
        )
        self.change_export(
            "users", lambda data: data["101"].update(last_name="Updated")
        )
        self.import_all()
        self.person.refresh_from_db()
        self.assertEqual(self.person.last_name, "Updated")
        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(Relation.objects.get(cit_id=201).job_title_sk, "1.dINF")

    def test_workplace_name_override_is_preserved(self):
        cit.import_workplaces(self.store)
        workplace = Workplace.objects.get(cit_id=507)
        workplace.name_sk = "Custom department"
        workplace.is_overriden = True
        workplace.save()
        cit.import_workplaces(self.store)
        workplace.refresh_from_db()
        self.assertEqual(workplace.name_sk, "Custom department")

    def test_missing_relations_and_contacts_are_removed_only_from_cit(self):
        self.import_all()
        other_contact = self.stale_contact("fmfi")
        self.change_export("relations", lambda data: data.clear())
        self.change_export("contacts", lambda data: data.update(text={}, varchar={}))
        cit.import_relations(self.store)
        cit.import_contacts(self.store)
        self.assertFalse(Relation.objects.exists())
        self.assertFalse(Contact.objects.filter(source__identifier="cit").exists())
        self.assertTrue(Contact.objects.filter(pk=other_contact.pk).exists())

    def test_unknown_contact_type_and_unmapped_person_are_skipped(self):
        self.change_export(
            "contacts",
            lambda data: data["varchar"]["501"].update(contact_type_id="999"),
        )
        self.change_export(
            "contacts",
            lambda data: data["varchar"]["502"].update(workplace_user_id="999"),
        )
        cit.import_contacts(self.store)
        self.assertFalse(Contact.objects.exists())


class FMFIImportTests(ImportTestCase):
    def import_fixture(self):
        with (DATA / "fmfi.csv").open() as reader:
            fmfi.import_contacts(reader)

    def test_import_is_repeatable_and_skips_unknown_people(self):
        self.import_fixture()
        self.import_fixture()
        self.assertEqual(Contact.objects.count(), 4)
        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(
            Contact.objects.get(contact_type__identifier="room").value, "A - 123"
        )
        self.assertEqual(
            Contact.objects.get(contact_type__identifier="phone").value, "1234"
        )

    def test_stale_contacts_are_removed_without_affecting_other_sources(self):
        stale = self.stale_contact("fmfi")
        other = self.stale_contact("cit")
        self.import_fixture()
        self.assertFalse(Contact.objects.filter(pk=stale.pk).exists())
        self.assertTrue(Contact.objects.filter(pk=other.pk).exists())


class CandleImportTests(ImportTestCase):
    def response(self, contents):
        return Mock(content=contents)

    @patch("ludia.contacts.imports.candle.requests.get")
    def test_import_is_repeatable_and_skips_unknown_teachers(self, get):
        get.return_value = self.response((DATA / "candle.xml").read_bytes())
        candle.import_timetables()
        candle.import_timetables()
        lesson = Lesson.objects.get()
        self.assertEqual(lesson.person, self.person)
        self.assertEqual(lesson.candle_id, 601)
        self.assertEqual(lesson.day_of_week, 3)
        self.assertEqual(lesson.start_time, time(9))
        self.assertEqual(lesson.end_time, time(10, 30))
        self.assertEqual(lesson.subject_code, "INF101")
        self.assertEqual(lesson.teachers, "Jana Nováková, Unknown Teacher")

    @patch("ludia.contacts.imports.candle.requests.get")
    def test_updates_lessons_and_removes_missing_lessons(self, get):
        contents = (DATA / "candle.xml").read_bytes()
        get.return_value = self.response(contents)
        candle.import_timetables()
        original_id = Lesson.objects.get().pk
        get.return_value = self.response(contents.replace(b"A - 123", b"B - 456"))
        candle.import_timetables()
        self.assertEqual(Lesson.objects.get().pk, original_id)
        self.assertEqual(Lesson.objects.get().room, "B - 456")
        get.return_value = self.response(b"<timetable />")
        candle.import_timetables()
        self.assertFalse(Lesson.objects.exists())


class VUPCHImportTests(ImportTestCase):
    url = vupch.REPO_ROOT + "FMFI/SK/novak.uniba.sk.xml"

    def test_parse_selected_publications_and_orcid(self):
        data = vupch.parse_vupch((DATA / "vupch.xml").read_text())
        self.assertEqual(data.orcid, "0000-0002-1825-0097")
        self.assertEqual(
            data.publications,
            [
                "Nováková, J. A sample paper. https://doi.org/10.1234/example.",
                "A second paper without a DOI.",
            ],
        )

    def test_parse_falls_back_to_vi2_and_handles_missing_sections(self):
        contents = (DATA / "vupch.xml").read_text().replace("VI.3", "VI.4")
        self.assertEqual(
            vupch.parse_vupch(contents).publications, ["Not a selected publication"]
        )
        self.assertEqual(vupch.parse_vupch("<osoba />"), vupch.VUPCHData("", []))

    @patch("ludia.contacts.imports.vupch.requests.get")
    def test_file_import_updates_person_and_synchronizes_publications(self, get):
        get.return_value = Mock(text=(DATA / "vupch.xml").read_text())
        vupch._import_vupch_file(self.url)
        publication = Publication.objects.get(doi="10.1234/example")
        publication.display_text = "Editorial correction"
        publication.save()
        vupch._import_vupch_file(self.url)
        self.person.refresh_from_db()
        publication.refresh_from_db()
        self.assertEqual(self.person.orcid, "0000-0002-1825-0097")
        self.assertEqual(self.person.vupch_url, self.url.removesuffix(".xml") + ".html")
        self.assertEqual(Publication.objects.count(), 2)
        self.assertEqual(publication.display_text, "Editorial correction")
        get.return_value = Mock(text="<osoba />")
        vupch._import_vupch_file(self.url)
        self.assertFalse(Publication.objects.exists())
        self.person.refresh_from_db()
        self.assertEqual(self.person.orcid, "")

    @patch("ludia.contacts.imports.vupch.requests.get")
    def test_unknown_person_is_not_downloaded(self, get):
        vupch._import_vupch_file(self.url.replace("novak", "unknown"))
        get.assert_not_called()

    @patch("ludia.contacts.imports.vupch.requests.get")
    def test_failed_download_or_invalid_xml_preserves_existing_data(self, get):
        publication = Publication.objects.create(
            person=self.person, raw_text="Existing"
        )
        for response in (Mock(text="not XML"), Mock()):
            with self.subTest(response=response):
                get.return_value = response
                if response.text != "not XML":
                    response.raise_for_status.side_effect = requests.HTTPError(
                        "Unavailable"
                    )
                with self.assertLogs(vupch.logger, level="ERROR"):
                    vupch._import_vupch_file(self.url)
                self.assertTrue(Publication.objects.filter(pk=publication.pk).exists())

    @patch("ludia.contacts.imports.vupch.requests.get")
    def test_repository_discovery_and_duplicate_files(self, get):
        faculty_url = vupch.REPO_ROOT + "FMFI/"
        sk_url = faculty_url + "SK/"
        pages = {
            vupch.REPO_ROOT: '<a href="../">..</a><a href="FMFI/">FMFI</a>',
            faculty_url: '<a href="SK/">SK</a><a href="EN/">EN</a>',
            sk_url: '<a href="novak.uniba.sk.xml">XML</a>'
            '<a href="novak.uniba.sk.xml">Duplicate</a>'
            '<a href="novak.uniba.sk.html">HTML</a>',
            self.url: (DATA / "vupch.xml").read_text(),
        }
        get.side_effect = lambda url, **kwargs: Mock(text=pages[url])
        vupch.import_vupch()
        self.assertEqual(Publication.objects.count(), 2)
        self.assertEqual(get.call_count, 4)
