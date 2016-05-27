from wot_stories.fast_wot import WoT, plt
from random import randint
import numpy as np
import logging
from graph_tool.all import *
import asyncio

NB_TURN = 12 * 4

#@profile
async def run():
    global NB_TURN
    wot = WoT(sig_period=0, sig_stock=24, sig_validity=4, sig_qty=0, xpercent=0.9, steps_max=3)
    wot.initialize(4)
    magnet = {}
    for i in wot.identities[0]:
        magnet[i] = np.random.laplace()
    print(magnet)

    for i in range(0, NB_TURN):
        #need_certs_array = np.array([max(1, 5 - wot.wot[wot.turn].vertex(v).in_degree())
        #                             for v in wot.identities[wot.turn]])
        #members_array = np.array([1 if k in wot.members[wot.turn] else 1
        #                          for k in wot.identities[wot.turn]])
        distance = shortest_distance(wot.wot[wot.turn], directed=False, max_dist=0)
        for vertex in wot.members[wot.turn]:
            if vertex in wot.history and i < wot.history[vertex][0] + 80 * 4:
                if 0 <= wot.wot[wot.turn].vertex(vertex).out_degree() < 45:
                    nearest_array = 1 / (1 + 7*np.array(distance[vertex]))
                    pond = (nearest_array) / np.sum(nearest_array)
                    nb_members = len(wot.members[wot.turn])
                    nb_identities = len(wot.identities[wot.turn])
                    #pond = (100*nearest_array * members_array * 0.5*need_certs_array) / \
                    #       np.sum(100*nearest_array * members_array * 0.5*need_certs_array)
                    if nb_members / nb_identities > 0.5 and -0.3 < magnet[vertex] < 0.3:
                        new_id = wot.add_identity()
                        wot.add_link(vertex, new_id)
                        magnet[new_id] = np.random.laplace()
                        for i in range(0, min(2, int(len(wot.identities)/2))):
                            new_link_id = np.random.choice(wot.identities[wot.turn], p=pond)
                            wot.add_link(vertex, new_link_id)
                    else:
                        for i in range(0, min(3, int(len(wot.identities)/2))):
                            new_link_id = np.random.choice(wot.identities[wot.turn], p=pond)
                            wot.add_link(vertex, new_link_id)

        print('\r[{0}{1}] {2:10.2f}% - Turn {3} : {4} members, {5} identities'.format('#' * int(wot.turn / NB_TURN * 10),
                                       ' ' * (10 - (int(wot.turn / NB_TURN * 10))),
                                       (wot.turn / NB_TURN) * 100,
                                        wot.turn,
                                        len(wot.members[wot.turn]),
                                        len(wot.identities[wot.turn])))
        await wot.next_turn()
        if len(wot.members[wot.turn]) == 0:
            print("No more members. Community died")
            break
    wot.end()
    wot.save('perfect')

def display():
    global NB_TURN
    wot = WoT(sig_period=0, sig_stock=45, sig_validity=12, sig_qty=3, xpercent=0.9, steps_max=0)
    print("load")
    wot.load('perfect')
    wot.display_graphs()
    maxlen = max([len(wot.members[i]) for i in range(0, NB_TURN)])
    turn = 0
    for i in range(0, NB_TURN):
        if len(wot.members[i]) == maxlen:
            turn = i

    for i in range(turn-5, turn):
        wot.draw_turn(i, "perfect")
        wot.draw_blockmodel(i, "perfect")
    #wot.draw()
    plt.show()

async def main(loop):
    await run()
    display()

if __name__ == '__main__':

    logging.basicConfig(format='%(levelname)s:%(module)s:%(funcName)s:%(message)s',
                        level=logging.INFO)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
    loop.close()
