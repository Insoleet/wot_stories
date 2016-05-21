from graph_tool.all import *
from numpy import linspace
from matplotlib import pyplot as plt
from matplotlib import colors
from mpl_toolkits.mplot3d import Axes3D
from itertools import product


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

        self.wot = Graph(directed=True)
        self.next_wot = Graph(directed=True)
        self.wot.ep.time = self.wot.new_edge_property("int")
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

    def initialize(self, nb_identities):
        """
        Initialize the Wot with first members (typically block 0)
        :param idties: List of pub_keys of identities (still not members)
        :param links: List of certifications ([issuer pub_key, certified pub_key], …)
        """

        identities = []
        # Populate the graph with identities and certifications
        for idty in range(0, nb_identities):
            print("{0} - Add identity during init".format(idty))
            identities.append(int(self.wot.add_vertex()))

        init_links = list(product(identities, identities))
        for link in init_links:
            if link[1] != link[0]:
                print("{0} -> {1} - Add certification during init".format(link[0], link[1]))
                edge = self.wot.add_edge(link[0], link[1])
                self.wot.ep.time[edge] = 0
                # Keep track of certifications for future analysis and plotting
                self.past_links.append((0, link[0], link[1]))

        # Check if identities are members according to Wot rules
        for vertex in self.wot.vertices():
            enough_certs = vertex.in_degree() >= self.sig_qty
            if enough_certs:
                print("{0} joined successfully on init".format(vertex))
                self.members.append(int(vertex))

                # Keep track of memberships in time
                if vertex not in self.history:
                    self.history[int(vertex)] = []
                    self.colors[int(vertex)] = next(self.color_iter)
                self.history[int(vertex)].append(self.turn)
            else:
                print("Warning : {0} did not join during init ({1} certs)".format(int(vertex),
                                                                                  vertex.in_degree()))
        self._prepare_next_turn()

    def _prepare_next_turn(self):
        """
        Do a copy of the current state of the Wot
        """
        self.next_wot = self.wot.copy()
        self.next_members = self.members.copy()

    def add_identity(self):
        """
        Add an identity (still not member) to the graph
        :param idty: Public key of an individual
        :return:
        """
        v = self.next_wot.add_vertex()
        print("{0} : New identity in the wot".format(int(v)))
        return int(v)

    def add_link(self, from_idty, to_idty):
        """
        Checks the validity of the certification and adds it in the graph if ok
        :param from_idty: Public key of the member which issue the certificate
        :param to_idty: Public key of the certified individual
        :return:
        """
        # Checks the issuer signatures "stock"
        vertex = self.next_wot.vertex(from_idty)
        out_links = vertex.out_edges()
        if vertex.out_degree() >= self.sig_stock:
            print("{0} -> {1} : Too much certifications issued".format(from_idty, to_idty))
            return

        # Checks if the issuer has waited enough time since his last certificate before emit a new one
        if vertex.out_degree() > 0 and max([self.wot.ep.time[l] for l in out_links]) + self.sig_period > self.turn:
            print("{0} -> {1} : Latest certification is too recent".format(from_idty, to_idty))
            return

        # Adds the certificate to the graph and keeps track
        print("{0} -> {1} : Adding certification".format(from_idty, to_idty))
        edge = self.next_wot.add_edge(from_idty, to_idty)
        self.next_wot.ep.time[edge] = self.turn
        self.past_links.append((self.turn, from_idty, to_idty))

        # Checks if the certified individual must join the wot as a member
        if to_idty not in self.next_members and self.can_join(self.next_wot, to_idty):
            print("{0} : Joining members".format(to_idty))

            # Keep track of memberships in time
            if to_idty not in self.history:
                self.history[to_idty] = []
                try:
                    self.colors[to_idty] = next(self.color_iter)
                except StopIteration:
                    self.color_iter = iter(colors.cnames.items())
                    self.colors[to_idty] = next(self.color_iter)

            self.history[to_idty].append(self.turn)
            self.next_members.append(to_idty)

    def ySentries(self, N):
        Y = {
            10: 2,
            100: 4,
            1000: 6,
            10000: 12,
            100000: 20
        }
        for k in reversed(sorted(Y.keys())):
            if N >= k:
                return Y[k]
        return 0

    def can_join(self, wot, idty):
        """
        Checks if an individual must join the wot as a member regarding the wot rules
        Protocol 0.2
        :param wot:     Graph to analyse
        :param idty:    Pubkey of the candidate
        :return: False or True
        """
        sentries = [m for m in self.members if wot.vertex(m).out_degree() > self.ySentries(len(self.members))]
        # Extract the list of all connected members to idty at steps_max via certificates (edges)

        linked_in_range = []
        for s in sentries:
            if graph_tool.topology.shortest_distance(wot,
                                                 wot.vertex(s),
                                                 wot.vertex(idty)) <= self.steps_max:
                linked_in_range.append(s)

        # Checks if idty is connected to at least xpercent of sentries
        enough_sentries = len(linked_in_range) >= len(sentries)*self.xpercent
        if not enough_sentries:
            print("{0} : Cannot join : not enough sentries ({1}/{2})".format(idty,
                                                                             len(linked_in_range),
                                                                             len(sentries)*self.xpercent))

        # Checks if idty has enough certificates to be a member
        enough_certs = wot.vertex(idty).in_degree() >= self.sig_qty
        if not enough_certs:
            print("{0} : Cannot join : not enough certifications ({1}/{2}".format(idty,
                                                                                  wot.vertex(idty).in_degree(),
                                                                                  self.sig_qty))

        return enough_certs and enough_sentries

    def next_turn(self):
        """
        Updates the wot by removing expired links and members
        """
        self.turn += 1
        dropped_links = []
        print("== New turn {0} ==".format(self.turn))
        tmp_wot = self.next_wot.copy()
        # Links expirations
        for link in tmp_wot.edges():
            if self.turn > tmp_wot.ep.time[link] + self.sig_validity:
                print("{0} -> {1} : Link expired ({2}/{3})".format(int(link.source()), int(link.target()),
                                                                   self.turn,
                                                                   tmp_wot.ep.time[link] + self.sig_validity))
                self.next_wot.remove_edge(self.next_wot.edge(int(link.source()), int(link.target())))
                dropped_links.append(link)

        for link in dropped_links:
            if int(link.target()) in self.next_members and not self.can_join(self.next_wot, int(link.target())):
                print("{0} : Left community".format(link.target()))
                self.next_members.remove(int(link.target()))
                if int(link.target()) in self.history:
                    self.history[int(link.target())].append(self.turn)

        self.wot = self.next_wot
        self.members = self.next_members
        #elf.layouts.append(graphviz_layout(self.wot, "twopi"))
        self._prepare_next_turn()

    def draw(self, zscale=1):
        for n in self.history:
            if len(self.history[n]) % 2 != 0:
                self.history[n].append(self.turn)
        pos = graph_tool.draw.arf_layout(self.wot)

        for n in self.history:
            periods = list(zip(self.history[n], self.history[n][1:]))
            for i, p in enumerate(periods):
                nbpoints = abs(p[1] - p[0])*zscale
                zline = linspace(p[0]*zscale, p[1]*zscale, nbpoints)
                xline = linspace(pos[n][0], pos[n][0], nbpoints)
                yline = linspace(pos[n][1], pos[n][1], nbpoints)
                print(self.colors)
                plot = self.ax.plot(xline, zline, yline, zdir='y', color=self.colors[n][0], alpha=1/(i % 2 + 1))

        for link in self.past_links:
            nbpoints = abs(pos[link[2]][0] - pos[link[1]][1])*zscale
            zline = linspace(link[0]*zscale, link[0]*zscale, nbpoints)
            xline = linspace(pos[link[2]][0], pos[link[1]][0], nbpoints)
            yline = linspace(pos[link[2]][1], pos[link[1]][1], nbpoints)
            if link[1] in self.colors:
                self.ax.plot(xline, zline, yline, zdir='y', color=self.colors[link[1]][0], alpha=0.1)

        self.ax.set_xlim3d(0, 10)
        self.ax.set_ylim3d(0, 10)
        self.ax.set_zlim3d(-5, (self.turn+1)*zscale)

    def draw_turn(self, turn):

        fig, ax_f = plt.subplots()
        pos = graph_tool.draw.arf_layout(self.wot)

        for n in self.history:
            periods = list(zip(self.history[n], self.history[n][1:]))
            for i, p in enumerate(periods):
                if p[0] < turn < p[1]:
                    nbpoints = abs(p[1] - p[0])
                    xline = linspace(pos[n][0], pos[n][0], nbpoints)
                    yline = linspace(pos[n][1], pos[n][1], nbpoints)
                    ax_f.plot(xline, yline, color=self.colors[n][0], alpha=1 / (i % 2 + 1))

        for link in self.past_links:
            if link[0] < turn < link[0] + self.sig_validity:
                nbpoints = abs(pos[link[2]][0] - pos[link[1]][1])
                xline = linspace(pos[link[2]][0], pos[link[1]][0], nbpoints)
                yline = linspace(pos[link[2]][1], pos[link[1]][1], nbpoints)
                if link[1] in self.colors:
                    ax_f.plot(xline, yline, color=self.colors[link[1]][0], alpha=0.1)

        ax_f.set_xlim(0, 10)
        ax_f.set_ylim(0, 10)
