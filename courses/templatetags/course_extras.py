from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """Фильтр для получения значения из словаря по ключу"""
    return dictionary.get(key)