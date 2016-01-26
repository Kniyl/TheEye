import argparse
from sys import stdout

from facebook_comments import parse_object, custom_date


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
    parser.add_argument('-f', '--focus-on', '--find', type=custom_date, default=None)
    parser.add_argument('-i', '--interactive', action='store_true')
    parser.add_argument('-e', '--export')
    parser.add_argument('-d', '--days', type=int, default=15)
    parser.add_argument('-m', '--minutes', type=int, default=20)
    parser.add_argument('token', type=string_or_stdin, nargs='?')
    parser.add_argument('object')

    args = parser.parse_args()

    parse_object(args.token, args.object, args.output, args.export, args.interactive, args.focus_on)

