from django import template

register = template.Library()

@register.filter(name='int_filter')
def int_filter(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return value