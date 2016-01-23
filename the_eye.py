import sys
import math
import facebook
import argparse
from pprint import pformat as pretty_string
from getpass import getpass


COMMENT_PER_QUERY = 999


def get_secret(secret=None):
    return secret if secret is not None else getpass()


class FacebookComments(object):
    def __init__(self, token=None, app_id=None, app_secret=None):
        if token is None:
            token = facebook.get_app_access_token(app_id, get_secret(app_secret))
        self.graph = facebook.GraphAPI(token)

    def analyse(self, object_id, output_file):
        for comment in self._fetch(object_id + '/comments'):
            output_file.write(comment)
            output_file.write('\n')

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


class StringOrStdinAction(argparse.Action):
    def __call__(self, parser, namespace, value, option=None):
        setattr(namespace, self.dest, value if value != '-' else raw_input())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument('token', action=StringOrStdinAction)
    parser.add_argument('object')

    args = parser.parse_args()

    comments = FacebookComments(args.token)
    data = comments.analyse(args.object, args.output)
    args.output.close()
