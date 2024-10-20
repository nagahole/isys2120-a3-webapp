#!/usr/bin/env python3

import configparser
import sys
import traceback
from typing import Optional, Callable

import pg8000

from src.filters import Filters
from src.lowercase_default_dict import LowercaseDefaultDict


# CONSTANTS

TICKETS_PER_PAGE = 50

# TYPEHINTS

SqlEntry = dict[str, any]
SqlResult = list[SqlEntry]
SqlFetcher = Callable[[pg8000.Cursor], any]

# GLOBAL VARIABLES

table_attributes: dict[str, list[str]] = LowercaseDefaultDict(list)


def validate_sort_params(table: str, sort_by: str,
                         sort_dir: str) -> Optional[tuple[str, str]]:

    if not isinstance(sort_by, str) or \
            not valid_table_attribute(table, sort_by):
        return None

    if not isinstance(sort_dir, str) or \
            sort_dir.lower() not in ("asc", "desc"):
        sort_dir = "asc"

    return sort_by.lower(), sort_dir.lower()


def complete_order_by(table: str, sort_by: str, sort_dir: str) -> str:
    """
    Use all primary keys for order by for consistent results
    """

    print(sort_by, sort_dir)

    attrs = get_table_attributes(table).copy()

    if len(attrs) == 0:  # invalid table?
        return ""

    sort_params = validate_sort_params(table, sort_by, sort_dir)

    if sort_params is not None:
        sort_by, sort_dir = sort_params
    else:
        sort_by = attrs[0]
        sort_dir = "asc"

    if sort_by in attrs:
        attrs.remove(sort_by)

    criterion = [f"{sort_by} {sort_dir.upper()}"] + \
                [f"{k} ASC" for k in attrs]

    return "ORDER BY " + ", ".join(criterion)


###############################################################################
# TICKET OPERATIONS                                                           #
###############################################################################


def tickets_count() -> Optional[int]:
    sql = """
        SELECT Count(TicketID) AS count
            FROM Tickets
    """

    response = execute_and_fetch(dict_fetchone, sql)

    if response is None:
        return None

    return response[0]["count"]


def get_tickets_classes() -> Optional[list[str]]:
    sql = """
        SELECT DISTINCT Class
            FROM Tickets
    """

    return execute_and_fetch(lambda c: [r[0] for r in c.fetchall()], sql)


def list_tickets(page: int, sort_by: str,
                 sort_dir: str) -> Optional[SqlResult]:
    """
    Lists all tickets

    Gets all the rows of Tickets table and returns them as a dict
    """

    sql = f"""
        SELECT *
            FROM Tickets
            {complete_order_by('Tickets', sort_by, sort_dir)}
            LIMIT {TICKETS_PER_PAGE}
            OFFSET {(page - 1) * TICKETS_PER_PAGE}
    """

    return execute_and_fetch(dict_fetchall, sql)


def list_ticket_stats() -> Optional[SqlResult]:

    sql = """
        SELECT class, COUNT(TicketID) as count
            FROM Tickets 
            GROUP BY Class
            ORDER BY Class ASC;
    """

    return execute_and_fetch(dict_fetchall, sql)


def update_single_ticket(
    ticket_id: int,
    flight_id: int,
    passenger_id: int,
    ticket_number: str,
    booking_date: str,
    seat_number: str,
    ticket_class: str,
    price: float
) -> Optional[SqlResult]:
    """
    Updates a single value by primary key
    """

    # Data validation checks are assumed to have been done in route processing

    sets = []
    params = []

    if flight_id is not None:
        sets.append("flightid = %s::bigint\n")
        params.append(flight_id)

    if passenger_id is not None:
        sets.append("passengerid = %s::bigint")
        params.append(passenger_id)

    if ticket_number is not None:
        sets.append("ticketnumber = %s")
        params.append(ticket_number)

    if booking_date is not None:
        sets.append("bookingdate = %s::timestamp")
        params.append(booking_date)

    if seat_number is not None:
        sets.append("seatnumber = %s")
        params.append(seat_number)

    if ticket_class is not None:
        sets.append("class = %s")
        params.append(ticket_class)

    if price is not None:
        sets.append("price = %s::decimal(10,2)")
        params.append(price)

    set_query = ", ".join(sets)

    # f-string is ok here as it's hardcoded (not based on user input) and safe
    sql = f"""
        UPDATE tickets
            SET {set_query}
            WHERE TicketID = %s;
    """

    params.append(ticket_id)

    return execute_and_fetch(dict_fetchone, sql, tuple(params), commit=True)


