import os.path
from itertools import izip, izip_longest


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
            ('Today', 'Past and coming days', 'By month', 'By year')
            if day_name is None else
            (day_name, 'Days around {}'.format(day_name), 'By month', 'By year')
        )

        self._write_data(graph_names, statistics)
        self.output.flush()

    def _write_data(self, graph_names, data_iterator):
        """Format the provided data into a suitable representation and
        write it into the underlying file.
        """

        for event, data in izip(graph_names, data_iterator):
            self.output.write('{}:\n'.format(event))
            for date, amount in data.iteritems():
                self.output.write('    {}:    {}\n'.format(date, int(amount)))


class HTMLPrettyfier(Prettyfier):
    """Utility class to output TimeSeries data into an HTML file"""

    def _write_data(self, graph_names, data_iterator):
        def _gen_helper():
            custom_iterator = enumerate(izip_longest(
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
                               for k, v in data.iteritems())
                    script = """
                        ctx = document.getElementById("{}").getContext("2d");
                        new Chart(ctx).Doughnut([{{
                            {}
                        }}], {{}})
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
                    """.format(dom, labels, data.values())

                yield canvas, script

        canvas, scripts = izip(*_gen_helper())
        tabs = ('<li><a href="#tabs-{}">{}</a></li>'.format(i, title)
                for i, title in enumerate(graph_names))

        script_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(script_dir, 'Chart.min.js')) as f:
            chartjs = f.read()

        with open(os.path.join(script_dir, 'template.html')) as f:
            template = f.read()

        self.output.write(template.format(
            chartjs,
            '\n'.join(scripts),
            '\n'.join(tabs),
            '\n'.join(canvas)
        ))

