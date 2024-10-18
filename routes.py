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
    return render_template("tickets/list_tickets.html")


@app.route("/tickets/search")
def search_tickets_byid():
    return render_template("tickets/search_tickets_byid.html")


@app.route("/tickets/add")
def add_ticket():
    return render_template("tickets/add_ticket.html")


@app.route("/tickets/summary")
def ticket_summary():
    return render_template("tickets/ticket_summary.html")


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

    users_listdict = database.list_users_equifilter("userid", userid)

    # Handle the null condition
    if users_listdict is None or len(users_listdict) == 0:
        # Create an empty list and show error message
        users_listdict = []
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
    # connect to the database and call the relevant function
    users_userroles_listdict = database.list_consolidated_users()

    # Handle the null condition
    if users_userroles_listdict is None:
        # Create an empty list and show error message
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
def search_users_by_name():
    """
    List all rows in users that match a particular name
    """
    if request.method == "POST":

        search = database.search_users_customfilter(
            request.form["searchfield"],
            "~",
            request.form["searchterm"]
        )

        print(search)

        if search is None:
            flash(DATABASE_ERR_TEXT)
            return redirect(url_for("index"))

        if len(search) == 0:
            flash(
                f"No items found for search: "
                f"{request.form['searchfield']}, {request.form['searchterm']}"
            )

            return redirect(url_for("index"))

        users_listdict = search
        # Handle the null condition
        print(users_listdict)

        if users_listdict is None or len(users_listdict) == 0:
            # Create an empty list and show error message
            users_listdict = []
            flash(
                "Error: No users matching the name " +
                request.form["searchterm"]
            )

        page["title"] = "Users search by name"

        return render_template(
            "users/list_users.html",
            page=page, session=session, users=users_listdict
        )

    else:
        return render_template(
            "users/search_users.html",
            page=page, session=session
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


def extract_from_form(form, default_values: tuple) -> tuple[dict, bool]:

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

    user_dict, valid_update = extract_from_form(request.form, (None,) * 4)

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

    users_list_dict = database.list_users_equifilter("userid", userid) or []

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

    user_dict, _ = extract_from_form(
        request.form,
        ("Empty firstname", "Empty lastname", 1, "blank")
    )

    print("Insert parameters are:")
    print(user_dict)

    database.add_user_insert(user_dict["userid"],
                             user_dict["firstname"],
                             user_dict["lastname"],
                             user_dict["userroleid"],
                             user_dict["password"])

    return list_single_users(user_dict["userid"])
