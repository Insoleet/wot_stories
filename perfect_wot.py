from wot_stories.fast_wot import WoT, plt
from random import randint
import numpy as np

if __name__ == '__main__':
    NMAX = 1000000000
    wot = WoT(sig_period=0, sig_stock=45, sig_validity=12, sig_qty=3, xpercent=0.9, steps_max=4)
    wot.initialize(4)
    individuals = [int(v) for v in wot.wot.vertices()]
    certs = {}
    for i in individuals:
        certs[i] = 0
    nb_members = [3]
    nb_identities = [3]

    for i in range(0, 50):
        print("Turn {0}".format(i))
        next_individuals = individuals.copy()
        for vertex in individuals:
            others = individuals.copy()
            del others[vertex]
            if vertex in wot.history and i < wot.history[vertex][0] + 80*12:
                if vertex in wot.wot.vertices() and vertex in wot.members:
                    if 0 <= certs[vertex] < 45:
                        if certs[vertex] % 9 == 0:
                            new_id = wot.add_identity()
                            wot.add_link(vertex, new_id)
                            individuals.append(new_id)
                            certs[new_id] = 0
                            certs[vertex] += 1
                        else:
                            members_array = np.array([1 if k in wot.members else 2 for k in others])
                            neighbours_array = np.array([2 if k in wot.wot.vertex(vertex).all_neighbours()
                                                else 1 for k in others])
                            need_certs_array = np.array([max(1, 5 - wot.next_wot.vertex(v).in_degree())
                                                     for v in others])
                            pond = (neighbours_array * members_array * need_certs_array) / \
                                   np.sum(neighbours_array * members_array * need_certs_array)
                            new_link_id = np.random.choice(others, p=pond)
                            wot.add_link(vertex, new_link_id)
                            certs[vertex] += 1
                    else:
                        print("No new cert for {0}".format(vertex))
        wot.next_turn()
        nb_members.append(len(wot.members))
        nb_identities.append(len(individuals))

    fig, ax_f = plt.subplots()
    ax_c = ax_f.twinx()
    ax_f.plot(nb_members)
    ax_f.plot(nb_identities)

    ax_f.set_ylim(-5, max(max(nb_members), max(nb_identities)))
    ax_f.set_xlim(-5, 4*40+5)
    wot.draw()
    wot.draw_turn(30)
    #plt.savefig('perfect_shell.png', dpi=192, facecolor='w', edgecolor='w',
    #            orientation='portrait')
    plt.show()