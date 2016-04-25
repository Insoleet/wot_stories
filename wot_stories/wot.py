import networkx
from numpy import linspace
from matplotlib import pyplot as plt
from matplotlib import colors
from mpl_toolkits.mplot3d import Axes3D

from networkx.drawing.nx_agraph import graphviz_layout

class WoT:
    def __init__(self, sig_period, sig_stock, sig_validity, sig_qty, xpercent, steps_max):
        """
        :param sig_period:      Minimum time (in number of blocks) that an individual has to wait to issue a new certificate
        :param sig_stock:       Maximum number of valid certifications that an individual can issue
        :param sig_validity:    Validity period (in number of blocks) of a certification
        :param sig_qty:         Number of valid certifications an individual must have to be a member
        :param xpercent:        Percentage of sentries an individual must reach via in_edges in the Wot to be a member
        :param steps_max:       Maximum number of hops via in_edges that can be done to reach a sentry
        """

        self.sig_period = sig_period
        self.sig_stock = sig_stock
        self.sig_validity = sig_validity
        self.sig_qty = sig_qty
        self.xpercent = xpercent
        self.steps_max = steps_max

        self.wot = networkx.DiGraph()
        self.next_wot = networkx.DiGraph()
        self.members = []
        self.next_members = []

        #Block number
        self.turn = 0

        self.fig = plt.figure()
        self.ax = self.fig.gca(projection='3d')

        self.history = {}       # { member_pubkey : [join_time, leave_time, join_time, leave_time, …] }
        self.past_links = []    # [(block_number, from_idty, to_idty),(…)]

        self.colors = {}
        self.color_iter = iter(colors.cnames.items())
        self.layouts = []

    def initialize(self, idties, links):
        """
        Initialize the Wot with first members (typically block 0)
        :param idties: List of pub_keys of identities (still not members)
        :param links: List of certifications ([issuer pub_key, certified pub_key], …)
        """

        # Populate the graph with identities and certifications
        for idty in idties:
            print("{0} - Add identity during init".format(idty))
            self.wot.add_node(idty)

        for link in links:
            print("{0} -> {1} - Add certification during init".format(link[0], link[1]))
            self.wot.add_edge(link[0], link[1], {'time': 0})
            # Keep track of certifications for future analysis and plotting
            self.past_links.append((0, link[0], link[1]))

        # Check if identities are members according to Wot rules
        for node in self.wot.nodes():
            enough_certs = len(self.wot.in_edges(node)) >= self.sig_qty
            if enough_certs:
                print("{0} joined successfully on init".format(node))
                self.members.append(node)

                # Keep track of memberships in time
                if node not in self.history:
                    self.history[node] = []
                    self.colors[node] = next(self.color_iter)
                self.history[node].append(self.turn)

            else:
                print("Warning : {0} did not join during init".format(node))
        self._prepare_next_turn()

    def _prepare_next_turn(self):
        """
        Do a copy of the current state of the Wot
        """
        self.next_wot = self.wot.copy()
        self.next_members = self.members.copy()

    def add_identity(self, idty):
        """
        Add an identity (still not member) to the graph
        :param idty: Public key of an individual
        :return:
        """
        print("{0} : New identity in the wot".format(idty))
        self.next_wot.add_node(idty)

    def add_link(self, from_idty, to_idty):
        """
        Checks the validity of the certification and adds it in the graph if ok
        :param from_idty: Public key of the member which issue the certificate
        :param to_idty: Public key of the certified individual
        :return:
        """

        # Checks the issuer signatures "stock"
        out_links = self.next_wot.out_edges(from_idty, data=True)
        if len(out_links) >= self.sig_stock:
            print("{0} -> {1} : Too much certifications issued".format(from_idty, to_idty))
            return

        # Checks if the issuer has waited enough time since his last certificate before emit a new one
        print(out_links)
        if len(out_links) > 0 and max([l[2]['time'] for l in out_links]) + self.sig_period > self.turn:
            print("{0} -> {1} : Latest certification is too recent".format(from_idty, to_idty))
            return

        # Adds the certificate to the graph and keeps track
        print("{0} -> {1} : Adding certification".format(from_idty, to_idty))
        self.next_wot.add_edge(from_idty, to_idty, attr_dict={'time': self.turn})
        self.past_links.append((self.turn, from_idty, to_idty))

        # Checks if the certified individual must join the wot as a member
        if to_idty not in self.next_members and self.can_join(self.next_wot, to_idty):
            print("{0} : Joining members".format(to_idty))

            # Keep track of memberships in time
            if to_idty not in self.history:
                self.history[to_idty] = []
                self.colors[to_idty] = next(self.color_iter)
            self.history[to_idty].append(self.turn)
            self.next_members.append(to_idty)

    def can_join(self, wot, idty):
        """
        Checks if an individual must join the wot as a member regarding the wot rules
        Protocol 0.2
        :param wot:     Graph to analyse
        :param idty:    Pubkey of the candidate
        :return: False or True
        """

        # Extract the list of all connected members to idty at steps_max via certificates (edges)
        linked = networkx.predecessor(wot.reverse(copy=True), idty, cutoff=self.steps_max)

        # Extract the list of members who emits at least one valid certificate (sentries)
        sentries = [m for m in self.members if len(wot.out_edges(m)) > 0]

        # List all sentries connected at steps_max from idty
        linked_in_range = [l for l in linked if l in sentries
                           and l != idty]

        # Checks if idty is connected to at least xpercent of sentries
        enough_sentries = len(linked_in_range) >= len(sentries)*self.xpercent
        if not enough_sentries:
            print("{0} : Cannot join : not enough sentries ({1}/{2})".format(idty,
                                                                             len(linked_in_range),
                                                                             len(sentries)*self.xpercent))

        # Checks if idty has enough certificates to be a member
        enough_certs = len(wot.in_edges(idty)) >= self.sig_qty
        if not enough_certs:
            print("{0} : Cannot join : not enough certifications ({1}/{2}".format(idty,
                                                                                  len(wot.in_edges(idty)),
                                                                                  self.sig_qty))

        return enough_certs and enough_sentries

    def next_turn(self):
        """
        Updates the wot by removing expired links and members
        """
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
                if link[0] in self.history:
                    self.history[link[0]].append(self.turn)

        self.wot = self.next_wot
        self.members = self.next_members
        #elf.layouts.append(graphviz_layout(self.wot, "twopi"))
        self._prepare_next_turn()

    def draw(self, zscale=1):
        for n in self.history:
            if len(self.history[n]) % 2 != 0:
                self.history[n].append(self.turn)
        pos = graphviz_layout(self.wot, "twopi")

        for n in self.history:
            periods = list(zip(self.history[n], self.history[n][1:]))
            for i, p in enumerate(periods):
                nbpoints = abs(p[1] - p[0])*zscale
                zline = linspace(p[0]*zscale, p[1]*zscale, nbpoints)
                xline = linspace(pos[n][0], pos[n][0], nbpoints)
                yline = linspace(pos[n][1], pos[n][1], nbpoints)
                plot = self.ax.plot(xline, zline, yline, zdir='y', color=self.colors[n][0], alpha=1/(i % 2 + 1))

        for link in self.past_links:
            nbpoints = abs(pos[link[2]][0] - pos[link[1]][1])*zscale
            zline = linspace(link[0]*zscale, link[0]*zscale, nbpoints)
            xline = linspace(pos[link[2]][0], pos[link[1]][0], nbpoints)
            yline = linspace(pos[link[2]][1], pos[link[1]][1], nbpoints)
            if link[1] in self.colors:
                self.ax.plot(xline, zline, yline, zdir='y', color=self.colors[link[1]][0], alpha=0.1)

            #txt = self.ax.text(pos[n][0], pos[n][1], self.history[n][0]*zscale, n[:5], 'z')

        self.ax.set_xlim3d(-5, max([p[0] for p in pos.values()]))
        self.ax.set_ylim3d(-5, max([p[1] for p in pos.values()]))
        self.ax.set_zlim3d(-5, (self.turn+1)*zscale)
