import os.path
from itertools import izip


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

