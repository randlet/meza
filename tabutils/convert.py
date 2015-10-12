#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: sw=4:ts=4:expandtab

"""
tabutils.convert
~~~~~~~~~~~~~~~~

Provides methods for converting data structures

Examples:
    basic usage::

        from tabutils.convert import to_decimal

        decimal = to_decimal('$123.45')

Attributes:
    DEFAULT_DATETIME (obj): Default datetime object
"""

from __future__ import (
    absolute_import, division, print_function, with_statement,
    unicode_literals)

import itertools as it
import unicodecsv as csv

from os import path as p
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_HALF_DOWN
from StringIO import StringIO
from json import dumps, JSONEncoder
from datetime import datetime as dt

from . import fntools as ft, ENCODING

from dateutil.parser import parse

DEFAULT_DATETIME = dt(9999, 12, 31, 0, 0, 0)


class CustomEncoder(JSONEncoder):
    def default(self, obj):
        if set(['quantize', 'year']).intersection(dir(obj)):
            return str(obj)
        elif set(['next', 'union']).intersection(dir(obj)):
            return list(obj)
        return JSONEncoder.default(self, obj)


def ctype2ext(content_type=None):
    """Converts an http content type to a file extension.

    Args:
        content_type (str): Output file path or directory.

    Returns:
        str: file extension

    Examples:
        >>> ctype2ext('/csv;')
        u'csv'
        >>> ctype2ext('/xls;')
        u'xls'
        >>> ctype2ext('/vnd.openxmlformats-officedocument.spreadsheetml.sheet;')
        u'xlsx'
    """
    try:
        ctype = content_type.split('/')[1].split(';')[0]
    except (AttributeError, IndexError):
        ctype = None

    xlsx_type = 'vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    switch = {'xls': 'xls', 'csv': 'csv'}
    switch[xlsx_type] = 'xlsx'

    if ctype not in switch:
        print(
            'Content-Type %s not found in dictionary. Using default value.'
            % ctype)

    return switch.get(ctype, 'csv')


def to_bool(content, trues=None, falses=None):
    """Formats strings into bool.

    Args:
        content (str): The content to parse.
        trues (List[str]): Values to consider True.
        falses (List[str]): Values to consider Frue.

    See also:
        `process.type_cast`

    Returns:
        bool: The parsed content.

    Examples:
        >>> to_bool(True)
        True
        >>> to_bool('true')
        True
        >>> to_bool('y')
        True
        >>> to_bool(1)
        True
        >>> to_bool(False)
        False
        >>> to_bool('false')
        False
        >>> to_bool('n')
        False
        >>> to_bool(0)
        False
        >>> to_bool('')
        False
        >>> to_bool(None)
        False

    Returns:
        int
    """
    trues = set(map(str.lower, trues) if trues else ft.DEF_TRUES)

    try:
        value = content.lower() in trues
    except AttributeError:
        value = bool(content)

    return value


def to_int(value, thousand_sep=',', decimal_sep='.'):
    """Formats strings into integers.

    Args:
        value (str): The number to parse.
        thousand_sep (char): thousand's separator (default: ',')
        decimal_sep (char): decimal separator (default: '.')

    See also:
        `process.type_cast`

    Returns:
        flt: The parsed number.

    Examples:
        >>> to_int('$123.45')
        123
        >>> to_int('123€')
        123
        >>> to_int('2,123.45')
        2123
        >>> to_int('2.123,45', thousand_sep='.', decimal_sep=',')
        2123
        >>> to_int('spam')

    Returns:
        int
    """
    try:
        value = int(float(ft.strip(value, thousand_sep, decimal_sep)))
    except ValueError:
        value = None

    return value


def to_float(content, thousand_sep=',', decimal_sep='.'):
    """Formats strings into floats.

    Args:
        content (str): The number to parse.
        thousand_sep (char): thousand's separator (default: ',')
        decimal_sep (char): decimal separator (default: '.')

    Returns:
        flt: The parsed number.

    See also:
        `process.type_cast`

    Examples:
        >>> to_float('$123.45')
        123.45
        >>> to_float('123€')
        123.0
        >>> to_float('2,123.45')
        2123.45
        >>> to_float('2.123,45', thousand_sep='.', decimal_sep=',')
        2123.45
        >>> to_float('spam')

    Returns:
        float
    """
    try:
        value = float(ft.strip(content, thousand_sep, decimal_sep))
    except ValueError:
        value = None

    return value


