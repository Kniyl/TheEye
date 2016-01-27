import argparse
from sys import stdout

from facebook_comments import (statistical_analysis,
                               read_from_file, read_from_facebook)


def string_or_stdin(argument, raw_input=raw_input):
    """Helper type for argparse.

    Return the argument or read it from stdin if '-' is specified.

    The raw_input parameter can be used to customize or mock the way
    data are read.
    """

    return argument if argument != '-' else raw_input()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), default=stdout)
    parser.add_argument('-f', '--focus-on', '--find', default='now')
    parser.add_argument('-i', '--interactive', action='store_true')
    parser.add_argument('-e', '--export')
    parser.add_argument('-d', '--days', type=int, default=15)
    parser.add_argument('-m', '--minutes', type=int, default=20)
    parser.add_argument('token', type=string_or_stdin, nargs='?')
    parser.add_argument('object')

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

