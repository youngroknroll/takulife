"""form_extras — template filter to wire a bound field's own error list.

{{ form.email }} renders whatever attrs the field's widget was configured
with; none of the auth forms here (allauth's built-ins, or accounts.forms.
SignupForm) set aria-describedby, and most of them aren't ours to subclass
just for this. A small filter is the least invasive way to add it in the
template layer, without touching any form class.
"""
from django import template

register = template.Library()


@register.filter(name="describedby")
def describedby(field):
    """Render `field` with aria-describedby pointed at its own error list —
    only when it actually has field-level errors, so a clean field never
    references a container that doesn't exist on the page."""
    if not field.errors:
        return field
    return field.as_widget(attrs={"aria-describedby": field.id_for_label + "-error"})
