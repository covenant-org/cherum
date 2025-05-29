import sqlite3
from datetime import datetime

import click
from flask import current_app, g


def init_db():
    db = get()

    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))


@click.command('db:create')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')


def get():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


sqlite3.register_converter(
    "timestamp", lambda v: datetime.fromisoformat(v.decode())
)
