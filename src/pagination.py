import math


class Pagination:
    def __init__(
        self,
        page_no: int,
        tickets_per_page: int,
        total_tickets: int,
        max_jump: int = 5
    ):
        num_pages = math.ceil(total_tickets / tickets_per_page)

        self.page = min(num_pages, max(1, page_no))
        self.per_page = tickets_per_page
        self.total = total_tickets
        self.pages = num_pages
        self.has_prev = page_no > 1
        self.has_next = page_no < num_pages
        self.max_jump = max_jump
