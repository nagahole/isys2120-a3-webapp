import configparser
from datetime import datetime
from typing import Optional
from urllib.parse import quote, unquote
from functools import wraps

from flask import *

import database
from src.session import Session
from src.filters import Filters
from src.pagination import Pagination


TICKET_FORM_ATTRIBUTES: tuple[tuple[str, callable], ...] = (
    ("ticketid", int),
    ("flightid", int),
    ("passengerid", int),
    ("ticketnumber", str),
    ("bookingdate", str),
    ("seatnumber", str),
    ("class", str),
    ("price", float)
)

USER_FORM_ATTRIBUTES: tuple[tuple[str, callable], ...] = (
    ("userid", str),
    ("firstname", str),
    ("lastname", str),
    ("userroleid", int),
    ("password", str)
)

DATABASE_ERR_TEXT = "Error connecting to database"


# web-app setup
page = {}
session = Session()

# flask init
app = Flask(__name__)
app.secret_key = "SoMeSeCrEtKeYhErE"

app.debug = True  # whether to debug output on error


# init app based on config content (stored in config.ini)
config = configparser.ConfigParser()
config.read("config.ini")

db_user = config["DATABASE"]["user"]
portchoice = config["FLASK"]["port"]

if portchoice == "10000":
    print("ERROR: Please change config.ini as in instructions")
    exit(0)


def require_login(func):

    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not session.logged_in:
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return decorated_function


###############################################################################
# ROUTES                                                                      #
###############################################################################

# == TICKETS ==================================================================


def extract_ticket_sort():
    sort_by = request.args.get("sort", "ticketid", type=str).lower()
    sort_dir = request.args.get("direction", "asc", type=str).lower()
    toggled = request.args.get("togglesort")

    if toggled is None or \
            toggled.lower() not in map(lambda x: x[0], TICKET_FORM_ATTRIBUTES):
        return sort_by, sort_dir

    toggled = toggled.lower()

    if toggled == sort_by:
        sort_dir = "desc" if sort_dir == "asc" else "asc"
    else:
        sort_by = toggled
        sort_dir = "asc"

    return sort_by, sort_dir


@app.route("/tickets")
@require_login
def list_tickets():
    page_no = request.args.get("page", 1, type=int)
    sort_by, sort_dir = extract_ticket_sort()

    total_tickets = database.tickets_count()

    if total_tickets is None:
        flash("Error accessing tickets information")
        return redirect(url_for("index"))

    tickets_listdict = database.list_tickets(page_no, sort_by, sort_dir)

    if tickets_listdict is None:  # error fetching tickets
        tickets_listdict = []
        flash("Error fetching tickets")

    pagination = Pagination(
        page_no,
        database.TICKETS_PER_PAGE,
        total_tickets
    )

    page["title"] = "Tickets"
    return render_template(
        "tickets/list_tickets.html",
        page=page,
        session=session,
        tickets=tickets_listdict,
        pagination=pagination,
        route="list_tickets",
        params={"sort": quote(sort_by), "direction": quote(sort_dir)}
    )


@app.route("/tickets/<ticketid>")
@require_login
def list_single_tickets(ticketid):
    """
    List all rows in tickets that match the specified ticketid
    """

    try:
        ticketid = int(ticketid)
    except ValueError:
        flash("TicketID must be an integer")
        return redirect(url_for("list_tickets"))

    tickets_listdict = database.search_table_by_filter(
        "Tickets", "ticketid", Filters.EQUALS, ticketid
    ) or []

    if len(tickets_listdict) == 0:
        flash(
            "Error, there are no rows in tickets that match the attribute "
            f"'ticketid' for the value {ticketid}"
        )

    pagination = Pagination(
        1,
        1,
        1,
        0
    )

    page["title"] = "Ticket"
    return render_template(
        "tickets/list_tickets.html",
        page=page,
        session=session,
        tickets=tickets_listdict,
        pagination=pagination,
        route="list_single_tickets",
        params={}
    )


@app.route("/ticket_stats")
@require_login
def list_ticket_stats():
    """
    List some ticket stats
    """

    ticket_stats = database.list_ticket_stats()

    if ticket_stats is None:
        ticket_stats = []
        flash("Error, there are no rows in ticket_stats")

    page["title"] = "Ticket Stats"
    return render_template(
        "tickets/list_ticket_stats.html",
        page=page, session=session, tickets=ticket_stats
    )


