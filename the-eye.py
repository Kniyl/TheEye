import sys
import facebook
import argparse
from pprint import pformat as pretty_string
from getpass import getpass


def get_secret(secret=None):
    return secret if secret is not None else getpass()


def get_app_token(token=None, app_id=None, app_secret=None):
    return (token
            if token is not None
            else facebook.get_app_access_token(
                    app_id,
                    get_secret(app_secret)
                 )
           )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument('-s', '--app-secret')
    parser.add_argument('-a', '--app-id')
    parser.add_argument('token', nargs='?')

    args = parser.parse_args()
    token = get_app_token(args.token, args.app_id, args.app_secret)

    graph = facebook.GraphAPI(token)
    obj = graph.get_object('10151775534413086')

    args.output.write(pretty_string(obj))
    args.output.close()
