# TheEye

## Installation

Written using Python 2.7

Virtualenv setup:

 - `virtualenv2 <env_name>`
 - `source <env_name>/bin/activate`
 - `pip install -r requirements.txt`

## Usage

Detailled help available using `python the_eye.py --help`

Example usage:

 - `python the_eye.py -o foobar.html <facebook_token> <object_id>`
 - `cat my_facebook_token.txt | python the_eye.py - <object_id> > foobar.html`
 - `cat my_facebook_token.txt | python the_eye.py - <object_id> -o foobar.html -f 2015-09-23`
