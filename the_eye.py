"""CLI built around the facebook_comments package.

Provide ways to customize a call to statistical_analysis from this
package.
"""

import argparse
from sys import stdout
from itertools import chain

from facebook_comments import (statistical_analysis,
                               read_from_file, read_from_facebook)


# Inspired from http://stackoverflow.com/a/22157136/5069029
class NewLinesFormatter(argparse.HelpFormatter):
    """Help text formatter for argparse that will keep newlines in
    formatted text.
    """

    def _split_lines(self, text, width):
        """Override argparse.HelpFormatter behaviour"""

        old_formatter = super(NewLinesFormatter, self)._split_lines
        return list(chain.from_iterable(
            old_formatter(line, width) for line in text.splitlines()))


def string_or_stdin(argument, raw_input=raw_input):
    """Helper type for argparse.

    Return the argument or read it from stdin if '-' is specified.

    The raw_input parameter can be used to customize or mock the way
    data are read.
    """

    return argument if argument != '-' else raw_input()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Retrieves, parses, '
            'analyze, and store data about comments on Facebook posts.',
            formatter_class=NewLinesFormatter)
    parser.add_argument('-o', '--output', metavar='FILE', default=stdout,
            type=argparse.FileType('w'), help='Path to the file where '
            'HTML output will be written. If not provided, the standard '
            'output will be used.')
    parser.add_argument('-f', '--focus-on', '--find', metavar='DATE',
            default='now', help='A date around which detailled analysis '
            'will be performed. If not provided, the current date and '
            'time will be used.')
    parser.add_argument('-d', '--days', metavar='N', type=int, default=15,
            help='Number of days before and after the --focus-on date a '
            'detailled analysis should occur. (default: 15, for a total of '
            '31 days analyzed.)')
    parser.add_argument('-m', '--minutes', metavar='N', type=int, default=20,
            help='Interval of time, in minutes, the --focus-on day should be '
            'sliced into for the detailled analysis. (default: 20, for a '
            'total of 72 slices.)')
    parser.add_argument('-i', '--interactive', action='store_true', help=''
            'Enables an interactive session to analyze a dataset. After each '
            'write to the output file, the program will ask for a new date '
            'to compute detailled statistics from. Any input that is not a '
            'valid date will terminate the session.')
    parser.add_argument('-e', '--export', metavar='FILE', help='Path to a '
            'file where raw data will be written for future analysis.')
    parser.add_argument('token', type=string_or_stdin, nargs='?', help=''
            'Facebook user token to use to connect to Facebook Graph API. '
            'The token should be valid and the user it is bound to should '
            'have sufficient privileges to read data from the Facebook '
            'object.\nIf \'-\' is provided instead of the token, the '
            'program will read the token value from the standard input.\n'
            'If no value is provided, the program will read raw data from a '
            'file instead of fetching them from Facebook.')
    parser.add_argument('object', help='The Facebook object ID to fetch data '
            'from. If TOKEN is not provided, this value should be the path '
            'to the file where raw data are stored.')

    args = parser.parse_args()

    if args.token is None:
        comments = read_from_file(args.object)
    else:
        comments = read_from_facebook(args.token, args.object)

    if args.export is not None:
        comments.pickle(args.export)

    statistical_analysis(
            comments, args.output, args.interactive,
            args.focus_on, args.days, args.minutes)

