import configparser

from flask import *

import database
from session import Session


DATABASE_ERR_TEXT = \
    "Error connecting to database - Invalid credentials in config?"


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


###############################################################################
# ROUTES                                                                      #
###############################################################################

# == TICKETS ==================================================================

@app.route("/tickets")
def list_tickets():

    tickets_listdict = database.list_tickets()

    if tickets_listdict is None:  # error fetching tickets
        tickets_listdict = []
        flash("Error fetching tickets")

    page["title"] = "List Contents of Tickets"
    return render_template(
        "tickets/list_tickets.html",
        page=page, session=session, tickets=tickets_listdict
    )


@app.route("/tickets/<ticketid>")
def list_single_tickets(ticketid):
    """
    List all rows in tickets that match the specified ticketid
    """

    tickets_listdict = database.list_table_equifilter(
        "Tickets", "ticketid", ticketid
    ) or []

    if len(tickets_listdict) == 0:
        flash(
            "Error, there are no rows in tickets that match the attribute "
            f"'ticketid' for the value {ticketid}"
        )

    page["title"] = "List Single ticketid for tickets"
    return render_template(
        "tickets/list_tickets.html",
        page=page, session=session, tickets=tickets_listdict
    )


@app.route("/consolidated/tickets")
def list_consolidated_tickets():
    """
    List all rows in tickets join ticketroles
    """

    tickets_ticketroles_listdict = database.list_consolidated_tickets()

    if tickets_ticketroles_listdict is None:
        tickets_ticketroles_listdict = []
        flash("Error, there are no rows in tickets_ticketroles_listdict")

    page["title"] = "List Contents of Tickets join Ticketroles"

    return render_template(
        "tickets/list_consolidated_tickets.html",
        page=page, session=session, tickets=tickets_ticketroles_listdict
    )


@app.route("/ticket_stats")
def list_ticket_stats():
    """
    List some ticket stats
    """
    # connect to the database and call the relevant function
    ticket_stats = database.list_ticket_stats()

    # Handle the null condition
    if ticket_stats is None:
        # Create an empty list and show error message
        ticket_stats = []
        flash("Error, there are no rows in ticket_stats")
    page["title"] = "Ticket Stats"
    return render_template(
        "tickets/list_ticket_stats.html",
        page=page, session=session, tickets=ticket_stats
    )


@app.route("/tickets/search", methods=["POST", "GET"])
def search_tickets():
    """
    List all rows in tickets that match a particular name
    """
    if request.method == "GET":
        return render_template(
            "tickets/search_tickets.html",
            page=page, session=session
        )

    # else POST

    tickets_listdict = database.search_table_equifilter(
        "Tickets",
        request.form["searchfield"],
        "~",
        request.form["searchterm"]
    )

    print(tickets_listdict)

    if tickets_listdict is None:
        flash(DATABASE_ERR_TEXT)
        return redirect(url_for("index"))

    if len(tickets_listdict) == 0:
        flash(
            f"No items found for search: "
            f"{request.form['searchfield']}, {request.form['searchterm']}"
        )

        return redirect(url_for("index"))

    page["title"] = "Tickets search by name"

    return render_template(
        "tickets/list_tickets.html",
        page=page, session=session, tickets=tickets_listdict
    )


@app.route("/tickets/delete/<ticketid>")
def delete_ticket(ticketid):
    """
    Delete a ticket
    """

    response = database.delete_ticket(ticketid)

    if response is None:
        page["title"] = f"List tickets after user {ticketid} has been deleted"
    else:
        page["title"] = f"Error deleting {ticketid}. Is it a valid ticketID?"

    return redirect(url_for("list_consolidated_tickets"))

TICKET_FORM_ATTRIBUTES = (
    "ticketid",
    "flightid",
    "passengerid",
    "ticketnumber",
    "bookingdate",
    "seatnumber",
    "class",
    "price"
)

TICKET_FORM_ATTRIBUTE_TYPES = (
    int,
    int,
    int,
    str,
    str,
    str,
    float
)


def extract_from_ticket_form(form, default_values: tuple) -> tuple[dict, bool]:

    ticket_dict: dict[str, any] = {"ticketid": form["ticketid"]}
    some_value_present = False

    print("We have a value: ", ticket_dict["ticketid"])

    for attr, typ, default in zip(
        TICKET_FORM_ATTRIBUTES,
        TICKET_FORM_ATTRIBUTE_TYPES,
        default_values
    ):
        try:
            ticket_dict[attr] = typ(form[attr])
            some_value_present = True
            print("We have a value: ", ticket_dict[attr])
        except (ValueError, KeyError):
            ticket_dict[attr] = default

    return ticket_dict, some_value_present


