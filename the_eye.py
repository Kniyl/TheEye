"""This module provides a wrapper around the facebook-sdk module in
order to ease statistical analysis around comments on a given facebook
object.

Statistics are held in TimeSeries objects. They provide multi-scale
time buckets which count events occuring at specific moments in time.
They focus their analysis around a given point in time and also covers
months and years of data.

Data are fed into TimeSeries objects thanks to the FacebookComments
parser which queries the Facebook Graph API to retrieve comments
associated to an object.
"""

import argparse
from sys import stdout
from contextlib import closing
from datetime import datetime, timedelta
from collections import Counter

import facebook


__all__ = ['TimeSeries', 'FacebookComments']


AVAILABLE_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y %m %d",
    "%m-%d-%Y",
    "%d/%m/%Y",
)


class TimeSeries(object):
    """Multi-scale time buckets objects. Allow to count events occuring
    every few minutes and every days around a given date as well as
    getting a coarse overview over the course of months and years.
    """

    SLIDING_WINDOW = 31
    TIME_INTERVAL = int(timedelta(minutes=20).total_seconds())
    INTERVALS_PER_DAY = int(timedelta(days=1).total_seconds() / TIME_INTERVAL) + 1

    def __init__(self, reference_datetime=None):
        """Create monitoring entries for every few minutes of the day
        before the referenced time and every day for the month before
        the referenced date. Also initialize the monthly and yearly
        counters.

        If reference_datetime is not specified, it defaults to
        datetime.datetime.now()
        """

        self.reference = (
            datetime.now()
            if reference_datetime is None
            else reference_datetime + timedelta(days=1)
        ).replace(second=0, microsecond=0)

        self.hours = dict(
            (self.reference - timedelta(seconds=i*self.TIME_INTERVAL), 0)
            for i in xrange(self.INTERVALS_PER_DAY)
        )
        reference_day = self.reference.date()
        self.days = dict(
            (reference_day - timedelta(days=offset), 0)
            for offset in xrange(
                reference_datetime and 1 or 0,
                self.SLIDING_WINDOW
            )
        )
        self.months = Counter()
        self.years = Counter()

    def parse_new_time(self, time, format='%Y-%m-%dT%H:%M:%S+0000'):
        """Increment the counters associated to the given point in time
        by one.

        Raise ValueError if time can not be parsed using the given
        format.
        """

        time = datetime.strptime(time, format)

        try:
            self.hours[self.floor_to_bucket(time)] += 1
        except KeyError:
            # Not interested on being that precise around that time
            pass

        date = time.date()
        try:
            self.days[date] += 1
        except KeyError:
            # Not interested on that particular day
            pass

        self.months[date.replace(day=1)] += 1
        self.years[date.replace(month=1, day=1)] += 1

    def floor_to_bucket(self, date):
        """Compute the starting time of the time interval this date
        belongs to relative to the reference time held by this object.
        """

        offset = date - self.reference
        seconds_beyond = offset.total_seconds() % self.TIME_INTERVAL
        return date - timedelta(seconds=seconds_beyond)

    def __iter__(self):
        yield 'Today', self.hours.iteritems()
        yield 'Last month', self.days.iteritems()
        yield 'Each month', self.months.iteritems()
        yield 'Each year', self.years.iteritems()


class FacebookComments(object):
    """Wrapper around the facebook-sdk module and its GraphAPI.

    This class focusses on retrieving and parsing comments associated
    to a facebook object.
    """

    COMMENTS_PER_QUERY = 1000

    def __init__(self, facebook_token):
        """Initialize a session to the Facebook Graph API using the
        provided token. The token must be associated to a user
        account and not be directly generated from a developper app,
        or this object won't be able to retrieve even public data.
        """

        self.graph = facebook.GraphAPI(facebook_token)

    def analyze(self, object_id, statistics):
        """Fetche data about the comments associated to the object_id
        and store them into statistics (in place).
        """

        for comment_time in self._fetch(object_id + '/comments'):
            statistics.parse_new_time(comment_time)

    def _fetch(self, path):
        """Retrieve data from a given path on the Facebook Graph API.

        Continuously follows the 'after' paging cursor to retrieve the
        maximum amount of data.
        """

        response = self.graph.get_object(
            path,
            limit=self.COMMENTS_PER_QUERY,
            summary=True,
            filter='stream'
        )
        total = response['summary']['total_count']
        count = 0

        while True:
            count += len(response['data'])
            print 'Got', count, 'over', total, 'comments.'
            for comment in response['data']:
                yield comment['created_time']
            try:
                after = response['paging']['cursors']['after']
            except KeyError:
                break
            else:
                response = self.graph.get_object(
                    path,
                    limit=self.COMMENTS_PER_QUERY,
                    filter='stream',
                    after=after
                )


def string_or_stdin(argument):
    """Helper type for argparse.

    Return the argument or read it from stdin if '-' is specified.
    """

    return argument if argument != '-' else raw_input()

def custom_date(argument):
    """Helper type for argparse.

    Try to convert the argument to date by analyzing various formats.
    """

    for date_format in AVAILABLE_DATE_FORMATS:
        try:
            return datetime.strptime(argument, date_format)
        except ValueError:
            pass
    raise ValueError("invalid date '{}': format not recognized.".format(argument))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), default=stdout)
    parser.add_argument('-f', '--focus-on', '--find', type=custom_date, default=None)
    parser.add_argument('token', type=string_or_stdin)
    parser.add_argument('object')

    args = parser.parse_args()

    with closing(args.output) as output:
        statistics = TimeSeries(args.focus_on)
        parser = FacebookComments(args.token)

        try:
            parser.analyze(args.object, statistics)
        finally:
            # Writte anything we fetched in case of error
            for event, data in statistics:
                output.write('{}:\n'.format(event))
                for date, amount in sorted(data):
                    output.write('\t{}:\t{}\n'.format(date, amount))
