import sys
from datetime import datetime
from collections import OrderedDict
from itertools import imap

from .prettyfiers import HTMLPrettyfier
from .utils import TimeSeries, FacebookComments


__all__ = ['parse_object']


AVAILABLE_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y %m %d",
    "%m-%d-%Y",
    "%d/%m/%Y",
)


def failsafe_generator(iterable, exc_type=Exception):
    """Yield from an iterable and swallow any exception that could
    occur.

    Generation stop either when the iterable is exhausted or when an
    exception is raised.
    """

    try:
        for element in iterable:
            yield element
    except exc_type:
        # EAFP: only import this if really necessary
        import traceback
        traceback.print_exc()


def custom_date(argument):
    """Try to convert the argument to date by analyzing various formats"""

    for date_format in AVAILABLE_DATE_FORMATS:
        try:
            return datetime.strptime(argument, date_format)
        except ValueError:
            pass
    raise ValueError("invalid date '{}': format not recognized.".format(argument))


def parse_object(user_token, object_id,
                 output_stream=sys.stdout,
                 storage_file=None,
                 interactive=False,
                 focus=None,
                 focus_days=15,
                 focus_interval=20):
    """Provide a session to fetch and analyze data from a facebook
    object. Data are retrieved on behalf of the user represented in
    the given token.

    In case data should be analyzed from a previously exported session,
    user_token should be None and object_id should be the path to the
    file where data were pickled.
    """

    if user_token is None:
        storage = TimeSeries.unpickle(object_id)
    else:
        parser = FacebookComments(user_token)
        storage = TimeSeries(failsafe_generator(parser.analyze(object_id)))

    if storage_file is not None:
        storage.pickle(storage_file)

    with HTMLPrettyfier(output_stream) as output:
        while True:
            name = focus.strftime('%d %B %Y') if focus is not None else None
            data = storage.generate_statistics(focus, focus_days, focus_interval)
            output.new_document(imap(OrderedDict, data), name)

            if not interactive:
                break

            try:
                focus = custom_date(raw_input('Focus on a new date> '))
            except ValueError:
                break
