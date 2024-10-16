class Session:
    def __init__(self):
        self.name = None
        self.userid = None
        self.logged_in = False
        self.isadmin = False

    def __getitem__(self, key: str):

        if key == "name":
            return self.name
        elif key == "userid":
            return self.userid
        elif key == "logged_in":
            return self.logged_in
        elif key == "isadmin":
            return self.isadmin

        return None
