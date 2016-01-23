import sys
import facebook
import argparse
from pprint import pformat as pretty_string
from getpass import getpass


def get_secret(secret=None):
    return secret if secret is not None else getpass()


class FacebookComments(object):
    def __init__(self, token=None, app_id=None, app_secret=None):
        if token is None:
            token = facebook.get_app_access_token(app_id, get_secret(app_secret))
        self.graph = facebook.GraphAPI(token)

    def analyse(self, object_id, output_file):
        for comment in self.fetch_comments(object_id + '/comments'):
            output_file.write(comment)
            output_file.write('\n')

    def fetch_comments(self, path):
        response = self.graph.get_object(path, limit=1000, summary=True, filter='stream')
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
                    response = self.graph.get_object(path, limit=1000, after=after, filter='stream')
                except facebook.GraphAPIError as e:
                    print 'Error occured (', e, '), stopping after', count, 'comments.'
                    break


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument('-s', '--app-secret')
    parser.add_argument('-a', '--app-id')
    parser.add_argument('token', nargs='?')

    args = parser.parse_args()

    comments = FacebookComments(args.token, args.app_id, args.app_secret)
    data = comments.analyse('10151775534413086', args.output)
    args.output.close()
