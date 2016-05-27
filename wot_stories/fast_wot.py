from graph_tool.all import *
from numpy import linspace, sqrt
from matplotlib import pyplot as plt
from matplotlib import colors
from mpl_toolkits.mplot3d import Axes3D
from itertools import product
import logging
import pickle
import os, errno

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

        self.wot = []
        self.members = []
        self.identities = []
        self.received_links = []

        #Block number
        self.turn = 0

        self.history = {}       # { member_pubkey : [join_time, leave_time, join_time, leave_time, …] }
        self.past_links = []    # [(block_number, from_idty, to_idty),(…)]

        self.colors = {}
        self.color_iter = iter(colors.cnames.items())

    def load(self, dest):
        with open(os.path.join(dest, "history.p"), "rb") as outfile:
            self.history = pickle.load(outfile)

        with open(os.path.join(dest, "past_links.p"), "rb") as outfile:
            self.past_links = pickle.load(outfile)

        with open(os.path.join(dest, "members.p"), "rb") as outfile:
            self.members = pickle.load(outfile)

        with open(os.path.join(dest, "identities.p"), "rb") as outfile:
            self.identities = pickle.load(outfile)

        with open(os.path.join(dest, "colors.p"), "rb") as outfile:
            self.colors = pickle.load(outfile)

        with open(os.path.join(dest, "attributes.p"), "rb") as outfile:
            parameters = pickle.load(outfile)
            self.sig_period = parameters["sig_period"]
            self.sig_stock = parameters["sig_stock"]
            self.sig_validity = parameters["sig_validity"]
            self.sig_qty = parameters["sig_qty"]
            self.xpercent = parameters["xpercent"]
            self.steps_max = parameters["steps_max"]
            self.turn = parameters["turn"]

        self.wot = []
        for i in range(0, self.turn+1):
            self.wot.append(load_graph(os.path.join(dest, "wot", "wot{0}.gt".format(i))))

            print('\r[{0}{1}] {2:10.2f}% - Loading...'.format('#' * int(i / self.turn * 10),
                  ' ' * (10 - (int(i / self.turn * 10))),
                  (i/self.turn) * 100))

    def save(self, dest):
        try:
            os.makedirs(os.path.join(dest, "wot"))
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise
        with open(os.path.join(dest, "history.p"), "wb") as outfile:
            pickle.dump(self.history, outfile)

        with open(os.path.join(dest, "past_links.p"), "wb") as outfile:
            pickle.dump(self.past_links, outfile)

        with open(os.path.join(dest, "members.p"), "wb") as outfile:
            pickle.dump(self.members, outfile)

        with open(os.path.join(dest, "identities.p"), "wb") as outfile:
            pickle.dump(self.identities, outfile)

        with open(os.path.join(dest, "colors.p"), "wb") as outfile:
            pickle.dump(self.colors, outfile)

        with open(os.path.join(dest, "attributes.p"), "wb") as outfile:
            parameters = {
                'sig_period': self.sig_period,
                'sig_stock': self.sig_stock,
                'sig_validity': self.sig_validity,
                'sig_qty': self.sig_qty,
                'xpercent': self.xpercent,
                'steps_max': self.steps_max,
                'turn': self.turn
            }
            pickle.dump(parameters, outfile)
        for i, w in enumerate(self.wot):
            w.save(os.path.join(dest, "wot", "wot{0}.gt".format(i)))

    def initialize(self, nb_identities):
        """
        Initialize the Wot with first members (typically block 0)
        :param idties: List of pub_keys of identities (still not members)
        :param links: List of certifications ([issuer pub_key, certified pub_key], …)
        """
        self.members.append([])
        self.identities.append([])

        self.wot.append(Graph(directed=True))
        self.wot[0].ep.time = self.wot[0].new_edge_property("int")
        # Populate the graph with identities and certifications
        for idty in range(0, nb_identities):
            logging.debug("{0} - Add identity during init".format(idty))
            v = self.wot[0].add_vertex()
            logging.debug("{0} : New identity in the wot".format(int(v)))
            # Keep track of memberships in time
            if int(v) not in self.history:
                self.history[int(v)] = [self.turn]
                try:
                    self.colors[int(v)] = next(self.color_iter)
                except StopIteration:
                    self.color_iter = iter(colors.cnames.items())
                    self.colors[int(v)] = next(self.color_iter)
            self.identities[self.turn].append(int(v))

        init_links = list(product(self.identities[0], self.identities[0]))
        for link in init_links:
            if link[1] != link[0]:
                logging.debug("{0} -> {1} - Add certification during init".format(link[0], link[1]))
                edge = self.wot[0].add_edge(link[0], link[1])
                self.wot[0].ep.time[edge] = 0
                # Keep track of certifications for future analysis and plotting
                self.past_links.append((0, link[0], link[1]))

        # Check if identities are members according to Wot rules
        for vertex in self.wot[0].vertices():
            enough_certs = vertex.in_degree() >= self.sig_qty
            if enough_certs:
                logging.debug("{0} joined successfully on init".format(vertex))
                self.members[0].append(int(vertex))

                # Keep track of memberships in time
                if vertex not in self.history:
                    self.colors[int(vertex)] = next(self.color_iter)
                self.history[int(vertex)].append(self.turn)
            else:
                logging.debug("Warning : {0} did not join during init ({1} certs)".format(int(vertex),
                                                                                  vertex.in_degree()))
        self._prepare_next_turn()

    #@profile
    def _prepare_next_turn(self):
        """
        Do a copy of the current state of the Wot
        """
        self.received_links = []
        self.wot.append(self.wot[self.turn].copy())
        self.members.append(self.members[self.turn].copy())
        self.identities.append(self.identities[self.turn].copy())

    #@profile
    def add_identity(self):
        """
        Add an identity (still not member) to the graph
        :param idty: Public key of an individual
        :return:
        """
        v = self.wot[self.turn+1].add_vertex()
        logging.debug("{0} : New identity in the wot".format(int(v)))

        # Keep track of memberships in time
        if int(v) not in self.history:
            self.history[int(v)] = [self.turn+1]
            try:
                self.colors[int(v)] = next(self.color_iter)
            except StopIteration:
                self.color_iter = iter(colors.cnames.items())
                self.colors[int(v)] = next(self.color_iter)
        self.identities[self.turn+1].append(int(v))
        return int(v)

    #@profile
    def add_link(self, from_idty, to_idty):
        """
        Checks the validity of the certification and adds it in the graph if ok
        :param from_idty: Public key of the member which issue the certificate
        :param to_idty: Public key of the certified individual
        :return:
        """
        if from_idty == to_idty:
            logging.debug("{0} -> {1} : Error : link on self")
            return

        # Checks the issuer signatures "stock"
        vertex = self.wot[self.turn+1].vertex(from_idty)
        out_links = vertex.out_edges()
        if vertex.out_degree() >= self.sig_stock:
            logging.debug("{0} -> {1} : Too much certifications issued".format(from_idty, to_idty))
            return

        # Checks if the issuer has waited enough time since his last certificate before emit a new one
        if vertex.out_degree() > 0 and max([self.wot[0].ep.time[l]
                                            for l in out_links]) + self.sig_period > self.turn:
            logging.debug("{0} -> {1} : Latest certification is too recent".format(from_idty, to_idty))
            return

        # Adds the certificate to the graph and keeps track
        logging.debug("{0} -> {1} : Adding certification".format(from_idty, to_idty))
        edge = self.wot[self.turn+1].edge(from_idty, to_idty)
        if not edge:
            edge = self.wot[self.turn+1].add_edge(from_idty, to_idty)
        self.wot[self.turn+1].ep.time[edge] = self.turn
        self.past_links.append((self.turn, from_idty, to_idty))

        # Checks if the certified individual must join the wot as a member
        if to_idty not in self.members[self.turn+1]:
            self.received_links.append(to_idty)

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

    #@profile
    def can_join(self, wot, sentries, computed_links, distances, idty):
        """
        Checks if an individual must join the wot as a member regarding the wot rules
        Protocol 0.2
        :param wot:     Graph to analyse
        :param idty:    Pubkey of the candidate
        :return: False or True
        """
        # Extract the list of all connected members to idty at steps_max via certificates (edges)

        linked_in_range = []
        ind = computed_links.index(idty)
        for s in sentries:
            try:
                if distances[s][ind] <= self.steps_max:
                    linked_in_range.append(s)
            except IndexError:
                print(distances[s])
                print(ind)

        # Checks if idty is connected to at least xpercent of sentries
        enough_sentries = len(linked_in_range) >= len(sentries)*self.xpercent
        if not enough_sentries:
            logging.debug("{0} : Cannot join : not enough sentries ({1}/{2})".format(idty,
                                                                             len(linked_in_range),
                                                                             len(sentries)*self.xpercent))

        # Checks if idty has enough certificates to be a member
        enough_certs = wot.vertex(idty).in_degree() >= self.sig_qty
        if not enough_certs:
            logging.debug("{0} : Cannot join : not enough certifications ({1}/{2}".format(idty,
                                                                                  wot.vertex(idty).in_degree(),
                                                                                  self.sig_qty))

        return enough_certs and enough_sentries

    #@profile
    def next_turn(self):
        """
        Updates the wot by removing expired links and members
        """
        dropped_links = []
        logging.debug("== New turn {0} ==".format(self.turn+1))

        tmp_wot = self.wot[self.turn+1].copy()
        # Links expirations
        for link in tmp_wot.edges():
            if self.turn > tmp_wot.ep.time[link] + self.sig_validity:
                logging.debug("{0} -> {1} : Link expired ({2}/{3})".format(int(link.source()), int(link.target()),
                                                                   self.turn+1,
                                                                   tmp_wot.ep.time[link] + self.sig_validity))
                self.wot[self.turn+1].remove_edge(self.wot[self.turn+1].edge(int(link.source()), int(link.target())))
                dropped_links.append(int(link.target()))

        computed_links = dropped_links + self.received_links

        sentries = [m for m in self.members[self.turn]
                    if self.wot[self.turn].vertex(m).out_degree() > self.ySentries(len(self.members[self.turn]))]

        distances = {}
        for s in sentries:
            distances[s] = graph_tool.topology.shortest_distance(self.wot[self.turn+1],
                                              source=s,
                                              target=computed_links,
                                              max_dist=self.steps_max,
                                              directed=True)

        for receiver in self.received_links:
            if receiver not in self.members[self.turn + 1] and self.can_join(self.wot[self.turn + 1],
                                                                                sentries,
                                                                                computed_links,
                                                                               distances,
                                                                             receiver):
                logging.debug("{0} : Joined community".format(receiver))
                self.history[receiver].append(self.turn)
                self.members[self.turn+1].append(receiver)

        for dropped in dropped_links:
            if dropped in self.members[self.turn+1] and not self.can_join(self.wot[self.turn+1],
                                                                                    sentries,
                                                                                     computed_links,
                                                                                    distances,
                                                                                    dropped):
                logging.debug("{0} : Left community".format(dropped))
                self.members[self.turn+1].remove(dropped)
                self.history[dropped].append(self.turn+1)

        self.turn += 1
        self._prepare_next_turn()

    def end(self):
        for n in self.history:
            if len(self.history[n]) % 2 == 0:
                self.history[n].append(self.turn)

    def draw(self, zscale=1):

        fig = plt.figure()
        ax = fig.gca(projection='3d')
        pos = graph_tool.draw.arf_layout(self.wot[self.turn])

        step = 0
        size = len(self.history.keys())
        for n in self.history:
            step = step + 1
            periods = list(zip(self.history[n], self.history[n][1:]))
            for i, p in enumerate(periods):
                nbpoints = abs(p[1] - p[0])*zscale
                zline = linspace(p[0]*zscale, p[1]*zscale, nbpoints)
                xline = linspace(pos[n][0], pos[n][0], nbpoints)
                yline = linspace(pos[n][1], pos[n][1], nbpoints)
                plot = ax.plot(xline, zline, yline, zdir='y',
                                    color=self.colors[n][0], alpha=abs(1/(((i+1) % 2) + 1)))

            print('\r[{0}{1}] {2:10.2f}% - Rendering plots...'.format('#' * int(step / (2 * size) * 10),
                  ' ' * (10 - (int(step / (2 * size) * 10))),
                  (step / size) * 100))

        step = 0
        size = len(self.past_links)
        for link in self.past_links:
            step = step + 1
            nbpoints = abs(pos[link[2]][0] - pos[link[1]][1])*100
            zline = linspace(link[0]*zscale, link[0]*zscale, nbpoints)
            xline = linspace(pos[link[2]][0], pos[link[1]][0], nbpoints)
            yline = linspace(pos[link[2]][1], pos[link[1]][1], nbpoints)
            if link[1] in self.colors:
                ax.plot(xline, zline, yline, zdir='y', color=self.colors[link[1]][0], alpha=0.1)

            print('\r[{0}{1}] {2:10.2f}% - Rendering links...'.format('#' * int(step / (2 * size) * 10 + 5),
                  ' ' * (10 - (int(step / (2 * size * 10) + 5))),
                  (step / size) * 50 + 50))

        ax.set_xlim3d(min([pos[v][0] for v in self.wot[self.turn].vertices()]),
                            max([pos[v][0] for v in self.wot[self.turn].vertices()]))
        ax.set_ylim3d(min([pos[v][1] for v in self.wot[self.turn].vertices()]),
                           max([pos[v][1] for v in self.wot[self.turn].vertices()]))
        ax.set_zlim3d(-5, (self.turn+1)*zscale)

    def draw_turn(self, turn, outpath):
        pos = graph_tool.draw.sfdp_layout(self.wot[turn], C=0.6, p=12)
        self.wot[turn].type = self.wot[turn].new_vertex_property("double")
        sentries = [m for m in self.members[turn]
                    if self.wot[turn].vertex(m).out_degree() > self.ySentries(len(self.members[turn]))]

        for v in self.wot[turn].vertices():
            if v in sentries:
                self.wot[turn].type[v] = 10
            elif v in self.members[turn]:
                self.wot[turn].type[v] = 5
            else:
                self.wot[turn].type[v] = 0
        ebet = betweenness(self.wot[turn])[1]
        graph_draw(self.wot[turn], pos=pos, vertex_size=self.wot[turn].type,
                   vertex_fill_color=self.wot[turn].type, vorder=self.wot[turn].type,
                    edge_color = ebet, # some curvy edges
                    output = outpath + "turn {0}.png".format(turn))

    def display_graphs(self):
        fig, ax_f = plt.subplots()
        nb_members = [len(m) for m in self.members]
        nb_identities = [len(i) for i in self.identities]

        ax_f.plot(nb_members, color='blue')
        ax_f.plot(nb_identities, color='green')

        ax_f.set_ylim(-5, max(max(nb_members), max(nb_identities)) + 5)
        ax_f.set_xlim(-5, self.turn + 5)