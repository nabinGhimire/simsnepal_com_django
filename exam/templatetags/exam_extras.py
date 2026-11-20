from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return None
    key_str = str(key)
    if isinstance(dictionary, dict):
        if key_str in dictionary:
            return dictionary[key_str]
        if key in dictionary:
            return dictionary[key]
    return None

@register.filter
def div(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except ValueError:
        return 0

@register.filter
def gp_grade(value):
    try:
        cgpa = float(value)
    except (ValueError, TypeError):
        return "NG"
    if cgpa >= 4.0:
        return "A"
    elif cgpa >= 3.6:
        return "A"
    elif cgpa >= 3.2:
        return "B"
    elif cgpa >= 2.8:
        return "B"
    elif cgpa >= 2.4:
        return "C"
    elif cgpa >= 2.0:
        return "C"
    elif cgpa >= 1.6:
        return "D"
    else:
        return "NG"

@register.filter
def gp_symbol(value):
    try:
        cgpa = float(value)
    except (ValueError, TypeError):
        return ""
    if cgpa >= 4.0:
        return "+"
    elif cgpa >= 3.6:
        return " "
    elif cgpa >= 3.2:
        return "+"
    elif cgpa >= 2.8:
        return " "
    elif cgpa >= 2.4:
        return "+"
    elif cgpa >= 2.0:
        return " "
    elif cgpa >= 1.6:
        return " "
    else:
        return ""