@app.route("/tickets/search", methods=["POST", "GET"])
@require_login
def search_tickets():
    """
    List all rows in tickets that match a particular name
    """
    if request.method == "GET":

        classes = database.get_tickets_classes()

        if classes is None:
            flash("Something went wrong with the database")
            return redirect(url_for("index"))

        return render_template(
            "tickets/search_tickets.html",
            page=page,
            session=session,
            classes=classes
        )

    # else POST

    attribute = request.form["searchfield"].lower()
    search = request.form[
        "searchterm_class" if attribute == "class" else "searchterm_text"
    ].lower()

    return redirect(
        url_for(
            "search_tickets_result",
            page=1,
            attribute=quote(attribute),
            search=quote(search)
        )
    )


@app.route("/tickets/searched", methods=["GET"])
@require_login
def search_tickets_result():

    # validate attribute
    attribute = unquote(request.args.get("attribute", "", type=str))

    try:
        parser = next(
            filter(lambda tup: attribute == tup[0], TICKET_FORM_ATTRIBUTES)
        )[1]
    except StopIteration:  # attribute not in TICKET_FORM_ATTRIBUTES
        flash(f"Search field '{attribute}' doesn't exist")
        return redirect(url_for("search_tickets"))

    # validate search
    search = unquote(request.args.get("search", "", type=str))

    try:
        parsed_search = parser(search)
    except ValueError:
        flash(f"Search field in wrong form")
        return redirect(url_for("search_tickets"))

    if isinstance(parsed_search, str) and attribute != "bookingdate":
        search_filter = Filters.LIKE
    else:
        search_filter = Filters.EQUALS

    no_lower = attribute == "bookingdate"

    count_listdict = database.select_from_table_by_filter(
        "Count(TicketID) AS count",
        "Tickets",
        attribute,
        search_filter,
        parsed_search,
        no_lower=no_lower
    )

    if count_listdict is None:
        flash(DATABASE_ERR_TEXT)
        return redirect(url_for("index"))

    matching_tickets = count_listdict[0]["count"]

    if matching_tickets == 0:
        flash(
            f"No items found for search "
            f"{attribute}: {parsed_search}"
        )

        return redirect(url_for("index"))

    page_no = request.args.get("page", 1, type=int)

    pagination = Pagination(
        page_no,
        database.TICKETS_PER_PAGE,
        matching_tickets
    )

    sort_by, sort_dir = extract_ticket_sort()

    if page_no != pagination.page:
        return redirect(
            url_for(
                "search_tickets_result",
                page=pagination.page,
                attribute=attribute,
                search=search,
                sort=sort_by,
                direction=sort_dir
            )
        )

    page_no = pagination.page

    print(
        f"search {attribute}: {search}, "
        f"pg {page_no}, "
        f"sorted by {sort_by} {sort_dir}"
    )

    tickets_listdict = database.search_table_by_filter(
        "Tickets",
        attribute,
        search_filter,
        parsed_search,
        limit=database.TICKETS_PER_PAGE,
        offset=(page_no - 1) * database.TICKETS_PER_PAGE,
        sort_by=sort_by,
        sort_dir=sort_dir
    )

    if tickets_listdict is None:
        flash(DATABASE_ERR_TEXT)
        return redirect(url_for("index"))

    page["title"] = f"Tickets Search by {attribute}"

    return render_template(
        "tickets/list_tickets.html",
        page=page,
        session=session,
        tickets=tickets_listdict,
        pagination=pagination,
        route="search_tickets_result",
        params={
            "attribute": quote(attribute),
            "search": quote(search),
            "sort": quote(sort_by),
            "direction": quote(sort_dir)
        }
    )


@app.route("/tickets/delete/<ticketid>")
@require_login
def delete_ticket(ticketid):
    """
    Delete a ticket
    """

    if not session.isadmin:
        flash("Only admins can delete tickets!")
        return redirect(url_for("index"))

    route = request.args.get("route", "list_tickets", type=str)
    page_no = request.args.get("page", 1, type=int)
    sort_by, sort_dir = extract_ticket_sort()
    attribute = request.args.get("attribute", "ticketid", type=str)
    search = request.args.get("search", "1", type=str)

    redirection = redirect(
        url_for(
            route,
            page=page_no,
            sort=sort_by,
            direction=sort_dir,
            attribute=attribute,
            search=search
        )
    )

    try:
        ticketid = int(ticketid)
    except ValueError:
        flash("TicketID must be an integer")
        return redirection

    response = database.delete_ticket(ticketid)

    if response is None:
        flash(f"Error deleting {ticketid}")

    return redirection


