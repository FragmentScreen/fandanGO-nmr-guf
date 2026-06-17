import os
import traceback
from contextlib import contextmanager
from nmrguf.db.sqlite import connect_to_ddbb, close_connection_to_ddbb


@contextmanager
def db_session(error_message="could not check projects"):
    connection = None
    try:
        connection = connect_to_ddbb()
        yield connection.cursor(), connection
    except Exception as e:
        print(f'... {error_message} because of: {e}')
        if os.getenv('DEV') == 'LOCAL':
            print(traceback.format_exc())
    finally:
        if connection:
            close_connection_to_ddbb(connection)


def update_project(project_name, key, value):
    with db_session("project could not be updated") as (cursor, connection):
        cursor.execute('INSERT INTO project_info VALUES (?, ?, ?)', (project_name, key, value))
        connection.commit()
        print(f'... project {project_name} updated: "{key}" = "{value}"')


def get_project_info(project_name):
    with db_session() as (cursor, _):
        cursor.execute('SELECT * FROM project_info WHERE project_name = ?', (project_name,))
        project_info = cursor.fetchall()
        column_names = [columns[0] for columns in cursor.description]
        return column_names, project_info


def get_project_metadata(project_name):
    with db_session() as (cursor, _):
        cursor.execute(
            'SELECT value FROM project_info WHERE project_name = ? AND '
            '(key = "filtered_library_metadata_path" OR key = "experiment_metadata_path")',
            (project_name,)
        )
        project_metadata = cursor.fetchall()
        return [metadata_file[0] for metadata_file in project_metadata]


def get_project_value(project_name, key, default=None):
    with db_session() as (cursor, _):
        cursor.execute('SELECT value FROM project_info WHERE project_name = ? AND key = ?', (project_name, key))
        db_result = cursor.fetchone()
        return db_result[0] if db_result and len(db_result) > 0 else default