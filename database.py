#!/usr/bin/env python3

import configparser
import sys
import traceback
from typing import Optional

import pg8000


SqlEntry = dict[str, any]
SqlResult = list[SqlEntry]

USERS_ATTRIBUTES = set()

"""
Common Functions

 - database_connect()
 - dictfetchall(cursor,sql,params)
 - dictfetchone(cursor,sql,params)
 - print_sql_string(inputstring, params)

"""


def database_connect() -> Optional[pg8000.Connection]:
    """
    Reads config file and attempts to connect to database

    Primary db connection method for the program
    """

    # reads the config file
    config = configparser.ConfigParser()
    config.read('config.ini')

    # creates a connection to the database
    connection = None

    # choose a connection target, you can use the default or use a
    # different set of credentials that are set up for localhost or winhost
    connection_target = 'DATABASE'

    if "database" in config[connection_target]:
        targetdb = config[connection_target]["database"]
    else:
        targetdb = config[connection_target]["user"]

    try:
        connection = pg8000.connect(
            database=targetdb,
            host=config[connection_target]["host"],
            user=config[connection_target]["user"],
            password=config[connection_target]["password"],
            port=int(config[connection_target]["port"])
        )
        connection.run("SET SCHEMA 'airline';")
    except pg8000.OperationalError as e:
        print("""Error, you haven't updated your config.ini or you have a bad
        connection, please try again. (Update your files first, then check
        internet connection)
        """)
        print(e)
    except pg8000.ProgrammingError as e:
        print("Error, config file incorrect: check your password and username")
        print(e)
    except Exception as e:
        print(e)

    # Return the connection to use
    return connection


###############################################################################
# DATABASE HELPER FUNCTIONS                                                   #
###############################################################################


def trace_fetch_err() -> None:
    traceback.print_exc()
    print(f"Error Fetching from Database - {sys.exc_info()[0]}")


def dict_fetchall(cursor: pg8000.Cursor, sql: str,
                  params=()) -> Optional[SqlResult]:
    """
    Returns query results as list of dictionaries

    Useful for read queries that return 1 or more rows
    """

    cursor.execute(sql, params)

    if cursor.description is None:
        return None

    result = []

    cols = [a[0] for a in cursor.description]

    rows = cursor.fetchall()

    if rows is not None:
        for row in rows:
            result.append(dict(zip(cols, row)))

    print("returning result: ", result)
    return result


def dict_fetchone(cursor: pg8000.Cursor,
                  sql: str, params=()) -> SqlResult:
    """
    Returns query results as list of dictionaries.

    Useful for create, update and delete queries that
    only need to return one row
    """

    result = []
    cursor.execute(sql, params)

    if cursor.description is not None:

        print("cursor description", cursor.description)

        cols = [a[0] for a in cursor.description]
        sql_result = cursor.fetchone()

        print("sql_result: ", sql_result)

        if sql_result is not None:
            result.append(dict(zip(cols, sql_result)))

    return result


def print_sql_string(sql: str, params=None) -> None:
    """
    Prints out a string as a SQL string parameterized

    Assumes params are all strings

    Useful for checking how it would insert
    """

    print(sql.replace("%s", "'%s'") % params)


def check_login(username: str, password: str) -> Optional[SqlResult]:
    """
    Check Login given a username and password
    """

    print("checking login")

    conn = database_connect()

    if conn is None:
        return None

    cursor = conn.cursor()

    sql = """
        SELECT *     
            FROM Users
            JOIN UserRoles ON (Users.userroleid = UserRoles.userroleid)
            WHERE userid = %s AND password = %s
    """

    print_sql_string(sql, (username, password))

    sql_res = None

    try:
        sql_res = dict_fetchone(cursor, sql, (username, password))
    except Exception as _:
        traceback.print_exc()
        print(f"Error Invalid Login")

    cursor.close()
    conn.close()
    return sql_res


def list_users() -> Optional[SqlResult]:
    """
    Lists all users

    Gets all the rows of Users table and returns them as a dict
    """

    conn = database_connect()

    if conn is None:
        return None

    cursor = conn.cursor()

    sql = """
        SELECT *
            FROM Users
    """

    users_dict = None

    try:
        users_dict = dict_fetchall(cursor, sql)
        print(users_dict)
    except Exception as _:
        trace_fetch_err()

    cursor.close()
    conn.close()

    return users_dict


def list_userroles() -> Optional[SqlResult]:

    conn = database_connect()

    if conn is None:
        return None

    cursor = conn.cursor()
    user_roles_dict = None

    sql = """
        SELECT *
            FROM userroles
    """

    try:
        user_roles_dict = dict_fetchall(cursor, sql)
        print(user_roles_dict)
    except Exception as _:
        trace_fetch_err()

    cursor.close()
    conn.close()

    return user_roles_dict


def list_users_equifilter(attribute: str,
                          filter_val: str) -> Optional[SqlResult]:
    """
    Get all rows in users where a particular attribute matches a value
    """
    return search_users_customfilter(attribute, "=", filter_val)


def list_consolidated_users() -> Optional[SqlResult]:
    """
    A report with the details of Users, Userroles
    """

    conn = database_connect()

    if conn is None:
        return None

    cursor = conn.cursor()

    sql = """
        SELECT *
            FROM Users 
            JOIN userroles ON (users.userroleid = userroles.userroleid);
    """

    sql_res = None

    try:
        sql_res = dict_fetchall(cursor, sql)
        print(sql_res)
    except Exception as _:
        trace_fetch_err()

    cursor.close()
    conn.close()

    return sql_res


