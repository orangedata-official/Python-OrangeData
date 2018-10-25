import re


def phone_is_valid(phone):
    """
    :param phone: Телефон для валидации
    :type phone: str
    :return: Результат валидации
    :rtype: bool
    """
    return True if re.match(r'^((8|\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{7,10}$', phone) else False


def length_is_valid(obj, min_=None, max_=None):
    """
    :param obj: Любой объект, у которого релизован метод __len__
    :param min_: минимальное значение для сравнения
    :param max_: максимальное значение для сравнения
    :type min_: int or float
    :type max_: int or float
    :return: Результат сравнения
    :rtype: bool or None
    """
    length = len(obj)
    res = None

    if min_:
        res = length >= min_
        if not res:
            return res

    if max_:
        res = length <= max_

    return res