def delete_ticket(ticketid: int) -> Optional[SqlEntry]:
    """
    Remove a ticket from your system
    """

    # Data validation checks are assumed to have been done in route processing

    sql = """
        DELETE
            FROM Tickets
            WHERE TicketID = %s;
    """

    return execute_and_fetch(
        dict_fetchone,
        sql,
        (ticketid,),
        err_msg=f"Error deleting ticket with id {ticketid}",
        commit=True
    )


def add_ticket_insert(
    ticket_id: int,
    flight_id: int,
    passenger_id: int,
    ticket_number: str,
    booking_date: str,
    seat_number: str,
    ticket_class: str,
    price: float
) -> Optional[SqlEntry]:
    """
    Add (inserts) a new Ticket to the system
    """

    # Data validation checks are assumed to have been done in route processing

    sql = """
        INSERT INTO Tickets(TicketID, FlightID, PassengerID, TicketNumber, 
                            BookingDate, SeatNumber, Class, Price)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s);
    """

    return execute_and_fetch(
        dict_fetchone,
        sql,
        (ticket_id, flight_id, passenger_id, ticket_number,
         booking_date, seat_number, ticket_class, price),
        err_msg="Unexpected error adding a ticket",
        commit=True
    )


###############################################################################
# USER OPERATIONS                                                             #
###############################################################################

def list_users() -> Optional[SqlResult]:
    """
    Lists all users

    Gets all the rows of Users table and returns them as a dict
    """

    sql = """
        SELECT Users.*, UserRoles.IsAdmin
            FROM Users JOIN UserRoles USING (UserRoleID)
    """

    return execute_and_fetch(dict_fetchall, sql)


def list_userroles() -> Optional[SqlResult]:

    sql = """
        SELECT *
            FROM userroles
    """

    return execute_and_fetch(dict_fetchall, sql)


def list_consolidated_users() -> Optional[SqlResult]:
    """
    A report with the details of Users, Userroles
    """

    sql = """
        SELECT *
            FROM Users 
            JOIN userroles ON (users.userroleid = userroles.userroleid);
    """

    return execute_and_fetch(dict_fetchall, sql)


def list_user_stats() -> Optional[SqlResult]:

    sql = """
        SELECT userroleid, COUNT(*) as count
            FROM Users 
            GROUP BY userroleid
            ORDER BY userroleid ASC;
    """

    return execute_and_fetch(dict_fetchall, sql)


def valid_table_attribute(table: str, attribute: str) -> bool:
    return attribute.lower() in get_table_attributes(table)


def get_table_attributes(table: str) -> list[str]:

    if len(table_attributes[table]) == 0:
        fetch_table_attributes(table)

    return table_attributes[table]


def fetch_table_attributes(table: str) -> bool:

    sql = f"""
        SELECT *
            FROM {table}
            WHERE 1 = 0
    """

    description = execute_and_fetch(lambda c: c.description, sql)

    if description is None:
        return False

    table_attributes[table] = list(map(lambda c: c[0].lower(), description))

    return True


def update_single_user(user_id: str, first_name: str,
                       last_name: str, user_role_id: str,
                       password: str) -> Optional[SqlResult]:
    """
    Updates a single value by primary key
    """

    # Data validation checks are assumed to have been done in route processing

    sets = []
    params = []

    if first_name is not None:
        sets.append("firstname = %s")
        params.append(first_name)

    if last_name is not None:
        sets.append("lastname = %s")
        params.append(last_name)

    if user_role_id is not None:
        sets.append("userroleid = %s::bigint")
        params.append(user_role_id)

    if password is not None:
        sets.append("password = %s")
        params.append(password)

    set_query = ", ".join(sets)

    # f-string is ok here as it's hardcoded (not based on user input) and safe
    sql = f"""
        UPDATE users
            SET {set_query}
            WHERE UserID = %s;
    """

    params.append(user_id)

    return execute_and_fetch(dict_fetchone, sql, tuple(params), commit=True)


def add_user_insert(user_id: str, first_name: str, last_name: str,
                    user_role_id: int, password: str) -> Optional[SqlEntry]:
    """
    Add (inserts) a new User to the system
    """

    # Data validation checks are assumed to have been done in route processing

    sql = """
        INSERT into Users(UserID, FirstName, LastName, UserRoleID, Password)
            VALUES (%s,%s,%s,%s,%s);
    """

    return execute_and_fetch(
        dict_fetchone,
        sql,
        (user_id, first_name, last_name, user_role_id, password),
        err_msg="Unexpected error adding a user",
        commit=True
    )


def delete_user(userid: str) -> Optional[SqlEntry]:
    """
    Remove a user from your system
    """

    # Data validation checks are assumed to have been done in route processing

    sql = """
        DELETE
            FROM Users
            WHERE UserID = %s;
    """

    return execute_and_fetch(
        dict_fetchone,
        sql,
        (userid,),
        err_msg=f"Error deleting user with id {userid}",
        commit=True
    )