def extract_from_ticket_form(form, default_values: tuple) \
        -> Optional[tuple[dict, bool]]:

    try:
        ticketid = form["ticketid"]
    except ValueError:
        return None

    ticket_dict: dict[str, any] = {"ticketid": ticketid}
    some_value_present = False

    print("We have a value: ", ticket_dict["ticketid"])

    for (attr, parser), default in zip(
        TICKET_FORM_ATTRIBUTES,
        default_values
    ):

        if attr == "ticketid":
            continue

        try:
            ticket_dict[attr] = parser(form[attr])
            some_value_present = True
            print("We have a value: ", ticket_dict[attr])
        except (ValueError, KeyError):
            ticket_dict[attr] = default

    return ticket_dict, some_value_present


@app.route("/tickets/update", methods=["POST"])
@require_login
def update_ticket():
    """
    Update details for a ticket
    """

    if not session.isadmin:
        flash("Only admins can update ticket details!")
        return redirect(url_for("index"))

    print("request form is:")
    print(request.form)

    if "ticketid" not in request.form:
        flash("Can not update without a ticketid")
        return redirect(url_for("list_tickets"))

    ticket_dict, valid_update = extract_from_ticket_form(
        request.form, (None,) * 8
    )

    print("Update dict is:")
    print(ticket_dict, valid_update)

    if not valid_update:
        flash("No updated values for ticket with ticketid")
        return redirect(url_for("list_tickets"))

    response = database.update_single_ticket(ticket_dict["ticketid"],
                                             ticket_dict["flightid"],
                                             ticket_dict["passengerid"],
                                             ticket_dict["ticketnumber"],
                                             ticket_dict["bookingdate"],
                                             ticket_dict["seatnumber"],
                                             ticket_dict["class"],
                                             ticket_dict["price"])

    if response is None:
        flash("Error updating ticket")

    return list_single_tickets(ticket_dict["ticketid"])


@app.route("/tickets/edit/<ticketid>", methods=["GET"])
@require_login
def edit_ticket(ticketid):
    """
    Edit a ticket
    """

    if not session.isadmin:
        flash("Only admins can update ticket details!")
        return redirect(url_for("index"))

    try:
        ticketid = int(ticketid)
    except ValueError:
        flash("TicketID must be an integer")
        return redirect(url_for("list_tickets"))

    page["title"] = "Edit Ticket"

    tickets_list_dict = database.search_table_by_filter(
        "Tickets", "ticketid", Filters.EQUALS, ticketid
    ) or []

    if len(tickets_list_dict) == 0:
        flash(f"Error: No tickets matching id {ticketid}")
        return redirect(url_for("list_tickets"))

    ticket = tickets_list_dict[0]
    ticket["bookingdate"] = ticket.get("bookingdate", datetime.min)\
        .strftime("%Y-%m-%dT%H:%M")

    return render_template("tickets/edit_ticket.html",
                           session=session,
                           page=page,
                           ticket=ticket)


@app.route("/tickets/add", methods=["POST", "GET"])
@require_login
def add_ticket():
    """
    Add a new Ticket
    """

    if not session.isadmin:
        flash("Only admins can add tickets!")
        return redirect(url_for("index"))

    page["title"] = "Add Ticket"

    if request.method == "GET":
        return render_template("tickets/add_ticket.html",
                               session=session,
                               page=page)

    # else POST

    print("request form is:")
    print(request.form)

    if "ticketid" not in request.form:
        flash("Can not add ticket without a ticketid")
        return redirect(url_for("add_ticket"))

    extraction = extract_from_ticket_form(
        request.form,
        (
            None,
            0,
            0,
            "no_ticketno",
            "1970-01-01 00:00:00",  # unix time
            "nseat",
            "noclass",
            0
        )
    )

    if extraction is None:
        flash("Error adding ticket (invalid ticketid?)")
        return redirect(url_for("add_ticket"))

    ticket_dict, _ = extraction

    print("Insert parameters are:")
    print(ticket_dict)

    response = database.add_ticket_insert(ticket_dict["ticketid"],
                                          ticket_dict["flightid"],
                                          ticket_dict["passengerid"],
                                          ticket_dict["ticketnumber"],
                                          ticket_dict["bookingdate"],
                                          ticket_dict["seatnumber"],
                                          ticket_dict["class"],
                                          ticket_dict["price"])

    if response is None:
        flash("Error adding ticket")
        return redirect(url_for("add_ticket"))

    return list_single_tickets(ticket_dict["ticketid"])