@app.route("/tickets/update", methods=["POST"])
def update_ticket():
    """
    Update details for a ticket
    """

    if not session.logged_in:
        return redirect(url_for("login"))

    if not session.isadmin:
        flash("Only admins can update ticket details!")
        return redirect(url_for("index"))

    page["title"] = "Update ticket details"

    print("request form is:")
    print(request.form)

    if "ticketid" not in request.form:
        flash("Can not update without a ticketid")
        return redirect(url_for("list_tickets"))

    ticket_dict, valid_update = extract_from_user_form(
        request.form, (None,) * 4
    )

    print("Update dict is:")
    print(ticket_dict, valid_update)

    if not valid_update:
        flash("No updated values for ticket with ticketid")
        return redirect(url_for("list_tickets"))

    database.update_single_ticket(ticket_dict["ticketid"],
                                ticket_dict["firstname"],
                                ticket_dict["lastname"],
                                ticket_dict["ticketroleid"],
                                ticket_dict["password"])

    return list_single_tickets(ticket_dict["ticketid"])


@app.route("/tickets/edit/<ticketid>", methods=["GET"])
def edit_ticket(ticketid):
    """
    Edit a ticket
    """

    if not session.logged_in:
        return redirect(url_for("login"))

    if not session.isadmin:
        flash("Only admins can update ticket details!")
        return redirect(url_for("index"))

    page["title"] = "Edit ticket details"

    tickets_list_dict = database.list_tickets_equifilter("ticketid", ticketid) or []

    if len(tickets_list_dict) == 0:
        flash(f"Error: No tickets matching id '{ticketid}'")
        return redirect(url_for("list_consolidated_tickets"))

    ticket = tickets_list_dict[0]

    return render_template("tickets/edit_ticket.html",
                           session=session,
                           page=page,
                           ticketroles=database.list_ticketroles(),
                           ticket=ticket)


@app.route("/tickets/add", methods=["POST", "GET"])
def add_ticket():
    """
    Add a new Ticket
    """

    if not session.logged_in:
        return redirect(url_for("login"))

    if not session.isadmin:
        flash("Only admins can add tickets!")
        return redirect(url_for("index"))

    page["title"] = "Add ticket details"

    # Check your incoming parameters
    if request.method == "GET":
        return render_template("tickets/add_ticket.html",
                               session=session,
                               page=page,
                               ticketroles=database.list_ticketroles())

    # else POST

    print("request form is:")
    print(request.form)

    if "ticketid" not in request.form:
        flash("Can not add ticket without a ticketid")
        return redirect(url_for("add_ticket"))

    ticket_dict, _ = extract_from_user_form(
        request.form,
        ("Empty firstname", "Empty lastname", 1, "blank")
    )

    print("Insert parameters are:")
    print(ticket_dict)

    response = database.add_ticket_insert(ticket_dict["ticketid"],
                             ticket_dict["firstname"],
                             ticket_dict["lastname"],
                             ticket_dict["ticketroleid"],
                             ticket_dict["password"])

    if response is None:
        flash("Error adding ticket")
        return redirect(url_for("index"))

    return list_single_tickets(ticket_dict["ticketid"])


# == USERS ====================================================================

@app.route("/users")
def list_users():
    """
    List all rows in Users table
    """

    users_listdict = database.list_users()

    if users_listdict is None:  # error fetching users
        users_listdict = []
        flash("Error fetching users")

    page["title"] = "List Contents of users"
    return render_template(
        "users/list_users.html",
        page=page, session=session, users=users_listdict
    )


@app.route("/users/<userid>")
def list_single_users(userid):
    """
    List all rows in users that match the specified userid
    """

    users_listdict = database.list_table_equifilter(
        "Users", "userid", userid
    ) or []

    if len(users_listdict) == 0:
        flash(
            "Error, there are no rows in users that match the attribute "
            f"'userid' for the value {userid}"
        )

    page["title"] = "List Single userid for users"
    return render_template(
        "users/list_users.html",
        page=page, session=session, users=users_listdict
    )


@app.route("/consolidated/users")
def list_consolidated_users():
    """
    List all rows in users join userroles
    """

    users_userroles_listdict = database.list_consolidated_users()

    if users_userroles_listdict is None:
        users_userroles_listdict = []
        flash("Error, there are no rows in users_userroles_listdict")

    page["title"] = "List Contents of Users join Userroles"

    return render_template(
        "users/list_consolidated_users.html",
        page=page, session=session, users=users_userroles_listdict
    )


