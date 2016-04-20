from wot_stories.wot import WoT, plt
import json
import sqlite3


def parse_block(wot, block_row, id_col, cert_col):
    certifications = []
    identities = []

    if block_row[id_col]:
        id_str = "{{\"i\": {0}}}".format(block_row[id_col])
        idties = json.loads(id_str)
        for i in idties['i']:
            isplit = i.split(':')
            identities.append(isplit[0])

    if block_row[cert_col]:
        cert_str = "{{\"i\": {0}}}".format(block_row[cert_col])
        certs = json.loads(cert_str)
        for c in certs['i']:
            csplit = c.split(':')
            certifications.append((csplit[0], csplit[1]))

    return identities, certifications

def from_sqlite(wot, filepath):
    conn = sqlite3.connect(filepath)

    cursor = conn.cursor()

    cursor.execute('SELECT * FROM block WHERE fork=0')
    columns = [d[0] for d in cursor.description]
    id_col = columns.index('identities')
    cert_col = columns.index('certifications')

    block_zero = cursor.fetchone()
    identities, certs = parse_block(wot, block_zero, id_col, cert_col)
    wot.initialize(identities, certs)
    fetching = True
    count = 0
    while fetching:
        blocks = cursor.fetchmany(50)
        count += 50
        for b in blocks:
            identities, certs = parse_block(wot, b, id_col, cert_col)
            for i in identities:
                wot.add_identity(i)

            for c in certs:
                wot.add_link(c[0], c[1])

            wot.next_turn()
        if len(blocks) < 50:
            fetching = False

    conn.close()

if __name__ == '__main__':
    wot = WoT(sig_period=0, sig_stock=100, sig_window=0, sig_validity=10800, sig_qty=3, xpercent=1, steps_max=3)
    from_sqlite(wot, 'metabrouzouf.db')
    wot.draw(0.01)
    plt.savefig('out.png', dpi=192, facecolor='w', edgecolor='w',
        orientation='portrait')
    plt.show()