###############################################################################
# USER AUTH                                                                   #
###############################################################################

def check_login(username: str, password: str) -> Optional[SqlResult]:
    """
    Check Login given a username and password
    """

    print("checking login")

    sql = """
        SELECT *     
            FROM Users
            JOIN UserRoles ON (Users.userroleid = UserRoles.userroleid)
            WHERE UserID = %s AND Password = %s
    """

    return execute_and_fetch(
        dict_fetchone,
        sql,
        (username, password),
        "Error Invalid Login"
    )


###############################################################################
# DATABASE HELPER FUNCTIONS                                                   #
###############################################################################

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


def search_table_by_filter(table: str,
                           attribute: str,
                           filter_type: Filters,
                           filter_val: any,
                           limit: int = None,
                           offset: int = None,
                           sort_by: str = None,
                           sort_dir: str = None,
                           no_lower: bool = False) -> Optional[SqlResult]:

    return select_from_table_by_filter(
        "*",
        table,
        attribute,
        filter_type,
        filter_val,
        limit,
        offset,
        sort_by,
        sort_dir,
        complete_sort=True,
        no_lower=no_lower
    )


def select_from_table_by_filter(
    select_operation: str,
    table: str,
    attribute: str,
    filter_type: Filters,
    filter_val: any,
    limit: int = None,
    offset: int = None,
    sort_by: str = None,
    sort_dir: str = None,
    complete_sort: bool = True,
    no_lower: bool = False
) -> Optional[SqlResult]:
    """
    Search for a table with a custom filter

    Useful for inexact matches

    filter_type can be: '=', '<', '>', '<>', '~', 'LIKE'
    """

    if not valid_table_attribute(table, attribute):
        return None

    if isinstance(filter_val, str):

        if no_lower:
            attr_val = attribute
        else:
            attr_val = f"lower({attribute})"

            filter_val = filter_val.lower()

            if filter_type == Filters.LIKE:
                filter_val = f"%{filter_val}%"

    else:
        attr_val = attribute

    sort_params = validate_sort_params(table, sort_by, sort_dir)

    if sort_params is None:
        sort_query = ""
    elif complete_sort:
        sort_query = complete_order_by(table, sort_by, sort_dir)
    else:
        sort_query = f"ORDER BY {sort_by} {sort_dir}"

    sql = f"""
        SELECT {select_operation}
            FROM {table}
            WHERE {attr_val} {filter_type.value} %s
            {sort_query}
    """

    if limit is not None:
        sql += f" LIMIT {limit}"

    if offset is not None:
        sql += f" OFFSET {offset}"

    print(sql)

    return execute_and_fetch(dict_fetchall, sql, (filter_val,))


def trace_fetch_err() -> None:
    traceback.print_exc()
    print(f"Error Fetching from Database - {sys.exc_info()[0]}")


def dict_fetchall(cursor: pg8000.Cursor) -> Optional[SqlResult]:
    """
    Returns query results as list of dictionaries

    Useful for read queries that return 1 or more rows
    """

    if cursor.description is None:
        return None

    result = []

    cols = [a[0].lower() for a in cursor.description]

    rows = cursor.fetchall()

    if rows is not None:
        for row in rows:
            result.append(dict(zip(cols, row)))

    print(f"returning results {len(result)}:")
    return result


def dict_fetchone(cursor: pg8000.Cursor) -> SqlResult:
    """
    Returns query results as list of dictionaries.

    Useful for create, update and delete queries that
    only need to return one row
    """

    result = []

    if cursor.description is not None:

        print("cursor description", cursor.description)

        cols = [a[0].lower() for a in cursor.description]
        sql_result = cursor.fetchone()

        print("sql_result: ", sql_result)

        if sql_result is not None:
            result.append(dict(zip(cols, sql_result)))

    return result


def execute_and_fetch(fetcher: SqlFetcher, sql: str, params=(),
                      err_msg: Optional[str] = None,
                      commit: bool = False) -> any:

    conn = database_connect()

    if conn is None:
        return None

    cursor = conn.cursor()

    print_sql_string(sql, params)

    sql_res = None

    try:
        cursor.execute(sql, params)
        sql_res = fetcher(cursor)
        print(sql_res[:5])

        if commit:
            conn.commit()

    except Exception as _:
        traceback.print_exc()
        if err_msg is not None:
            print(err_msg)

    cursor.close()
    conn.close()
    return sql_res


def print_sql_string(sql: str, params=None) -> None:
    """
    Prints out a string as a SQL string parameterized

    Assumes params are all strings

    Useful for checking how it would insert
    """

    print(sql.replace("%s", "'{}'").format(*params))