def list_user_stats() -> Optional[SqlResult]:

    conn = database_connect()

    if conn is None:
        return None

    cursor = conn.cursor()

    sql = """
        SELECT userroleid, COUNT(*) as count
            FROM Users 
            GROUP BY userroleid
            ORDER BY userroleid ASC;
    """

    sql_res = None

    try:
        sql_res = dict_fetchall(cursor, sql)
        print(sql_res)
    except Exception as _:
        trace_fetch_err()

    cursor.close()
    conn.close()

    return sql_res


VALID_FILTERS: set[str] = {"=", "<", ">", "<>", "~", "LIKE"}


def valid_users_attribute(attribute: str) -> bool:

    if len(USERS_ATTRIBUTES) == 0 and not fetch_user_attributes():
        return False

    return attribute in USERS_ATTRIBUTES


def fetch_user_attributes() -> bool:

    conn = database_connect()

    if conn is None:
        return False

    cursor = conn.cursor()

    sql = """
        SELECT *
            FROM Users
            WHERE 1 = 0
    """

    try:
        cursor.execute(sql)
        description = cursor.description
    except Exception as _:
        trace_fetch_err()
        return False

    print("columns:", )

    conn.close()
    cursor.close()

    if description is None:
        return False

    USERS_ATTRIBUTES.clear()

    for col in description:
        USERS_ATTRIBUTES.add(col[0])

    return True


def search_users_customfilter(attribute: str, filter_type: str,
                              filter_val: str) -> Optional[SqlResult]:
    """
    Search for users with a custom filter

    Useful for inexact matches

    filter_type can be: '=', '<', '>', '<>', '~', 'LIKE'
    """

    if filter_type not in VALID_FILTERS:
        return None

    if not valid_users_attribute(attribute):
        return None

    conn = database_connect()

    if conn is None:
        return None

    cursor = conn.cursor()
    sql_res = None

    prefix = ""
    suffix = ""

    if filter_type.lower() == "like":
        prefix = "'%"
        suffix = "%'"

    sql = f"""
        SELECT *
            FROM Users
            WHERE lower({attribute}) {filter_type} {prefix}lower(%s){suffix}
    """

    try:
        print_sql_string(sql, (filter_val,))
        sql_res = dict_fetchall(cursor, sql, (filter_val,)) or []
    except Exception as _:
        trace_fetch_err()

    cursor.close()
    conn.close()

    return sql_res


def update_single_user(user_id: str, first_name: str,
                       last_name: str, user_role_id: str,
                       password: str) -> Optional[SqlResult]:
    """
    Updates a single value by primary key
    """

    conn = database_connect()

    if conn is None:
        return None

    cursor = conn.cursor()
    sql_res = None

    # Data validation checks are assumed to have been done in route processing

    set_query = ""
    params = []

    if first_name is not None:
        set_query += "firstname = %s\n"
        params.append(first_name)

    if last_name is not None:
        if len(params) > 0:
            set_query += ","

        set_query += "lastname = %s\n"
        params.append(last_name)

    if user_role_id is not None:
        if len(params) > 0:
            set_query += ","

        set_query += "userroleid = %s::bigint\n"
        params.append(user_role_id)

    if password is not None:
        if len(params) > 0:
            set_query += ","

        set_query += "password = %s\n"
        params.append(password)

    # f-string is ok here as it's hardcoded (not based on user input) and safe
    sql = f"""
        UPDATE users
            SET {set_query}
            WHERE userid = %s;
    """

    params.append(user_id)

    try:
        params = tuple(params)

        print_sql_string(sql, params)
        sql_res = dict_fetchone(cursor, sql, params)

        conn.commit()
    except Exception as _:
        trace_fetch_err()

    cursor.close()
    conn.close()

    return sql_res


def add_user_insert(user_id: str, first_name: str, last_name: str,
                    user_role_id: int, password: str) -> Optional[SqlEntry]:
    """
    Add (inserts) a new User to the system
    """

    # Data validation checks are assumed to have been done in route processing

    conn = database_connect()

    if conn is None:
        return None

    cursor = conn.cursor()

    sql = """
        INSERT into Users(userid, firstname, lastname, userroleid, password)
            VALUES (%s,%s,%s,%s,%s);
    """

    params = (user_id, first_name, last_name, user_role_id, password)
    print_sql_string(sql, params)

    sql_res = None

    try:
        cursor.execute(sql, params)
        conn.commit()

        sql_res = cursor.fetchone()

        print("return val is:")
        print(sql_res)
    except Exception as _:
        print(f"Unexpected error adding a user - {sys.exc_info()[0]}")

    cursor.close()
    conn.close()

    return sql_res


def delete_user(userid: str) -> Optional[SqlEntry]:
    """
    Remove a user from your system
    """
    # Data validation checks are assumed to have been done in route processing
    conn = database_connect()

    if conn is None:
        return None

    cursor = conn.cursor()

    sql = """
        DELETE
            FROM Users
            WHERE userid = %s;
    """

    sql_res = None

    try:
        cursor.execute(sql, (userid,))
        conn.commit()

        sql_res = cursor.fetchone()

        print("return val is:")
        print(sql_res)
    except Exception as _:
        print(
            f"Unexpected error deleting user with id {userid} - " +
            str(sys.exc_info()[0])
        )

    cursor.close()
    conn.close()

    return sql_res
