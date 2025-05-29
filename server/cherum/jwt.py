import jwt
import click
from flask import request, current_app


def create_token():
    return jwt.encode({'issuer': current_app.config['APP_NAME']},
                      current_app.config['SECRET_KEY'],
                      algorithm='HS256')


def get_token():
    header = request.headers.get('Authorization')
    if header is None:
        return None
    return header.split(' ')[1]


def decode_token(token):
    return jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])


def get_and_validate_token():
    try:
        token = get_token()
        if token is None:
            return None
        obj = decode_token(token)
        if obj['issuer'] != current_app.config['APP_NAME']:
            return None
        return obj
    except Exception as e:
        print(f"Error: {e}")
        return None


@click.command('jwt:create')
def create_token_command():
    click.echo(create_token())
