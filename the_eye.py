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

import os.path
import argparse
import datetime
from sys import stdout, stderr
from collections import Counter, OrderedDict
from itertools import takewhile, chain, izip, repeat, count

import facebook


__all__ = ['TimeSeries', 'FacebookComments']


AVAILABLE_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y %m %d",
    "%m-%d-%Y",
    "%d/%m/%Y",
)


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


class Prettyfier(object):
    """Utility class to output TimeSeries data into a file.
    
    Mimics contextlib.closing behaviour and capabilities to output
    data into the underlying file object.
    """

    def __init__(self, stream):
        """Initialize handling of the given file-like object"""

        self.output = stream

    def __enter__(self):
        """Use this object as a context manager"""

        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Close the underlying file when exiting the context manager"""

        self.output.close()

    def new_document(self, statistics, day_name=None):
        """Clear the underlying file and output the newly provided
        statistics. Use day_name to format legends.
        """

        if not self.output.isatty():
            # We want to avoid IOErrors on sys.stdout and alike
            self.output.seek(0)
            self.output.truncate()

        graph_names = (
            ('Today', 'Last month', 'By month', 'By year')
            if day_name is None else
            (day_name, 'Month before {}'.format(day_name), 'By month', 'By year')
        )

        self._write_data(izip(graph_names, statistics))
        self.output.flush()

    def _write_data(self, data_iterator):
        """Format the provided data into a suitable representation and
        write it into the underlying file.
        """

        for event, data in data_iterator:
            self.output.write('{}:\n'.format(event))
            for date, amount in data.iteritems():
                self.output.write('    {}:    {}\n'.format(date, amount))


class HTMLPrettyfier(Prettyfier):
    """Utility class to output TimeSeries data into an HTML file"""

    def _write_data(self, data_iterator):
        write = self.output.write

        write('<!doctype html>\n')
        write('<html lang="en">\n')
        write('  <head>\n')
        write('    <title>Comments for Facebook object</title>\n')
        write('    <style>\n')
        write('      html, body {background: white; color: black;')
        write(' width: 100%; height: 100%; padding: 0px; margin: 0px;}\n')
        write('      .wrapper {width: 80%; height: 80%; padding: 0px; margin: 0px auto;}\n')
        write('      canvas {width: 100%; height: 100%;}\n')
        write('      h1 {text-align: center; padding: 0px; margin: 50px 0px;}\n')
        write('    </style>\n')

        # Minified scripts have so long lines, they lie in their own file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(script_dir, 'scripts.html')) as f:
            for line in f:
                write(line)

        write('    <script type="text/javascript">\n')
        write('      function load() {\n')
        write('        Chart.defaults.global["responsive"] = true;\n')

        main_label, data = next(data_iterator)

        write('        var ctx = document.getElementById("chart-hours").getContext("2d");\n')
        write('        var hour_data = {\n')
        write('          labels: {},\n'.format([d.strftime('%H:%M') for d in data]))
        write('          datasets: [{\n')
        write('            fillColor: "rgba(20, 100, 250, 0.2)",\n')
        write('            strokeColor: "rgba(20, 100, 250, 1)",\n')
        write('            data: {}\n'.format(data.values()))
        write('          }]\n')
        write('        }\n')
        write('        var hour_chart = new Chart(ctx).Line(hour_data, {})\n')

        days_label, data = next(data_iterator)

        write('        ctx = document.getElementById("chart-days").getContext("2d");\n')
        write('        var day_data = {\n')
        write('          labels: {},\n'.format([d.strftime('%d %b') for d in data]))
        write('          datasets: [{\n')
        write('            fillColor: "rgba(20, 100, 250, 0.2)",\n')
        write('            strokeColor: "rgba(20, 100, 250, 1)",\n')
        write('            data: {}\n'.format(data.values()))
        write('          }]\n')
        write('        }\n')
        write('        var day_chart = new Chart(ctx).Line(day_data, {})\n')

        months_label, data = next(data_iterator)

        write('        ctx = document.getElementById("chart-months").getContext("2d");\n')
        write('        var month_data = {\n')
        write('          labels: {},\n'.format([d.strftime('%b %Y') for d in data]))
        write('          datasets: [{\n')
        write('            fillColor: "rgba(20, 100, 250, 0.2)",\n')
        write('            strokeColor: "rgba(20, 100, 250, 1)",\n')
        write('            data: {}\n'.format(data.values()))
        write('          }]\n')
        write('        }\n')
        write('        var month_chart = new Chart(ctx).Line(month_data, {})\n')

        years_label, data = next(data_iterator)

        write('        ctx = document.getElementById("chart-years").getContext("2d");\n')
        write('        var year_data = [{\n')
        write('          {}\n'.format('},{'.join('value: {}, label: {}'
                                .format(v, k) for k, v in data.iteritems())))
        write('        }]\n')
        write('        var year_chart = new Chart(ctx).Doughnut(year_data, {})\n')
        write('      }\n')
        write('    </script>\n')

        write('  </head>\n')
        write('  <body onload="load();">\n')

        helper = (
            (main_label, 'hours'),
            (days_label, 'days'),
            (months_label, 'months'),
            (years_label, 'years'),
        )

        for title, name in helper:
            write('    <h1>{}</h1>\n'.format(title))
            write('    <div class="wrapper">\n')
            write('      <canvas id="chart-{}"></canvas>\n'.format(name))
            write('    </div>\n')

        write('  </body>\n')
        write('</html>\n')


def string_or_stdin(argument, raw_input=raw_input):
    """Helper type for argparse.

    Return the argument or read it from stdin if '-' is specified.

    The raw_input parameter can be used to customize or mock the way
    data are read.
    """

    return argument if argument != '-' else raw_input()

def custom_date(argument):
    """Helper type for argparse.

    Try to convert the argument to date by analyzing various formats.
    """

    for date_format in AVAILABLE_DATE_FORMATS:
        try:
            return datetime.datetime.strptime(argument, date_format)
        except ValueError:
            pass
    raise ValueError("invalid date '{}': format not recognized.".format(argument))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), default=stdout)
    parser.add_argument('-f', '--focus-on', '--find', type=custom_date, default=None)
    parser.add_argument('-i', '--interactive', action='store_true')
    parser.add_argument('token', type=string_or_stdin)
    parser.add_argument('object')

    args = parser.parse_args()

    with HTMLPrettyfier(args.output) as output:
        storage = TimeSeries()
        parser = FacebookComments(args.token)

        try:
            for comment_time in parser.analyze(args.object):
                storage.parse_new_time(comment_time)
        except Exception:
            if not storage:
                # Nothing fetched, abort now
                raise

            import traceback
            traceback.print_exc()
            print >> stderr, 'Some data were fetched, continuing analysis'

        focus = args.focus_on
        while True:
            name = focus.strftime('%d %B %Y') if focus is not None else None
            output.new_document(storage.generate_statistics(focus), name)

            if not args.interactive:
                break

            try:
                focus = custom_date(raw_input('Focus on a new date> '))
            except ValueError:
                break
