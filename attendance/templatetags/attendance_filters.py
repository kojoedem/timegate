from django import template

register = template.Library()

@register.filter
def hours(value):
    try:
        return value // 3600
    except Exception:
        return 0

@register.filter
def minutes(value):
    try:
        return (value % 3600) // 60
    except Exception:
        return 0
