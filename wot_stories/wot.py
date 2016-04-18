import networkx

class WoT:
    def __init__(self, sig_period, sig_stock, sig_window, sig_validity, sig_qty, xpercent, steps_max):
        self.sig_period = sig_period
        self.sig_stock = sig_stock
        self.sig_window = sig_window
        self.sig_validity = sig_validity
        self.sig_qty = sig_qty
        self.xpercent = xpercent
        self.steps_max = steps_max
        self.wot = networkx.DiGraph()
        self.next_wot = networkx.DiGraph()
        self.members = []
        self.next_members = []
        self.turn = 0

    def initialize(self, idties, links):
        for idty in idties:
            print("{0} - Add identity during init".format(idty))
            self.wot.add_node(idty)

        for link in links:
            print("{0} -> {1} - Add certification during init".format(link[0], link[1]))
            self.wot.add_edge(link[0], link[1], {'time': 0})

        for node in self.wot.nodes():
            enough_certs = len(self.wot.in_edges(node)) >= self.sig_qty
            if enough_certs:
                print("{0} joined successfully on init".format(node))
                self.members.append(node)
            else:
                print("Warning : {0} did not join during init".format(node))

    def prepare_next_turn(self):
        self.next_wot = self.wot.copy()
        self.next_members = self.members.copy()

    def add_identity(self, idty):
        print("{0} : New identity in the wot".format(idty))
        self.next_wot.add_node(idty)

    def add_link(self, from_idty, to_idty):
        out_links = self.next_wot.out_edges(from_idty, data=True)
        if len(out_links) >= self.sig_stock:
            print("{0} -> {1} : Too much certifications issued".format(from_idty, to_idty))
            return

        print(out_links)
        if max([l[2]['time'] for l in out_links]) + self.sig_window < self.turn:
            print("{0} -> {1} : Latest certification is too recent".format(from_idty, to_idty))
            return

        print("{0} -> {1} : Adding certification".format(from_idty, to_idty))
        self.next_wot.add_edge(from_idty, to_idty, attr_dict={'time': self.turn})

        if to_idty not in self.next_members and self.can_join(self.next_wot, to_idty):
            print("{0} : Joining members".format(to_idty))
            self.next_members.append(to_idty)

    def can_join(self, wot, idty):
        linked = networkx.floyd_warshall_predecessor_and_distance(wot.reverse(copy=True), idty)
        linked_in_range = [l for l in linked[1][idty] if l in self.members and linked[1][idty][l] <= self.steps_max]

        enough_sentries = len(linked_in_range) >= len(self.members)*self.xpercent
        if not enough_sentries:
            print("{0} : Cannot join : not enough sentries ({1}/{2})".format(idty,
                                                                             len(linked_in_range),
                                                                             len(self.members)*self.xpercent))

        enough_certs = len(wot.in_edges(idty)) >= self.sig_qty
        if not enough_certs:
            print("{0} : Cannot join : not enough certifications ({1}/{2}".format(idty,
                                                                                  len(wot.in_edges(idty)),
                                                                                  self.sig_qty))

        return enough_certs and enough_sentries

    def next_turn(self):
        self.turn += 1
        dropped_links = []
        print("== New turn {0} ==".format(self.turn))
        # Links expirations
        for link in self.next_wot.copy().edges(data=True):
            if self.turn > link[2]['time'] + self.sig_validity:
                print("{0} -> {1} : Link expired ({2}/{3})".format(link[0], link[1],
                                                                   self.turn, link[2]['time'] + self.sig_validity))
                self.next_wot.remove_edge(link[0], link[1])
                dropped_links.append(link)

        for link in dropped_links:
            if link[0] in self.next_members and not self.can_join(self.next_wot, link[0]):
                print("{0} : Left community".format(link[0]))
                self.next_members.remove(link[0])

        self.wot = self.next_wot
        self.members = self.next_members

    def draw(self):
        #from networkx.drawing.nx_agraph import graphviz_layout
        #pos = graphviz_layout(self.wot, "twopi")
        #networkx.draw(self.wot, pos)
        networkx.draw_shell(self.wot)