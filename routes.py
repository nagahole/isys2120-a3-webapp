import configparser
from typing import Optional

from flask import *

import database
from session import Session


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

    if request.method == "POST":
        print(request.form)

        logins = database.check_login(
            request.form["userid"],
            request.form["password"]
        )

        print(logins)

        # If our database connection gave back an error
        if logins is None:
            errortext = "Error with the database connection. "
            errortext += "Please check your terminal " \
                         "and make sure you updated your INI files."
            flash(errortext)
            return redirect(url_for("login"))

        # If it"s null, or nothing came up, flash a message saying error
        # And make them go back to the login screen
        if logins is None or len(logins) < 1:
            flash("There was an error logging you in")
            return redirect(url_for("login"))

        # If it was successful, then we can log them in :)
        print(logins[0])
        session.name = logins[0]["firstname"]
        session.userid = request.form["userid"]
        session.logged_in = True
        session.isadmin = logins[0]["isadmin"]
        return redirect(url_for("index"))
    else:
        # Else, they"re just looking at the page :)
        if session.get("logged_in", False) is True:
            return redirect(url_for("index"))
        return render_template("index.html", page=page)


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
def search_users_byname():
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
            errortext = "Error with the database connection."
            errortext += "Please check your terminal and " \
                         "make sure you updated your INI files."
            flash(errortext)

            return redirect(url_for("index"))

        if len(search) == 0:
            flash(
                f"No items found for search: "
                f"{request.form['searchfield']}, {request.form['searchterm']}"
            )

            return redirect(url_for("index"))

        users_listdict = search
        # Handle the null condition"
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
        return render_template("users/search_users.html", page=page, session=session)

@app.route("/users/delete/<userid>")
def delete_user(userid):
    """
    Delete a user
    """
    # connect to the database and call the relevant function
    resultval = database.delete_user(userid)

    page["title"] = f"List users after user {userid} has been deleted"
    return redirect(url_for("list_consolidated_users"))

@app.route("/users/update", methods=["POST","GET"])
def update_user():
    """
    Update details for a user
    """
    # # Check if the user is logged in, if not: back to login.
    if not session.logged_in:
        return redirect(url_for("login"))

    if not session.isadmin:
        flash("Only admins can update user details!")
        return

    page["title"] = "Update user details"

    userslist = None

    print("request form is:")
    newdict: dict[str, Optional[str]] = {}
    print(request.form)

    validupdate = False
    # Check your incoming parameters
    if request.method == "POST":

        # verify that at least one value is available:
        if "userid" not in request.form:
            # should be an exit condition
            flash("Can not update without a userid")
            return redirect(url_for("list_users"))
        else:
            newdict["userid"] = request.form["userid"]
            print("We have a value: ",newdict["userid"])

        if "firstname" not in request.form:
            newdict["firstname"] = None
        else:
            validupdate = True
            newdict["firstname"] = request.form["firstname"]
            print("We have a value: ",newdict["firstname"])

        if "lastname" not in request.form:
            newdict["lastname"] = None
        else:
            validupdate = True
            newdict["lastname"] = request.form["lastname"]
            print("We have a value: ",newdict["lastname"])

        if "userroleid" not in request.form:
            newdict["userroleid"] = None
        else:
            validupdate = True
            newdict["userroleid"] = request.form["userroleid"]
            print("We have a value: ",newdict["userroleid"])

        if "password" not in request.form:
            newdict["password"] = None
        else:
            validupdate = True
            newdict["password"] = request.form["password"]
            print("We have a value: ",newdict["password"])

        print("Update dict is:")
        print(newdict, validupdate)

        if validupdate:
            #forward to the database to manage update
            userslist = database.update_single_user(newdict["userid"],newdict["firstname"],newdict["lastname"],newdict["userroleid"],newdict["password"])
        else:
            # no updates
            flash("No updated values for user with userid")
            return redirect(url_for("list_users"))
        # Should redirect to your newly updated user
        return list_single_users(newdict["userid"])
    else:
        return redirect(url_for("list_consolidated_users"))

