import sys
import datetime
import argparse
from collections import Counter
import facebook
from pprint import pformat as pretty_string


COMMENT_PER_QUERY = 1000
DAYS_COUNT = datetime.timedelta(days=30)


class TimeSeries(object):
    def __init__(self):
        self.today = datetime.date.today()
        self.start_observation = self.today - DAYS_COUNT
        self.hours = Counter()
        self.days = Counter()
        self.months = Counter()
        self.years = Counter()

    def parse_new_time(self, time, format='%Y-%m-%dT%H:%M:%S+0000'):
        time = datetime.datetime.strptime(time, format)
        date = time.date()
        if date == self.today:
            self.hours[time.hour] += 1
        if date >= self.start_observation:
            self.days[date] += 1
        self.months[date.replace(day=1)] += 1
        self.years[date.replace(month=1, day=1)] += 1

    def __iter__(self):
        yield 'Today', self.hours.iteritems()
        yield 'Last month', self.days.iteritems()
        yield 'Each month', self.months.iteritems()
        yield 'Each year', self.years.iteritems()


class FacebookComments(object):
    def __init__(self, token, output):
        self.graph = facebook.GraphAPI(token)
        self.comments = TimeSeries()
        self.output = output

    def analyze(self, object_id):
        for comment_time in self._fetch(object_id + '/comments'):
            self.comments.parse_new_time(comment_time)

    def _fetch(self, path):
        response = self.graph.get_object(path, limit=COMMENT_PER_QUERY, summary=True, filter='stream')
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
                try:
                    response = self.graph.get_object(path, limit=COMMENT_PER_QUERY, filter='stream', after=after)
                except facebook.GraphAPIError as e:
                    print 'Error occured (', e, '), stopping after', count, 'comments.'
                    break

    def __enter__(self):
        return self

    def __exit__(self, a, b, c):
        for event, data in self.comments:
            self.output.write('{}:\n'.format(event))
            for date, amount in sorted(data):
                self.output.write('\t{}:\t{}\n'.format(date, amount))
        self.output.close()


class StringOrStdinAction(argparse.Action):
    def __call__(self, parser, namespace, value, option=None):
        setattr(namespace, self.dest, value if value != '-' else raw_input())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument('token', action=StringOrStdinAction)
    parser.add_argument('object')

    args = parser.parse_args()

    with FacebookComments(args.token, args.output) as parser:
        parser.analyze(args.object)