# == USERS ====================================================================

@app.route("/users")
@require_login
def list_users():
    """
    List all rows in Users table
    """

    users_listdict = database.list_users()

    if users_listdict is None:  # error fetching users
        users_listdict = []
        flash("Error fetching users")

    page["title"] = "Users"
    return render_template(
        "users/list_users.html",
        page=page, session=session, users=users_listdict
    )


@app.route("/users/<userid>")
@require_login
def list_single_users(userid):
    """
    List all rows in users that match the specified userid
    """

    users_listdict = database.search_table_by_filter(
        "Users", "userid", Filters.EQUALS, userid
    ) or []

    if len(users_listdict) == 0:
        flash(
            "Error, there are no rows in users that match the attribute "
            f"'userid' for the value {userid}"
        )

    page["title"] = "User"
    return render_template(
        "users/list_users.html",
        page=page, session=session, users=users_listdict
    )


@app.route("/consolidated/users")
@require_login
def list_consolidated_users():
    """
    List all rows in users join userroles
    """

    users_userroles_listdict = database.list_consolidated_users()

    if users_userroles_listdict is None:
        users_userroles_listdict = []
        flash("Error, there are no rows in users_userroles_listdict")

    page["title"] = "Consolidated Users"

    return render_template(
        "users/list_consolidated_users.html",
        page=page, session=session, users=users_userroles_listdict
    )


@app.route("/user_stats")
@require_login
def list_user_stats():
    """
    List some user stats
    """

    user_stats = database.list_user_stats()

    if user_stats is None:
        user_stats = []
        flash("Error, there are no rows in user_stats")

    page["title"] = "User Stats"
    return render_template(
        "users/list_user_stats.html",
        page=page, session=session, users=user_stats
    )


@app.route("/users/search", methods=["POST", "GET"])
@require_login
def search_users():
    """
    List all rows in users that match a particular name
    """
    if request.method == "GET":
        return render_template(
            "users/search_users.html",
            page=page, session=session
        )

    # else POST

    users_listdict = database.search_table_by_filter(
        "Users",
        request.form["searchfield"],
        Filters.LIKE,
        request.form["searchterm"]
    )

    if users_listdict is None:
        flash(DATABASE_ERR_TEXT)
        return redirect(url_for("search_users"))

    if len(users_listdict) == 0:
        flash(
            f"No items found for search "
            f"{request.form['searchfield']}: {request.form['searchterm']}"
        )
        return redirect(url_for("search_users"))

    return render_template(
        "users/list_users.html",
        page=page, session=session, users=users_listdict
    )


@app.route("/users/delete/<userid>")
@require_login
def delete_user(userid):
    """
    Delete a user
    """

    if not session.isadmin:
        flash("Only admins can delete users!")
        return redirect(url_for("index"))

    response = database.delete_user(userid)

    if response is None:
        flash(f"Error deleting {userid}")

    return redirect(url_for("list_consolidated_users"))


def extract_from_user_form(form, default_values: tuple) -> tuple[dict, bool]:

    user_dict: dict[str, any] = {"userid": form["userid"]}
    some_value_present = False

    print("We have a value: ", user_dict["userid"])

    for (attr, parser), default in zip(
        USER_FORM_ATTRIBUTES,
        default_values
    ):
        if attr == "userid":
            continue

        try:
            user_dict[attr] = parser(form[attr])
            some_value_present = True
            print("We have a value: ", user_dict[attr])
        except (ValueError, KeyError):
            user_dict[attr] = default

    return user_dict, some_value_present