def to_decimal(content, thousand_sep=',', decimal_sep='.', **kwargs):
    """Formats strings into decimals

    Args:
        content (str): The string to parse.
        thousand_sep (char): thousand's separator (default: ',')
        decimal_sep (char): decimal separator (default: '.')
        kwargs (dict): Keyword arguments.

    Kwargs:
        roundup (bool): Round up to the desired number of decimal places (
            default: True).

        places (int): Number of decimal places to display (default: 2).

    See also:
        `process.type_cast`

    Examples:
        >>> to_decimal('$123.45')
        Decimal('123.45')
        >>> to_decimal('123€')
        Decimal('123.00')
        >>> to_decimal('2,123.45')
        Decimal('2123.45')
        >>> to_decimal('2.123,45', thousand_sep='.', decimal_sep=',')
        Decimal('2123.45')
        >>> to_decimal('1.554')
        Decimal('1.55')
        >>> to_decimal('1.555')
        Decimal('1.56')
        >>> to_decimal('1.555', roundup=False)
        Decimal('1.55')
        >>> to_decimal('1.556')
        Decimal('1.56')
        >>> to_decimal('spam')

    Returns:
        decimal
    """
    try:
        decimalized = Decimal(ft.strip(content, thousand_sep, decimal_sep))
    except InvalidOperation:
        quantized = None
    else:
        roundup = kwargs.get('roundup', True)
        rounding = ROUND_HALF_UP if roundup else ROUND_HALF_DOWN
        places = int(kwargs.get('places', 2))
        precision = '.%s1' % ''.join(it.repeat('0', places - 1))
        quantized = decimalized.quantize(Decimal(precision), rounding=rounding)

    return quantized


def _to_datetime(content):
    """Parses and formats strings into datetimes.

    Args:
        content (str): The date to parse.

    Returns:
        [tuple(str, bool)]: Tuple of the formatted date string and retry value.

    Examples:
        >>> _to_datetime('5/4/82')
        (datetime.datetime(1982, 5, 4, 0, 0), False)
        >>> _to_datetime('2/32/82')
        (u'2/32/82', True)
        >>> _to_datetime('Novmbr 4')
        (None, False)
    """
    try:
        value = parse(content, default=DEFAULT_DATETIME)
    except ValueError:  # impossible date, e.g., 2/31/15
        value = content
        retry = True
    except TypeError:  # unparseable date, e.g., Novmbr 4
        value = None
        retry = False
    else:
        retry = False

    return (value, retry)


def to_datetime(content, dt_format=None):
    """Parses and formats strings into datetimes.

    Args:
        content (str): The string to parse.

    Kwargs:
        dt_format (str): Date format passed to `strftime()`
            (default: None).

    Returns:
        obj: The datetime object or formatted datetime string.

    See also:
        `process.type_cast`

    Examples:
        >>> to_datetime('5/4/82 2:00 pm')
        datetime.datetime(1982, 5, 4, 14, 0)
        >>> to_datetime('5/4/82 10:00', '%Y-%m-%d %H:%M:%S')
        '1982-05-04 10:00:00'
        >>> to_datetime('2/32/82 12:15', '%Y-%m-%d %H:%M:%S')
        '1982-02-28 12:15:00'
        >>> to_datetime('Novmbr 4')
    """
    bad_nums = it.imap(str, xrange(29, 33))
    good_nums = it.imap(str, xrange(31, 27, -1))

    try:
        bad_num = it.ifilter(lambda x: x in content, bad_nums).next()
    except StopIteration:
        options = [content]
    else:
        possibilities = (content.replace(bad_num, x) for x in good_nums)
        options = it.chain([content], possibilities)

    # Fix impossible dates, e.g., 2/31/15
    results = it.ifilterfalse(lambda x: x[1], it.imap(_to_datetime, options))

    try:
        good_value = results.next()[0]
    except StopIteration:
        datetime = None
    else:
        datetime = good_value.strftime(dt_format) if dt_format else good_value

    return datetime


def to_date(content, date_format=None):
    """Parses and formats strings into dates.

    Args:
        content (str): The string to parse.

    Kwargs:
        date_format (str): Time format passed to `strftime()` (default: None).

    Returns:
        obj: The date object or formatted date string.

    See also:
        `process.type_cast`

    Examples:
        >>> to_date('5/4/82')
        datetime.date(1982, 5, 4)
        >>> to_date('5/4/82', '%Y-%m-%d')
        '1982-05-04'
        >>> to_date('2/32/82', '%Y-%m-%d')
        '1982-02-28'
    """
    value = to_datetime(content).date()
    return value.strftime(date_format) if date_format else value


def to_time(content, time_format=None):
    """Parses and formats strings into times.

    Args:
        content (str): The string to parse.

    Kwargs:
        time_format (str): Time format passed to `strftime()` (default: None).

    Returns:
        obj: The time object or formatted time string.

    See also:
        `process.type_cast`

    Examples:
        >>> to_time('2:00 pm')
        datetime.time(14, 0)
        >>> to_time('10:00', '%H:%M:%S')
        '10:00:00'
        >>> to_time('2/32/82 12:15', '%H:%M:%S')
        '12:15:00'
    """
    value = to_datetime(content).time()
    return value.strftime(time_format) if time_format else value


