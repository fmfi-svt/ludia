from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Q
from django.db.models.expressions import RawSQL
from django.shortcuts import get_object_or_404, render

from ludia.contacts.imports.cit import FMFI_CIT_ID
from ludia.contacts.models import Person, Workplace


def person_list(request):
    query = request.GET.get("q", "").strip()
    workplace_table = connection.ops.quote_name(Workplace._meta.db_table)
    faculty_workplaces = RawSQL(
        f"""
        WITH RECURSIVE faculty_workplaces AS (
            SELECT id FROM {workplace_table} WHERE cit_id = %s
            UNION
            SELECT workplace.id
            FROM {workplace_table} AS workplace
            JOIN faculty_workplaces ON workplace.parent_id = faculty_workplaces.id
        )
        SELECT id FROM faculty_workplaces
        """,
        [FMFI_CIT_ID],
    )
    include_university = request.GET.get("include_university") == "1"
    people = Person.objects.all()
    if not include_university:
        people = people.filter(relation__workplace_id__in=faculty_workplaces).distinct()
    people = people.order_by("last_name", "first_name", "login")
    for term in query.split():
        people = people.filter(
            Q(first_name__icontains=term)
            | Q(middle_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(login__icontains=term)
        )

    page = Paginator(people, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "people.html",
        {
            "page_obj": page,
            "page_range": page.paginator.get_elided_page_range(page.number),
            "query": query,
            "include_university": include_university,
        },
    )


def person_profile(request, login):
    person = get_object_or_404(Person, login=login)
    timetable = person.lesson_set.all()
    publications = person.publication_set.all()

    affiliations_by_workplace = {}
    for relation in person.relation_set.all():
        if relation.workplace_id not in affiliations_by_workplace:
            affiliations_by_workplace[relation.workplace_id] = {
                "job_titles": [],
                "workplaces": relation.all_workplaces(),
            }
        affiliation = affiliations_by_workplace[relation.workplace_id]
        title = relation.job_title
        if title and title not in affiliation["job_titles"]:
            affiliation["job_titles"].append(title)

    return render(
        request,
        "person.html",
        {
            "person": person,
            "affiliations": list(affiliations_by_workplace.values()),
            "contacts": person.get_contacts(),
            "timetable": timetable,
            "publications": publications,
        },
    )
