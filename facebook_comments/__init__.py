import sys
from datetime import datetime

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
                 interactive=False,
                 focus=None,
                 focus_days=31,
                 focus_interval=20):
    """Provide a session to fetch and analyze data from a facebook
    object. Data are retrieved on behalf of the user represented in
    the given token.
    """

    with HTMLPrettyfier(output_stream) as output:
        storage = TimeSeries()
        parser = FacebookComments(user_token)

        try:
            for comment_time in parser.analyze(object_id):
                storage.parse_new_time(comment_time)
        except Exception:
            if not storage:
                # Nothing fetched, abort now
                raise

            import traceback
            traceback.print_exc()
            print >> sys.stderr, 'Some data were fetched, continuing analysis'

        while True:
            name = focus.strftime('%d %B %Y') if focus is not None else None
            data = storage.generate_statistics(focus, focus_days, focus_interval)
            output.new_document(data, name)

            if not interactive:
                break

            try:
                focus = custom_date(raw_input('Focus on a new date> '))
            except ValueError:
                break
