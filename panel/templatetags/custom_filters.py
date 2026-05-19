from django import template

register = template.Library()

@register.filter(name='int_filter')
def int_filter(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return value

@register.filter(name='roman_grade')
def roman_grade(value):
    """
    Converts numeric grade names to Roman numerals or NUR/LKG/UKG.
    Expected input: "1", "2", "3", "NURSERY", "LKG", "UKG", etc.
    """
    if not value:
        return ""
    
    val_str = str(value).strip().upper()
    
    # Standard labels
    if "NURSERY" in val_str or val_str == "NUR":
        return "NUR"
    if "LKG" in val_str:
        return "LKG"
    if "UKG" in val_str:
        return "UKG"
        
    # Try to convert to int for Roman numerals
    try:
        num = int(val_str)
        roman_map = {
            1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V',
            6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X'
        }
        return roman_map.get(num, val_str)
    except ValueError:
        return val_str

@register.filter(name='get_item')
def get_item(dictionary, key):
    if not isinstance(dictionary, dict):
        return ""
    return dictionary.get(str(key), "")