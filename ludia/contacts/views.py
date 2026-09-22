from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils.translation import get_language

from ludia.contacts.models import Contact, Person


def person_profile(request, login):
    person = get_object_or_404(Person, login=login)
    contacts = (
        Contact.objects.filter(person=person)
        .filter(Q(language="") | Q(language=get_language()))
        .select_related("contact_type")
    )
    timetable = person.lesson_set.all()

    return render(
        request,
        "person.html",
        {
            "person": person,
            "contacts": contacts,
            "timetable": timetable,
        },
    )
