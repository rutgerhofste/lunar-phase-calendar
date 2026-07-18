#!/usr/bin/env python3
"""Generates calendars with lunar phase in iCal format."""

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from json import load
from math import degrees, pi
from os.path import isdir
from os import makedirs, chdir
from zoneinfo import ZoneInfo

import ephem

# pylint:disable=unspecified-encoding,disable=consider-using-with

MOON_PHASE_NAMES = load(open('moon-phase-names.json'))
MOON_PHASE_SYMBOLS = ('🌑', '🌒', '🌓', '🌔', '🌕', '🌖', '🌗', '🌘')

COUNTRIES = load(open('countries.json'))

# Capitalized header values for day, phase, symbol, name and title.
HEADER = load(open('headers.json'))

# Explicitely capitalize with title() all words.
TITLES = ('en', 'pt')


def moon_phase_code_to_name(code: int, lang: str = 'en') -> str:
    """Convert moon phase code to name."""
    return MOON_PHASE_NAMES[lang][code]


def moon_phase_code_to_symbol(code: int) -> str:
    """Convert moon phase code to symbol."""
    return MOON_PHASE_SYMBOLS[code]


# The four principal phases and their code, in cycle order, paired with the
# ephem function that returns the next occurrence of that phase.
PRINCIPAL_PHASES = (
    (ephem.next_new_moon, 0),
    (ephem.next_first_quarter_moon, 2),
    (ephem.next_full_moon, 4),
    (ephem.next_last_quarter_moon, 6),
)


def country_timezone(country: str) -> ZoneInfo:
    """Read the country's time zone from its calendar header template."""
    for line in open(f'../../templates/calendar-header-{country}.txt'):
        line = line.strip()
        if line.startswith('TZID:'):
            return ZoneInfo(line[len('TZID:'):])
    return ZoneInfo('UTC')


def phase_position(instant: datetime) -> float:
    """Moon phase as a value in [0, 28): new 0, first quarter 7, full 14,
    last quarter 21.

    Computed from the true Sun-Moon elongation in ecliptic longitude, so the
    principal phases land exactly on 0/7/14/21.
    """
    moon = ephem.Ecliptic(ephem.Moon(instant))
    sun = ephem.Ecliptic(ephem.Sun(instant))
    elongation = (moon.lon - sun.lon) % (2 * pi)
    return degrees(elongation) / 360 * 28 % 28


def principal_phase_days(start: date, end: date, tz: ZoneInfo) -> dict:
    """Map every local day in [start, end) that holds a principal phase to
    its code.

    ephem returns the exact UTC instant of each new/first-quarter/full/
    last-quarter moon; that instant is converted to the country's local time
    so the phase is recorded on the local calendar day on which it occurs.
    """
    days = {}
    # Start the search a little before the window so the first in-window day
    # already has a preceding principal phase to derive its arc from.
    search_start = ephem.Date(datetime(start.year, start.month, start.day)
                              - timedelta(days=40))
    for next_phase, code in PRINCIPAL_PHASES:
        when = search_start
        while True:
            when = next_phase(when)
            local = when.datetime().replace(
                tzinfo=timezone.utc).astimezone(tz).date()
            if local >= end:
                break
            days[local] = code
            when = ephem.Date(when + 0.5)
    return days


def day_codes(start: date, end: date, tz: ZoneInfo) -> dict:
    """Map every local day in [start, end) to its moon phase code.

    Principal phases come from the exact ephem event days; every other day
    gets the intermediate phase of the arc that follows the most recent
    principal phase (new -> waxing crescent, first quarter -> waxing gibbous,
    full -> waning gibbous, last quarter -> waning crescent).
    """
    principal = principal_phase_days(start - timedelta(days=40), end, tz)
    before = [day for day in principal if day < start]
    last_code = principal[max(before)] if before else 6
    codes = {}
    day = start
    while day < end:
        if day in principal:
            last_code = principal[day]
            codes[day] = last_code
        else:
            codes[day] = (last_code + 1) % 8
        day += timedelta(days=1)
    return codes


