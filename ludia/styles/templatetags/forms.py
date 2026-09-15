from django import template

register = template.Library()


@register.inclusion_tag("forms/field.html")
def render_field(field):
    return {"field": field}


@register.inclusion_tag("forms/form.html")
def render_form(form):
    return {"form": form}
