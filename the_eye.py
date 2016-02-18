"""CLI to fetch comments from Facebook posts.

Usage:
    the_eye.py [options] [- | TOKEN] FACEBOOK_ID
    the_eye.py [options] PATH

Positional arguments:
    TOKEN               Facebook user token to use to connect to Facebook
                        Graph API. The token should be valid and the user
                        it is bound to should have sufficient privileges
                        to read data from the Facebook object.
    FACEBOOK_ID         The Facebook object ID to fetch data from.
    PATH                File to raw data fetched from a previous analysis.

Options:
    -h --help           Show this screen
    -o --output=FILE    Path to the file where HTML output will be
                        written. Write to the standard output if none
                        is provided.
    -f --focus-on --find=DATE
                        A date around which detailled analysis will be
                        performed [default: now]
    -d --days=N         Number of days before and after the --focus-on
                        date a detailled analysis should occur [default: 15]
    -m --minutes=N      Interval of time, in minutes, the --focus-on day
                        Should be sliced into for the detailled analysis.
                        [default: 20]
    -i --interactive    Enables an interactive session to analyze a dataset.
                        After each write to the output file, the program
                        will ask for a new date to compute detailled
                        statistics from. Any input that is not a valid
                        date will terminate the session.
    -e --export=FILE    Path to a file where raw data will be written for
                        future analysis.
"""

import os.path
from sys import stdout, stderr
from itertools import zip_longest
from collections import OrderedDict
from operator import itemgetter

import requests
import pandas as pd
from pandas.tseries.frequencies import to_offset

from docopt import docopt


FACEBOOK_URL = 'https://graph.facebook.com/v{:.1f}/{}/comments'
QUERY_SIZE = 4000


def parse_arg(argument, parser, error_message=""):
    try:
        return parser(argument)
    except ValueError:
        exit(error_message)


def facebook_comments(token, object_id, api_version=2.5):
    """Retrieve comments from a given path on the Facebook Graph API.

    Continuously follows the 'after' paging cursor to retrieve the
    maximum amount of data.
    """

    path = FACEBOOK_URL.format(api_version, object_id)
    payload = {
            'access_token': token,
            'fields': 'created_time',
            'limit': QUERY_SIZE,
            'filter': 'stream',
    }

    try:
        response = requests.get(path, params=payload).json()

        while True:
            # response['data'] is a list of dictionaries containing
            # ids and created_time for each element in the given path
            yield from map(itemgetter('created_time'), response['data'])

            try:
                # follow paging links, only know method to get all data
                payload['after'] = response['paging']['cursors']['after']
            except KeyError:
                # no more data available
                break
            else:
                response = requests.get(path, params=payload).json()
    except (requests.exceptions.RequestException, ValueError):
        # On networking issue, warn the user with the traceback but
        # continue on processing data that was already fetched.
        # .json() can raise ValueError when no suitable data is available
        import traceback
        traceback.print_exc()
        print('\nAn error occured but continuing on processing '
              'data already fetched', file=stderr)


