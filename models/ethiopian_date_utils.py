# -*- coding: utf-8 -*-
from datetime import date, datetime

# Ethiopian Month Names in Amharic & English Transliteration
ETHIOPIAN_MONTHS_AMHARIC = [
    '',
    'መስከረም', 'ጥቅምት', 'ኅዳር', 'ታኅሣሥ', 'ጥር', 'የካቲት',
    'መጋቢት', 'ሚያዝያ', 'ግንቦት', 'ሰኔ', 'ሐምሌ', 'ነሐሴ', 'ጳጉሜ'
]

ETHIOPIAN_MONTHS_EN = [
    '',
    'Meskerem', 'Tikimt', 'Hidar', 'Tahsas', 'Tir', 'Yekatit',
    'Megabit', 'Miyazya', 'Ginbot', 'Sene', 'Hamle', 'Nehase', 'Pagume'
]

AMHARIC_WEEKDAYS = [
    'ሰኞ', 'ማክሰኞ', 'ረቡዕ', 'ሐሙስ', 'ዓርብ', 'ቅዳሜ', 'እሑድ'
]


def gregorian_to_jdn(year, month, day):
    """ Converts Gregorian date to Julian Day Number (JDN) """
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + ((153 * m + 2) // 5) + 365 * y + (y // 4) - (y // 100) + (y // 400) - 32045


def jdn_to_gregorian(jdn):
    """ Converts Julian Day Number (JDN) to Gregorian date tuple (year, month, day) """
    a = jdn + 32044
    b = (4 * a + 3) // 146097
    c = a - (146097 * b) // 4
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - ((153 * m + 2) // 5) + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + (m // 10)
    return year, month, day


def ethiopian_to_jdn(year, month, day):
    """ Converts Ethiopian date to Julian Day Number (JDN) """
    return (1723856 + 365) + 365 * (year - 1) + (year // 4) + 30 * (month - 1) + day - 1


def jdn_to_ethiopian(jdn):
    """ Converts Julian Day Number (JDN) to Ethiopian date tuple (year, month, day) """
    r = (jdn - 1723856) % 1461
    n = (r % 365) + 365 * (r // 1460)
    year = 4 * ((jdn - 1723856) // 1461) + (r // 365) - (r // 1460)
    month = (n // 30) + 1
    day = (n % 30) + 1
    return year, month, day


def gregorian_to_ethiopian(g_date):
    """
    Converts a Python date/datetime or ISO date string to Ethiopian (year, month, day).
    """
    if not g_date:
        return None
    if isinstance(g_date, str):
        g_date = datetime.strptime(g_date[:10], '%Y-%m-%d').date()
    elif isinstance(g_date, datetime):
        g_date = g_date.date()

    jdn = gregorian_to_jdn(g_date.year, g_date.month, g_date.day)
    return jdn_to_ethiopian(jdn)


def ethiopian_to_gregorian(e_year, e_month, e_day):
    """
    Converts Ethiopian (year, month, day) to a Python date object.
    """
    jdn = ethiopian_to_jdn(int(e_year), int(e_month), int(e_day))
    gy, gm, gd = jdn_to_gregorian(jdn)
    return date(gy, gm, gd)


def is_ethiopian_leap_year(year):
    """ Ethiopian leap year occurs if year % 4 == 3 (e.g. 2015, 2019...) """
    return (year % 4) == 3


def get_ethiopian_days_in_month(year, month):
    """ Returns total days in given Ethiopian month (1-13) """
    if month < 1 or month > 13:
        return 30
    if month <= 12:
        return 30
    return 6 if is_ethiopian_leap_year(year) else 5


def format_ethiopian_date(g_date, lang='am', include_weekday=False):
    """
    Formats a Gregorian date as an Ethiopian date string.
    e.g. "28 ነሐሴ 2018 ዓ.ም." or "ሐሙስ, 28 ነሐሴ 2018 ዓ.ም."
    """
    if not g_date:
        return ''
    if isinstance(g_date, str):
        try:
            g_date = datetime.strptime(g_date[:10], '%Y-%m-%d').date()
        except Exception:
            return g_date
    elif isinstance(g_date, datetime):
        g_date = g_date.date()

    ey, em, ed = gregorian_to_ethiopian(g_date)

    if lang == 'am':
        m_name = ETHIOPIAN_MONTHS_AMHARIC[em]
        formatted = f"{ed} {m_name} {ey} ዓ.ም."
        if include_weekday:
            w_name = AMHARIC_WEEKDAYS[g_date.weekday()]
            formatted = f"{w_name}, {formatted}"
    else:
        m_name = ETHIOPIAN_MONTHS_EN[em]
        formatted = f"{ed} {m_name} {ey} E.C."
        if include_weekday:
            formatted = f"{g_date.strftime('%A')}, {formatted}"

    return formatted
