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

import datetime
from collections import Counter, OrderedDict
from itertools import takewhile, chain, izip, repeat, count

import facebook


class TimeSeries(Counter):
    """Multi-scale time buckets objects. Allow to count events occuring
    every few minutes and every days around a given date as well as
    getting a coarse overview over the course of months and years.
    """

    def parse_new_time(self, time, format='%Y-%m-%dT%H:%M:%S+0000'):
        """Increment the counter associated to the given point in time
        by one. Time is rounded down to the nearest minute.

        Raise ValueError if time can not be parsed using the given
        format.
        """

        time = datetime.datetime.strptime(time, format)
        self[time.replace(second=0, microsecond=0)] += 1

    def generate_statistics(self, reference_datetime=None,
                            days_focussed=31, minutes_interval=20):
        """Generate the underlying data at different time scales with
        a particular focus around reference_datetime. Each scale is
        broader than the previous one:
         - the day before reference_date with minutes_interval gaps;
         - up to days_focussed days before reference_date;
         - each month between the oldest and the newest date stored;
         - each year between the oldest and the newest date stored.

        Yield OrderedDicts for each scale.
        """

        if not self:
            raise ValueError('no data to compute from')

        oldest = min(self)
        newest = max(self)
        begin = oldest.year

        # Focus around a specific day
        reference = (
            datetime.datetime.now()
            if reference_datetime is None
            else reference_datetime
        ).replace(second=0, microsecond=0)
        reference_date = reference.date()
        # Account for the fact that the reference is a little bit
        # behind the last items we are interested in.
        if reference == reference.replace(minute=0, hour=0):
            reference += datetime.timedelta(days=1)
        else:
            reference += datetime.timedelta(minutes=1)

        # Not using Counter initialization from iterable here since I
        # want to explicitly create keys for years whose total is 0.
        yearly_data = OrderedDict(
            (y, 0) for y in xrange(begin, newest.year + 1)
        )


        # Manually generate all month because there is no timedelta
        # constructor to deal with months.
        monthly_data = OrderedDict(
            (datetime.date(year, month, 1), 0)
            for year, month in takewhile(
                lambda d: datetime.datetime(*d, day=1) <= newest,
                (d for m in chain(
                    (izip(repeat(begin), xrange(oldest.month, 13)),),
                    (izip(repeat(y), xrange(1, 13)) for y in count(begin + 1))
                ) for d in m)
            )
        )

        dayly_data = OrderedDict(
            (reference_date - datetime.timedelta(days=offset), 0)
            for offset in reversed(xrange(days_focussed))
        )

        interval = int(datetime.timedelta(minutes=minutes_interval).total_seconds())
        buckets = int(datetime.timedelta(days=1).total_seconds() / interval) + 1
        hourly_data = OrderedDict(
            (reference - datetime.timedelta(seconds=i*interval), 0)
            for i in reversed(xrange(buckets))
        )

        for cur_datetime, amount in self.iteritems():
            cur_date = cur_datetime.date()
            yearly_data[cur_date.year] += amount
            monthly_data[cur_date.replace(day=1)] += amount
            try:
                dayly_data[cur_date] += amount
            except KeyError:
                pass

            # Compute the starting time of the time interval this date
            # belongs to relative to the reference time.
            offset = cur_datetime - reference
            beyond = offset.total_seconds() % interval
            cur_bucket = cur_datetime - datetime.timedelta(seconds=beyond)
            try:
                hourly_data[cur_bucket] += amount
            except KeyError:
                pass

        yield hourly_data
        yield dayly_data
        yield monthly_data
        yield yearly_data


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

    def analyze(self, object_id):
        """Fetch data about the comments associated to the object_id"""

        return self._fetch(object_id + '/comments')

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

