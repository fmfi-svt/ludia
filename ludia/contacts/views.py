from django.shortcuts import get_object_or_404, render

from ludia.contacts.models import Person


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
