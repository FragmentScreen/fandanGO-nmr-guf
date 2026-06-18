import os
from sqlite3 import dbapi2 as sqlite
from nmrguf.constants import DBNAME
import configparser

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'plugin.cfg'))
ddbb_path = config.get(section='DDBB', option='DDBB_PATH')


def connect_to_ddbb():
    db_file = os.path.join(ddbb_path, DBNAME)
    os.makedirs(os.path.dirname(db_file), exist_ok=True)
    connection = sqlite.connect(database=db_file)
    create_ddbb_data(connection)
    return connection


def create_ddbb_data(connection):
    cursor = connection.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS project_info (
                        project_name TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL);''')
    connection.commit()


def close_connection_to_ddbb(connection):
    connection.close()
