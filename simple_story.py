from wot_stories.wot import WoT

if __name__ == '__main__':
    wot = WoT(sig_period=2, sig_stock=5, sig_window=2, sig_validity=3, sig_qty=2, xpercent=0.9, steps_max=2)
    wot.initialize(['A', 'B', 'C'],
                   [('A', 'B'),
                    ('A', 'C'),
                    ('B', 'A'),
                    ('B', 'C'),
                    ('C', 'A'),
                    ('C', 'B')])
    wot.draw()
    wot.prepare_next_turn()
    wot.add_identity('D')
    wot.add_link('A', 'D')
    wot.add_link('B', 'D')
    wot.next_turn()
    wot.next_turn()
    wot.next_turn()
    wot.next_turn()
    wot.draw()