def write_files(country: str, lang: str) -> None:
    """Write calendar files."""
    # Open files for writing.
    tsv = open('moon-phases.tsv', 'w')
    tsv_new = open('new-moon.tsv', 'w')
    tsv_full = open('full-moon.tsv', 'w')
    tsv_all = open('moon-phases-all.tsv', 'w')
    mkd = open('moon-phases.md', 'w')
    mkd_new = open('new-moon.md', 'w')
    mkd_full = open('full-moon.md', 'w')
    mkd_all = open('moon-phases-all.md', 'w')
    ics = open('moon-phases.ics', 'w', newline='\r\n')
    ics_new = open('new-moon.ics', 'w', newline='\r\n')
    ics_full = open('full-moon.ics', 'w', newline='\r\n')
    ics_all = open('moon-phases-all.ics', 'w', newline='\r\n')

    # Write headers.
    tsv_header = f'# {HEADER[lang][0].ljust(10)}\t# {HEADER[lang][1]}\t#' \
        f' {HEADER[lang][2]}\t# {HEADER[lang][3]}\n'
    tsv_header_short = f'# {HEADER[lang][0]}\t# {HEADER[lang][1]}\n'
    tsv.write(tsv_header)
    tsv_all.write(tsv_header)
    tsv_new.write(tsv_header_short)
    tsv_full.write(tsv_header_short)
    title = HEADER[lang][4]
    if lang in TITLES:
        title = title.title()
    mkd_header = f'''# {title}

{HEADER[lang][0].ljust(10)} | {HEADER[lang][1].ljust(6)} | {HEADER[lang][2]} | {HEADER[lang][3]}
-----------|-------:|---|---
'''
    title = MOON_PHASE_NAMES[lang][0]
    if lang in TITLES:
        title = title.title()
    mkd_header_new = f'''# {title}

{HEADER[lang][0].ljust(10)} | {HEADER[lang][1]}
-----------|------:
'''
    title = MOON_PHASE_NAMES[lang][4]
    if lang in TITLES:
        title = title.title()
    mkd_header_full = f'''# {title}

{HEADER[lang][0].ljust(10)} | {HEADER[lang][1]}
-----------|------:
'''
    mkd.write(mkd_header)
    mkd_all.write(mkd_header)
    mkd_new.write(mkd_header_new)
    mkd_full.write(mkd_header_full)
    calendar_header = open(f'../../templates/calendar-header-{country}.txt')
    for line in calendar_header:
        if lang != 'en' and '//EN' in line and 'PRODID:-//' in line:
            line = line.replace('//EN', f'//{lang.upper()}')
        if lang in TITLES:
            ics.write(line.replace('Lunar Phase', HEADER[lang][4].title()))
            tmp = line.replace('//LUNAR PHASE', '//NEW MOON')
            ics_new.write(tmp.replace('Lunar Phase',
                                       MOON_PHASE_NAMES[lang][0].title()))
            tmp = line.replace('//LUNAR PHASE', '//FULL MOON')
            ics_full.write(tmp.replace('Lunar Phase',
                                        MOON_PHASE_NAMES[lang][4].title()))
            tmp = line.replace('//LUNAR PHASE', '//ALL LUNAR PHASES')
            ics_all.write(tmp.replace('Lunar Phase', HEADER[lang][4].title()))
        else:
            ics.write(line.replace('Lunar Phase', HEADER[lang][4]))
            tmp = line.replace('//LUNAR PHASE', '//NEW MOON')
            ics_new.write(tmp.replace('Lunar Phase',
                                       MOON_PHASE_NAMES[lang][0]))
            tmp = line.replace('//LUNAR PHASE', '//FULL MOON')
            ics_full.write(tmp.replace('Lunar Phase',
                                        MOON_PHASE_NAMES[lang][4]))
            tmp = line.replace('//LUNAR PHASE', '//ALL LUNAR PHASES')
            ics_all.write(tmp.replace('Lunar Phase', HEADER[lang][4]))

    # Create event footer.
    event_footer = ''
    for line in open('../../templates/event-footer.txt'):
        event_footer += line  # pylint:disable=consider-using-join

    tz = country_timezone(country)
    today = date.today()
    start = today + timedelta(days=-6 * 31)
    end = today + timedelta(days=(5 * 366) + (3 * 31))
    codes = day_codes(start, end, tz)
    for i in range((end - start).days):
        day = start + timedelta(days=i)
        dtstamp = start + timedelta(days=-7)
        code = codes[day]
        # Representative phase value, sampled at local noon of the day.
        local_noon = datetime(day.year, day.month, day.day, 12, tzinfo=tz)
        phase = phase_position(local_noon.astimezone(timezone.utc))
        symbol = moon_phase_code_to_symbol(code)
        name = moon_phase_code_to_name(code, lang)
        tsv_all.write(f'{day}\t{phase:6.3f}\t{symbol}\t{name}\n')
        mkd_all.write(f'{day} | {phase:6.3f} | {symbol} | {name}\n')
        ics_all.write('BEGIN:VEVENT\n')
        ics_all.write(f'DTSTAMP:{dtstamp.strftime("%Y%m%d")}T040000Z\n')
        ics_all.write(f'SUMMARY:{symbol} {name}\n')
        uid = sha256((str(day) + str(phase) + symbol + name + country + lang).encode()).hexdigest()[:16]
        ics_all.write(f'UID:{uid}@lunar-phase-calendar.pandermusubi\n')
        ics_start = f'{day}'
        ics_end = f'{day + timedelta(days=1)}'
        ics_all.write(f'DTSTART;VALUE=DATE:{ics_start.replace("-", "")}\n')
        ics_all.write(f'DTEND;VALUE=DATE:{ics_end.replace("-", "")}\n')
        ics_all.write(event_footer)
        if code % 2 == 0:
            tsv.write(f'{day}\t{phase:6.3f}\t{symbol}\t{name}\n')
            mkd.write(f'{day} | {phase:6.3f} | {symbol} | {name}\n')
            ics.write('BEGIN:VEVENT\n')
            ics.write(f'DTSTAMP:{dtstamp.strftime("%Y%m%d")}T040000Z\n')
            ics.write(f'SUMMARY:{symbol} {name}\n')
            uid = sha256((str(day) + str(phase) + symbol + name + country + lang).encode()).hexdigest()[:16]
            ics.write(f'UID:{uid}@lunar-phase-calendar.pandermusubi\n')
            ics_start = f'{day}'
            ics_end = f'{day + timedelta(days=1)}'
            ics.write(f'DTSTART;VALUE=DATE:{ics_start.replace("-", "")}\n')
            ics.write(f'DTEND;VALUE=DATE:{ics_end.replace("-", "")}\n')
            ics.write(event_footer)
        if code == 0:
            tsv_new.write(f'{day}\t{phase:6.3f}\n')
            mkd_new.write(f'{day} | {phase:6.3f}\n')
            ics_new.write('BEGIN:VEVENT\n')
            ics_new.write(f'DTSTAMP:{dtstamp.strftime("%Y%m%d")}T040000Z\n')
            ics_new.write(f'SUMMARY:{symbol} {name}\n')
            uid = sha256((str(day) + str(phase) + symbol + name + country + lang).encode()).hexdigest()[:16]
            ics_new.write(f'UID:{uid}@lunar-phase-calendar.pandermusubi\n')
            ics_start = f'{day}'
            ics_end = f'{day + timedelta(days=1)}'
            ics_new.write(f'DTSTART;VALUE=DATE:{ics_start.replace("-", "")}\n')
            ics_new.write(f'DTEND;VALUE=DATE:{ics_end.replace("-", "")}\n')
            ics_new.write(event_footer)
        if code == 4:
            tsv_full.write(f'{day}\t{phase:6.3f}\n')
            mkd_full.write(f'{day} | {phase:6.3f}\n')
            ics_full.write('BEGIN:VEVENT\n')
            ics_full.write(f'DTSTAMP:{dtstamp.strftime("%Y%m%d")}T040000Z\n')
            ics_full.write(f'SUMMARY:{symbol} {name}\n')
            uid = sha256((str(day) + str(phase) + symbol + name + country + lang).encode()).hexdigest()[:16]
            ics_full.write(f'UID:{uid}@lunar-phase-calendar.pandermusubi\n')
            ics_start = f'{day}'
            ics_end = f'{day + timedelta(days=1)}'
            ics_full.write('DTSTART;VALUE='
                           f'DATE:{ics_start.replace("-", "")}\n')
            ics_full.write(f'DTEND;VALUE=DATE:{ics_end.replace("-", "")}\n')
            ics_full.write(event_footer)

    calendar_footer = open('../../templates/calendar-footer.txt')
    for line in calendar_footer:
        ics.write(line)
        ics_new.write(line)
        ics_full.write(line)
        ics_all.write(line)


def generate() -> None:
    """Generate files for countries and languages."""
    for country in sorted(COUNTRIES.keys()):
        if not isdir(country):
            makedirs(country)
        chdir(country)
        for language in sorted(COUNTRIES[country]):
            print(f'{country}/{language}')
            if not isdir(language):
                makedirs(language)
            chdir(language)
            write_files(country, language)
            chdir('..')
        chdir('..')


if __name__ == '__main__':
    generate()