@app.route("/users/update", methods=["POST"])
@require_login
def update_user():
    """
    Update details for a user
    """

    if not session.isadmin:
        flash("Only admins can update user details!")
        return redirect(url_for("index"))

    print("request form is:")
    print(request.form)

    if "userid" not in request.form:
        flash("Can not update without a userid")
        return redirect(url_for("list_users"))

    user_dict, valid_update = extract_from_user_form(request.form, (None,) * 5)

    print("Update dict is:")
    print(user_dict, valid_update)

    if not valid_update:
        flash("No updated values for user with userid")
        return redirect(url_for("list_users"))

    response = database.update_single_user(user_dict["userid"],
                                           user_dict["firstname"],
                                           user_dict["lastname"],
                                           user_dict["userroleid"],
                                           user_dict["password"])

    if response is None:
        flash("Error updating user")

    return list_single_users(user_dict["userid"])


@app.route("/users/edit/<userid>", methods=["GET"])
@require_login
def edit_user(userid):
    """
    Edit a user
    """

    if not session.isadmin:
        flash("Only admins can update user details!")
        return redirect(url_for("index"))

    page["title"] = "Edit User Details"

    users_list_dict = database.search_table_by_filter(
        "Users", "userid", Filters.EQUALS, userid
    ) or []

    if len(users_list_dict) == 0:
        flash(f"Error: No users matching id '{userid}'")
        return redirect(url_for("list_consolidated_users"))

    user = users_list_dict[0]

    return render_template("users/edit_user.html",
                           session=session,
                           page=page,
                           userroles=database.list_userroles(),
                           user=user)


@app.route("/users/add", methods=["POST", "GET"])
@require_login
def add_user():
    """
    Add a new User
    """

    if not session.isadmin:
        flash("Only admins can add users!")
        return redirect(url_for("index"))

    page["title"] = "Add User Details"

    # Check your incoming parameters
    if request.method == "GET":
        return render_template("users/add_user.html",
                               session=session,
                               page=page,
                               userroles=database.list_userroles())

    # else POST

    print("request form is:")
    print(request.form)

    if "userid" not in request.form:
        flash("Can not add user without a userid")
        return redirect(url_for("add_user"))

    user_dict, _ = extract_from_user_form(
        request.form,
        (None, "Empty firstname", "Empty lastname", 1, "blank")
    )

    print("Insert parameters are:")
    print(user_dict)

    response = database.add_user_insert(user_dict["userid"],
                                        user_dict["firstname"],
                                        user_dict["lastname"],
                                        user_dict["userroleid"],
                                        user_dict["password"])

    if response is None:
        flash("Error adding user")
        return redirect(url_for("add_user"))

    return list_single_users(user_dict["userid"])

# == OTHER ====================================================================


@app.route("/jump_to", methods=["POST"])
@require_login
def jump_to():
    route = request.args.get("route", "index", type=str)
    params = request.args.to_dict()

    if "route" in params:
        del params["route"]

    if "page" in params:
        del params["page"]

    page_str = request.form.get("page", "1")

    try:
        page_no = int(page_str)
    except ValueError:
        page_no = 1

    return redirect(url_for(route, page=page_no, **params))


# == INDEX ====================================================================

@app.route("/")
@require_login
def index():
    """
    Index (home page)
    """

    page["username"] = db_user
    page["title"] = "Welcome"

    return render_template("welcome.html", session=session, page=page)


# == USER AUTH RELATED ========================================================

@app.route("/login", methods=["POST", "GET"])
def login():

    page["title"] = "Login"
    page["dbuser"] = db_user

    if request.method == "GET":
        if session.logged_in:
            return redirect(url_for("index"))
        return render_template("index.html", page=page)

    print(request.form)

    login_response = database.check_login(
        request.form["userid"],
        request.form["password"]
    )

    print(login_response)

    if login_response is None:  # database connection gave back error
        flash(DATABASE_ERR_TEXT)
        return redirect(url_for("login"))

    if len(login_response) == 0:
        flash("There was an error logging you in")
        return redirect(url_for("login"))

    print(login_response[0])
    session.name = login_response[0]["firstname"]
    session.userid = login_response[0]["userid"]
    session.logged_in = True
    session.isadmin = login_response[0]["isadmin"]
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.logged_in = False
    flash("You have been logged out")
    return redirect(url_for("index"))
