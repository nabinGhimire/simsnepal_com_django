from django.template.defaulttags import register


@register.filter
def get_value(dictionary, key):
    return dictionary.get(key)


@register.filter
def question_and(value):
    return value.replace("?", "&")


@register.filter
def and_question(value):
    return value.replace("&", "?")


@register.filter()
def dict_key(d, key):
   return d[key]

