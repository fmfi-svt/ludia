from django import template
from django.urls import translate_url

register = template.Library()


@register.simple_tag(takes_context=True)
def language_url(context, language):
    return translate_url(context["request"].get_full_path(), language)
