from django import template

register = template.Library()

@register.filter
def hours_from_seconds(value):
    """Convert seconds into hours."""
    try:
        return int(value) // 3600
    except (ValueError, TypeError):
        return 0

@register.filter
def minutes_from_seconds(value):
    """Convert seconds into minutes (after removing hours)."""
    try:
        return (int(value) % 3600) // 60
    except (ValueError, TypeError):
        return 0
