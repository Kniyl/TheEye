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

from collections import OrderedDict
from itertools import imap, chain
from operator import itemgetter

import facebook
import pandas as pd
from pandas.tseries.frequencies import to_offset


class TimeSeries(object):
    """Multi-scale time buckets objects. Allow to count events occuring
    every few minutes and every days around a given date as well as
    getting a coarse overview over the course of months and years.
    """

    def __init__(self, iterable=None, format='%Y-%m-%dT%H:%M:%S+0000'):
        """Store date contained in the iterable as an histogram using
        one minute resolution. Parse each date using the provided
        format.
        """

        if iterable is None:
            iterable = ()
        else:
            # Convert iterators/generator to lists so pandas is happy
            iterable = list(iterable)

        serie = pd.to_datetime(iterable, format=format)
        self.histogram = (pd
                .Series(serie)
                .value_counts()
                .groupby(self.truncate_to_frequency)
                .sum()
        )

    @staticmethod
    def truncate_to_frequency(time, frequency='1min'):
        """Convert a point in time to the latest timestamp a frequency
        occured.
        """

        freq = to_offset(frequency).delta.value
        return pd.Timestamp((time.value // freq) * freq)

    def statistics(self, reference_datetime='now',
                   days_focussed=15, minutes_interval=20):
        """Generate the underlying data at different time scales with
        a particular focus around reference_datetime. Each scale is
        broader than the previous one:
         - the day containing reference_date with minutes_interval gaps;
         - up to days_focussed days before and after reference_date;
         - each month between the oldest and the newest date stored;
         - each year between the oldest and the newest date stored.

        Yield OrderedDicts for each scale.
        """

        ref = pd.Timestamp(reference_datetime)
        ref = self.truncate_to_frequency(ref, '1D')
        frequency = '{}min'.format(minutes_interval)

        days_offset = pd.DateOffset(days=days_focussed)
        days = pd.date_range(ref - days_offset, ref + days_offset, freq='1D')
        hours = pd.date_range(ref, ref + pd.DateOffset(days=1), freq=frequency)

        return imap(OrderedDict, (
            self.histogram.resample(frequency, how='sum').reindex(hours).fillna(0),
            self.histogram.resample('1D', how='sum').reindex(days).fillna(0),
            self.histogram.resample('1MS', how='sum').fillna(0),
            self.histogram.resample('1AS', how='sum').fillna(0),
        ))

    def pickle(self, path):
        """Write the underlying data to an HDFStore"""

        self.histogram.to_pickle(path)

    @classmethod
    def unpickle(cls, path):
        """Read data from an HDFStore to initialize a new serie"""

        serie = cls()
        serie.histogram = pd.read_pickle(path)
        return serie


class FacebookComments(object):
    """Wrapper around the facebook-sdk module and its GraphAPI.

    This class focusses on retrieving and parsing comments associated
    to a facebook object.
    """

    COMMENTS_PER_QUERY = 4000
    API_VERSION = 2.5

    def __init__(self, facebook_token):
        """Initialize a session to the Facebook Graph API using the
        provided token. The token must be associated to a user
        account and not be directly generated from a developper app,
        or this object won't be able to retrieve even public data.
        """

        self.graph = facebook.GraphAPI(facebook_token)

    def analyze(self, object_id, edge='comments', version=None):
        """Fetch data about the comments associated to the object_id"""

        if version is None:
            version = self.API_VERSION

        path = 'v{:.1f}/{}/{}'.format(version, object_id, edge)

        # flatten the various API calls
        return chain.from_iterable(self._fetch(path))

    def _fetch(self, path):
        """Retrieve data from a given path on the Facebook Graph API.

        Continuously follows the 'after' paging cursor to retrieve the
        maximum amount of data.
        """

        kwargs = {
            'fields': 'created_time',
            'limit': self.COMMENTS_PER_QUERY,
            'filter': 'stream',
        }

        response = self.graph.get_object(path, **kwargs)

        while True:
            # response['data'] is a list of dictionaries containing
            # ids and created_time for each element in the given path
            yield imap(itemgetter('created_time'), response['data'])

            try:
                # follow paging links, only know method to get all data
                after = response['paging']['cursors']['after']
            except KeyError:
                # no more data available
                break
            else:
                response = self.graph.get_object(path, after=after, **kwargs)