def truncate_to_frequency(time, frequency='1min'):
    """Convert a point in time to the latest timestamp a frequency
    occured.
    """

    freq = to_offset(frequency).delta.value
    return pd.Timestamp((time.value // freq) * freq)


def analyze(comments, reference_datetime, days_focussed, minutes_interval):
    """Generate data for the comments at different time scales with
    a particular focus around reference_datetime. Each scale is
    broader than the previous one:
     - the day containing reference_date with minutes_interval gaps;
     - up to days_focussed days before and after reference_date;
     - each month between the oldest and the newest date stored;
     - each year between the oldest and the newest date stored.

    Yield OrderedDicts for each scale.
    """
    ref = truncate_to_frequency(reference_datetime, '1D')
    frequency = '{}min'.format(minutes_interval)

    days_offset = pd.DateOffset(days=days_focussed)
    days = pd.date_range(ref - days_offset, ref + days_offset, freq='1D')
    hours = pd.date_range(ref, ref + pd.DateOffset(days=1), freq=frequency)

    return map(OrderedDict, (
        comments.resample(frequency, how='sum').reindex(hours).fillna(0),
        comments.resample('1D', how='sum').reindex(days).fillna(0),
        comments.resample('1MS', how='sum').fillna(0),
        comments.resample('1AS', how='sum').fillna(0),
    ))


def html_writer(output_file, data_iterator, graph_names):
    """Utility function to output TimeSeries data into an HTML file"""

    def _gen_helper():
        custom_iterator = enumerate(zip_longest(
            graph_names, # Titles to display in <h1>
            data_iterator, # TimeSeries
            ('%H:%M', '%d %b', '%b %Y') # X-axis ticks format
        ))
        for i, (title, data, time_format) in custom_iterator:
            dom = 'chart-{}'.format(i)
            canvas = """
                <div id="tabs-{}">
                    <h1>{}</h1>
                    <div class="wrapper">
                        <canvas id="{}"></canvas>
                    </div>
                </div>
            """.format(i, title, dom)

            if time_format is None:
                content = ('value: {}, label: {}'.format(v, k.strftime('%Y'))
                           for k, v in data.items())
                script = """
                    ctx = document.getElementById("{}").getContext("2d");
                    new Chart(ctx).Doughnut([{{
                        {}
                    }}], {{}});
                """.format(dom, '},{'.join(content))
            else:
                labels = [d.strftime(time_format) for d in data]
                script = """
                    ctx = document.getElementById("{}").getContext("2d");
                    new Chart(ctx).Line({{
                        labels: {},
                        datasets: [{{
                            fillColor: "rgba(20, 100, 250, 0.2)",
                            strokeColor: "rgba(20, 100, 250, 1)",
                            data: {}
                        }}]
                    }}, {{}});
                """.format(dom, labels, list(data.values()))

            yield canvas, script

    canvas, scripts = zip(*_gen_helper())
    tabs = ('<li><a href="#tabs-{}">{}</a></li>'.format(i, title)
            for i, title in enumerate(graph_names))

    script_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(script_dir, 'Chart.min.js')) as f:
        chartjs = f.read()

    with open(os.path.join(script_dir, 'template.html')) as f:
        template = f.read()

    print(template.format(
            chartjs,
            '\n'.join(scripts),
            '\n'.join(tabs),
            '\n'.join(canvas)
        ), file=output_file)


def write(filename, statistics, day_name):
    """Wrapper to provide a file-like object and the proper labels to
    html_writer.
    """

    graph_names = (
        ('Today', 'Past and coming days', 'By month', 'By year')
        if day_name is None else
        (day_name, 'Days around {}'.format(day_name), 'By month', 'By year')
    )

    if filename is None:
        html_writer(stdout, statistics, graph_names)
    else:
        with open(filename, 'w') as f:
            html_writer(f, statistics, graph_names)


if __name__ == '__main__':
    args = docopt(__doc__)

    days = parse_arg(args['--days'], int, "--days: expected integer")
    minutes = parse_arg(args['--minutes'], int, "--minutes: expected integer")
    focus = parse_arg(args['--find'], pd.Timestamp, "--find: unparsable date")

    if args['-']:
        args['TOKEN'] = input()

    if args['PATH'] is not None:
        comments = pd.read_pickle(args['PATH'])
    else:
        data = pd.to_datetime(
                list(facebook_comments(args['TOKEN'], args['FACEBOOK_ID'])),
                format='%Y-%m-%dT%H:%M:%S+0000')
        comments = (pd
                .Series(data)
                .value_counts()
                .groupby(truncate_to_frequency)
                .sum())

    if args['--export'] is not None:
        try:
            comments.to_pickle(args['--export'])
        except IOError as e:
            print('Error writing exported file:', e.args, file=stderr) 

    while True:
        data = analyze(comments, focus, days, minutes)
        write(args['--output'], data, focus.strftime('%d %B %Y'))

        if not args['--interactive']:
            break

        try:
            focus = pd.Timestamp(input('Focus on a new date> '))
        except ValueError:
            break

