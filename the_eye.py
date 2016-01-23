import argparse
from sys import stdout
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
    SLIDING_WINDOW = 31
    TIME_INTERVAL = int(timedelta(minutes=20).total_seconds())
    INTERVALS_PER_DAY = int(timedelta(days=1).total_seconds() / TIME_INTERVAL) + 1

    def __init__(self, reference_date=None):
        self.reference = (
            datetime.today()
            if reference_date is None
            else reference_date + timedelta(days=1)
        ).replace(second=0, microsecond=0)

        self.hours = dict(
            (self.reference - timedelta(seconds=i*self.TIME_INTERVAL), 0)
            for i in xrange(self.INTERVALS_PER_DAY)
        )
        reference_day = self.reference.date()
        self.days = dict(
            (reference_day - timedelta(days=offset), 0)
            for offset in xrange(
                reference_date and 1 or 0,
                self.SLIDING_WINDOW
            )
        )
        self.months = Counter()
        self.years = Counter()

    def parse_new_time(self, time, format='%Y-%m-%dT%H:%M:%S+0000'):
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
        offset = date - self.reference
        seconds_beyond = offset.total_seconds() % self.TIME_INTERVAL
        return date - timedelta(seconds=seconds_beyond)

    def __iter__(self):
        yield 'Today', self.hours.iteritems()
        yield 'Last month', self.days.iteritems()
        yield 'Each month', self.months.iteritems()
        yield 'Each year', self.years.iteritems()


class FacebookComments(object):
    COMMENTS_PER_QUERY = 1000

    def __init__(self, facebook_token, output_file, statistics=None):
        self.graph = facebook.GraphAPI(facebook_token)
        self.stats = statistics if statistics is not None else TimeSeries()
        self.output = output_file

    def analyze(self, object_id):
        for comment_time in self._fetch(object_id + '/comments'):
            self.stats.parse_new_time(comment_time)

    def _fetch(self, path):
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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        for event, data in self.stats:
            self.output.write('{}:\n'.format(event))
            if not data:
                self.output.write('No comments\n')
            for date, amount in sorted(data):
                self.output.write('\t{}:\t{}\n'.format(date, amount))
        self.output.close()


def string_or_stdin(argument):
    return argument if argument != '-' else raw_input()

def custom_date(argument):
    for date_format in AVAILABLE_DATE_FORMATS:
        try:
            return datetime.strptime(argument, date_format)
        except ValueError:
            pass
    raise ValueError("invalid date '{}': format not recognized.".format(reference_date))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), default=stdout)
    parser.add_argument('-f', '--focus-on', '--find', type=custom_date, default=None)
    parser.add_argument('token', type=string_or_stdin)
    parser.add_argument('object')

    args = parser.parse_args()

    with FacebookComments(args.token, args.output, TimeSeries(args.focus_on)) as parser:
        parser.analyze(args.object)