@app.route("/user_stats")
def list_user_stats():
    """
    List some user stats
    """
    # connect to the database and call the relevant function
    user_stats = database.list_user_stats()

    # Handle the null condition
    if user_stats is None:
        # Create an empty list and show error message
        user_stats = []
        flash("Error, there are no rows in user_stats")
    page["title"] = "User Stats"
    return render_template(
        "users/list_user_stats.html",
        page=page, session=session, users=user_stats
    )


@app.route("/users/search", methods=["POST", "GET"])
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

    users_listdict = database.search_table_equifilter(
        "Users",
        request.form["searchfield"],
        "~",
        request.form["searchterm"]
    )

    print(users_listdict)

    if users_listdict is None:
        flash(DATABASE_ERR_TEXT)
        return redirect(url_for("index"))

    if len(users_listdict) == 0:
        flash(
            f"No items found for search: "
            f"{request.form['searchfield']}, {request.form['searchterm']}"
        )
        return redirect(url_for("index"))

    page["title"] = "Users search"

    return render_template(
        "users/list_users.html",
        page=page, session=session, users=users_listdict
    )


@app.route("/users/delete/<userid>")
def delete_user(userid):
    """
    Delete a user
    """

    response = database.delete_user(userid)

    if response is None:
        page["title"] = f"List users after user {userid} has been deleted"
    else:
        page["title"] = f"Error deleting {userid}. Are they a valid user?"

    return redirect(url_for("list_consolidated_users"))


USER_FORM_ATTRIBUTES = ("firstname", "lastname", "userroleid", "password")
USER_FORM_ATTRIBUTE_TYPES = (str, str, int, str)


def extract_from_user_form(form, default_values: tuple) -> tuple[dict, bool]:

    user_dict: dict[str, any] = {"userid": form["userid"]}
    some_value_present = False

    print("We have a value: ", user_dict["userid"])

    for attr, typ, default in zip(
        USER_FORM_ATTRIBUTES,
        USER_FORM_ATTRIBUTE_TYPES,
        default_values
    ):
        try:
            user_dict[attr] = typ(form[attr])
            some_value_present = True
            print("We have a value: ", user_dict[attr])
        except (ValueError, KeyError):
            user_dict[attr] = default

    return user_dict, some_value_present


@app.route("/users/update", methods=["POST"])
def update_user():
    """
    Update details for a user
    """

    if not session.logged_in:
        return redirect(url_for("login"))

    if not session.isadmin:
        flash("Only admins can update user details!")
        return redirect(url_for("index"))

    page["title"] = "Update user details"

    print("request form is:")
    print(request.form)

    if "userid" not in request.form:
        flash("Can not update without a userid")
        return redirect(url_for("list_users"))

    user_dict, valid_update = extract_from_user_form(request.form, (None,) * 4)

    print("Update dict is:")
    print(user_dict, valid_update)

    if not valid_update:
        flash("No updated values for user with userid")
        return redirect(url_for("list_users"))

    database.update_single_user(user_dict["userid"],
                                user_dict["firstname"],
                                user_dict["lastname"],
                                user_dict["userroleid"],
                                user_dict["password"])

    return list_single_users(user_dict["userid"])


@app.route("/users/edit/<userid>", methods=["GET"])
def edit_user(userid):
    """
    Edit a user
    """

    if not session.logged_in:
        return redirect(url_for("login"))

    if not session.isadmin:
        flash("Only admins can update user details!")
        return redirect(url_for("index"))

    page["title"] = "Edit user details"

    users_list_dict = database.list_table_equifilter("userid", userid) or []

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
def add_user():
    """
    Add a new User
    """

    if not session.logged_in:
        return redirect(url_for("login"))

    if not session.isadmin:
        flash("Only admins can add users!")
        return redirect(url_for("index"))

    page["title"] = "Add user details"

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
        ("Empty firstname", "Empty lastname", 1, "blank")
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
        return redirect(url_for("index"))

    return list_single_users(user_dict["userid"])


# == INDEX ====================================================================

@app.route("/")
def index():
    """
    Index (home page)
    """
    # If the user is not logged in, then make them go to the login page
    if not session.logged_in:
        return redirect(url_for("login"))

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
    session.isadmin = True  # TODO fix for submission login_response[0]["isadmin"]
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.logged_in = False
    flash("You have been logged out")
    return redirect(url_for("index"))
