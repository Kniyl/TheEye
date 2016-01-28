"""This package provides ways to fetch, store and analyze comments of
Facebook posts.
"""

import sys
from datetime import datetime
from itertools import imap

import pandas as pd

from .prettyfiers import HTMLPrettyfier
from .utils import TimeSeries, FacebookComments


__all__ = ['statistical_analysis', 'read_from_facebook', 'read_from_file']


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


def read_from_facebook(user_token, object_id):
    """Fetch data from the Facebook GraphAPI and store them in an
    facebook_comments.utils.TimeSeries object.

    Data are retrieved on behalf of the user the token is associated
    with.
    """

    parser = FacebookComments(user_token)
    return TimeSeries(failsafe_generator(parser.analyze(object_id)))


def read_from_file(path):
    """Fetch data from Facebook that were previously pickled in a file"""

    return TimeSeries.unpickle(path)


def statistical_analysis(
        object_data,
        output_stream=sys.stdout,
        interactive=False,
        focus='now',
        focus_days=15,
        focus_interval=20):
    """Analyze data comming from Facebook Graph API.

    The data must have already been parsed accordingly and be
    contained in an facebook_comments.utils.TimeSeries object.
    """

    # We want to be able to differentiate this conversion which can
    # lead to a real error (no output whatsoever) as opposed to the
    # one occuring at the end of the while loop acting as control flow
    focus = pd.Timestamp(focus)

    with HTMLPrettyfier(output_stream) as output:
        while True:
            data = object_data.statistics(focus, focus_days, focus_interval)
            name = focus.strftime('%d %B %Y') if focus is not None else None
            output.new_document(data, name)

            if not interactive:
                break

            try:
                focus = pd.Timestamp(raw_input('Focus on a new date> '))
            except ValueError:
                break