def to_filepath(filepath, **kwargs):
    """Creates a filepath from an online resource, i.e., linked file or
    google sheets export.

    Args:
        filepath (str): Output file path or directory.
        kwargs: Keyword arguments.

    Kwargs:
        headers (dict): HTTP response headers, e.g., `r.headers`.
        name_from_id (bool): Overwrite filename with resource id.
        resource_id (str): The resource id (required if `name_from_id` is True
            or filepath is a google sheets export)

    Returns:
        str: filepath

    Examples:
        >>> to_filepath('file.csv')
        u'file.csv'
        >>> to_filepath('.', resource_id='rid')
        Content-Type None not found in dictionary. Using default value.
        u'./rid.csv'
    """
    isdir = p.isdir(filepath)
    headers = kwargs.get('headers') or {}
    name_from_id = kwargs.get('name_from_id')
    resource_id = kwargs.get('resource_id')

    if isdir and not name_from_id:
        try:
            disposition = headers.get('content-disposition', '')
            filename = disposition.split('=')[1].split('"')[1]
        except (KeyError, IndexError):
            filename = resource_id
    elif isdir or name_from_id:
        filename = resource_id

    if isdir and filename.startswith('export?format='):
        filename = '%s.%s' % (resource_id, filename.split('=')[1])
    elif isdir and '.' not in filename:
        ctype = headers.get('content-type')
        filename = '%s.%s' % (filename, ctype2ext(ctype))

    return p.join(filepath, filename) if isdir else filepath


def df2records(df):
    """
    Converts a pandas DataFrame into records.

    Args:
        df (obj): pandas.DataFrame object

    Yields:
        dict: Record. A row of data whose keys are the field names.

    See also:
        `process.pivot`

    Examples:
        >>> try:
        ...    import pandas as pd
        ... except ImportError:
        ...    print('pandas is required to run this test')
        ... else:
        ...    records = [{'a': 1, 'b': 2, 'c': 3}, {'a': 4, 'b': 5, 'c': 6}]
        ...    df = pd.DataFrame.from_records(records)
        ...    df2records(df).next() == {u'a': 1, u'b': 2, u'c': 3}
        ...
        True
    """
    index = filter(None, (df.index.names))

    try:
        keys = index + df.columns.tolist()
    except AttributeError:
        # we have a Series, not a DataFrame
        keys = index + [df.name]
        rows = (i[0] + (i[1],) for i in df.iteritems())
    else:
        rows = df.itertuples()

    for values in rows:
        if index:
            yield dict(zip(keys, values))
        else:
            yield dict(zip(keys, values[1:]))


def records2csv(records, header=None, encoding=ENCODING, bom=False):
    """
    Converts records into a csv file like object.

    Args:
        records (Iter[dict]): Rows of data whose keys are the field names.
            E.g., output from any `tabutils.io` read function.

    Kwargs:
        header (List[str]): The header row (default: None)

    Returns:
        obj: StringIO.StringIO instance

    Examples:
        >>> records = [
        ...     {
        ...         u'usda_id': u'IRVE2',
        ...         u'species': u'Iris-versicolor',
        ...         u'wikipedia_url': u'wikipedia.org/wiki/Iris_versicolor'}]
        ...
        >>> header = records[0].keys()
        >>> csv_str = records2csv(records, header)
        >>> csv_str.next().strip()
        'usda_id,species,wikipedia_url'
        >>> csv_str.next().strip()
        'IRVE2,Iris-versicolor,wikipedia.org/wiki/Iris_versicolor'
    """
    f = StringIO()

    if bom:
        f.write(u'\ufeff'.encode(ENCODING))  # BOM for Windows

    w = csv.DictWriter(f, header, encoding=encoding)
    w.writer.writerow(header)
    w.writerows(records)
    f.seek(0)
    return f


def records2json(records, **kwargs):
    """
    Converts records into a json file like object.

    Args:
        records (Iter[dict]): Rows of data whose keys are the field names.
            E.g., output from any `tabutils.io` read function.

    Kwargs:
        indent (int): Number of spaces to indent (default: 2).
        sort_keys (bool): Sort rows by keys (default: True).
        ensure_ascii (bool): Sort response dict by keys (default: False).

    Returns:
        obj: StringIO.StringIO instance

    Examples:
        >>> record = {
        ...     u'usda_id': u'IRVE2',
        ...     u'species': u'Iris-versicolor',
        ...     u'wikipedia_url': u'wikipedia.org/wiki/Iris_versicolor'}
        ...
        >>> records2json([record]).next()
        '[{"usda_id": "IRVE2", "species": "Iris-versicolor", \
"wikipedia_url": "wikipedia.org/wiki/Iris_versicolor"}]'
    """
    json = dumps(records, cls=CustomEncoder, **kwargs)
    return StringIO(json)
