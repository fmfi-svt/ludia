import re
from typing import TYPE_CHECKING, Callable
from urllib.parse import urlsplit

import phonenumbers
from django.utils.html import escape, format_html
from django.utils.safestring import SafeString

if TYPE_CHECKING:
    from ludia.contacts.models import Contact


EXTERNAL_PHONE_PREFIX = "+421260295"


def get_phone_counterpart(value: str) -> str | None:
    """Return the external number or extension for our three-digit extensions."""
    value = value.strip()
    if re.fullmatch(r"[0-9]{3}", value):
        return f"{EXTERNAL_PHONE_PREFIX}{value}"

    try:
        number = phonenumbers.parse(value, "SK")
    except phonenumbers.NumberParseException:
        return None

    if not phonenumbers.is_valid_number(number) or number.extension:
        return None

    external = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    if re.fullmatch(re.escape(EXTERNAL_PHONE_PREFIX) + r"[0-9]{3}", external):
        return external[-3:]
    return None


def render_text(value: str) -> SafeString:
    return escape(value)


def render_room(value: str) -> SafeString:
    return render_text(re.sub(r"\s*-\s*", " - ", value))


def render_email(value: str) -> SafeString:
    value = value.lower()
    return format_html('<a href="mailto:{}">{}</a>', value, value)


def render_phone(value: str) -> SafeString:
    try:
        number = phonenumbers.parse(value, "SK")
    except phonenumbers.NumberParseException:
        return render_text(value)

    if not phonenumbers.is_valid_number(number):
        return render_text(value)

    href = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    display = phonenumbers.format_number(
        number, phonenumbers.PhoneNumberFormat.INTERNATIONAL
    )
    return format_html('<a href="tel:{}">{}</a>', href, display)


def render_website(value: str) -> SafeString:
    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return render_text(value)

    href = value if parsed.scheme else f"https://{value}"
    return format_html(
        '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
        href,
        value,
    )


CONTACT_RENDERERS: dict[str, Callable[[str], SafeString]] = {
    "room": render_room,
    "email": render_email,
    "phone": render_phone,
    "website": render_website,
}


def render_contact(contact: "Contact") -> SafeString:
    renderer = CONTACT_RENDERERS.get(contact.contact_type.identifier, render_text)
    return renderer(contact.value)