######
## Edit user
######
@app.route("/users/edit/<userid>", methods=["POST","GET"])
def edit_user(userid):
    """
    Edit a user
    """
    # Check if the user is logged in, if not: back to login.
    if not session.logged_in:
        return redirect(url_for("login"))

    if not session.isadmin:
        flash("Only admins can update user details!")
        return

    page["title"] = "Edit user details"

    users_listdict = None
    users_listdict = database.list_users_equifilter("userid", userid)

    # Handle the null condition
    if users_listdict is None or len(users_listdict) == 0:
        # Create an empty list and show error message
        users_listdict = []
        flash("Error, there are no rows in users that match the attribute 'userid' for the value "+userid)

    userslist = None
    print("request form is:")
    newdict: dict[str, Optional[str]] = {}
    print(request.form)
    user = users_listdict[0]
    validupdate = False

    # Check your incoming parameters
    if request.method == "POST":

        # verify that at least one value is available:
        if "userid" not in request.form:
            # should be an exit condition
            flash("Can not update without a userid")
            return redirect(url_for("list_users"))
        else:
            newdict["userid"] = request.form["userid"]
            print("We have a value: ",newdict["userid"])

        if "firstname" not in request.form:
            newdict["firstname"] = None
        else:
            validupdate = True
            newdict["firstname"] = request.form["firstname"]
            print("We have a value: ",newdict["firstname"])

        if "lastname" not in request.form:
            newdict["lastname"] = None
        else:
            validupdate = True
            newdict["lastname"] = request.form["lastname"]
            print("We have a value: ",newdict["lastname"])

        if "userroleid" not in request.form:
            newdict["userroleid"] = None
        else:
            validupdate = True
            newdict["userroleid"] = request.form["userroleid"]
            print("We have a value: ",newdict["userroleid"])

        if "password" not in request.form:
            newdict["password"] = None
        else:
            validupdate = True
            newdict["password"] = request.form["password"]
            print("We have a value: ",newdict["password"])

        print("Update dict is:")
        print(newdict, validupdate)

        if validupdate:
            #forward to the database to manage update
            userslist = database.update_single_user(newdict["userid"],newdict["firstname"],newdict["lastname"],newdict["userroleid"],newdict["password"])
        else:
            # no updates
            flash("No updated values for user with userid")
            return redirect(url_for("list_users"))
        # Should redirect to your newly updated user
        return list_single_users(newdict["userid"])
    else:
        # assuming GET request, need to setup for this
        return render_template("users/edit_user.html",
                               session=session,
                               page=page,
                               userroles=database.list_userroles(),
                               user=user)


######
## add items
######


@app.route("/users/add", methods=["POST","GET"])
def add_user():
    """
    Add a new User
    """
    # # Check if the user is logged in, if not: back to login.
    if not session.logged_in:
        return redirect(url_for("login"))

    if not session.isadmin:
        flash("Only admins can add users!")
        return

    page["title"] = "Add user details"

    userslist = None
    print("request form is:")
    newdict: dict[str, any] = {}
    print(request.form)

    # Check your incoming parameters
    if request.method == "POST":

        # verify that all values are available:
        if "userid" not in request.form:
            # should be an exit condition
            flash("Can not add user without a userid")
            return redirect(url_for("add_user"))
        else:
            newdict["userid"] = request.form["userid"]
            print("We have a value: ",newdict["userid"])

        if "firstname" not in request.form:
            newdict["firstname"] = "Empty firstname"
        else:
            newdict["firstname"] = request.form["firstname"]
            print("We have a value: ",newdict["firstname"])

        if "lastname" not in request.form:
            newdict["lastname"] = "Empty lastname"
        else:
            newdict["lastname"] = request.form["lastname"]
            print("We have a value: ",newdict["lastname"])

        if "userroleid" not in request.form:
            newdict["userroleid"] = 1 # default is traveler
        else:
            newdict["userroleid"] = request.form["userroleid"]
            print("We have a value: ",newdict["userroleid"])

        if "password" not in request.form:
            newdict["password"] = "blank"
        else:
            newdict["password"] = request.form["password"]
            print("We have a value: ",newdict["password"])

        print("Insert parametesrs are:")
        print(newdict)

        database.add_user_insert(newdict["userid"], newdict["firstname"],newdict["lastname"],newdict["userroleid"],newdict["password"])
        # Should redirect to your newly updated user
        print("did it go wrong here?")
        return redirect(url_for("list_consolidated_users"))
    else:
        # assuming GET request, need to setup for this
        return render_template("users/add_user.html",
                               session=session,
                               page=page,
                               userroles=database.list_userroles())
