from django import template

register = template.Library()

@register.filter(name='duration_from_seconds')
def duration_from_seconds(value):
    """Format total seconds into 'Xh Ym'."""
    try:
        value = int(value)
        hours = value // 3600
        minutes = (value % 3600) // 60
        return f"{hours}h {minutes}m"
    except (TypeError, ValueError):
        return "0h 0m"
