from django.shortcuts import get_object_or_404, render

from ludia.contacts.models import Person


def person_profile(request, login):
    person = get_object_or_404(Person, login=login)
    timetable = person.lesson_set.all()
    publications = person.publication_set.all()

    return render(
        request,
        "person.html",
        {
            "person": person,
            "contacts": person.get_contacts(),
            "timetable": timetable,
            "publications": publications,
        },
    )
