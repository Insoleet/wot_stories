from wot_stories.wot import WoT, plt
from random import randint
from networkx import shortest_path_length
import networkx as nx
from itertools import product
import numpy as np
import matplotlib.pyplot as plt

if __name__ == '__main__':
    NMAX = 1000000000
    wot = WoT(sig_period=0, sig_stock=45, sig_validity=4, sig_qty=3, xpercent=0.9, steps_max=4)
    individuals = [0, 1, 2, 3]
    init_links = list(product(individuals, individuals))
    wot.initialize([0, 1, 2, 3], init_links)
    certs = {}
    for i in individuals:
        certs[i] = 0
    nb_members = [3]
    nb_identities = [3]

    for i in range(0, 4*40):
        print("Turn {0}".format(i))
        lengths = shortest_path_length(wot.wot.to_undirected())
        for id in individuals:
            if id in wot.history and i < wot.history[id][0] + 80:
                if id in wot.wot.nodes():
                    if 0 <= certs[id] < 45:
                        if certs[id] % 3 == 0 and id in wot.members:
                            new_id = randint(0, NMAX)
                            wot.add_identity(new_id)
                            wot.add_link(id, new_id)
                            individuals.append(new_id)
                            certs[new_id] = 0
                            certs[id] += 1
                        else:
                            del lengths[id][id]
                            current_lengths = lengths[id]
                            len_array = np.array(list(current_lengths.values()))
                            members_array = [1 if k in wot.members else 100 for k in current_lengths.keys()]
                            pond = (len_array * members_array) / np.sum(len_array * members_array)
                            new_link_id = np.random.choice(list(current_lengths.keys()), p=pond)
                            wot.add_link(id, new_link_id)
                            certs[id] += 1
        wot.next_turn()
        nb_members.append(len(wot.members))
        nb_identities.append(len(individuals))

    fig, ax_f = plt.subplots()
    ax_c = ax_f.twinx()
    ax_f.plot(nb_members)
    ax_f.plot(nb_identities)

    ax_f.set_ylim(-5, max(max(nb_members), max(nb_identities)))
    ax_f.set_xlim(-5, 4*40+5)
    plt.show()
    #nx.draw_graphviz(wot.wot, prog="naeto")
    #wot.draw()
    #plt.savefig('perfect_shell.png', dpi=192, facecolor='w', edgecolor='w',
    #            orientation='portrait')
    #plt.show()