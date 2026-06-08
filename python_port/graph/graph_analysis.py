import numpy as np

def compute_louvain_communities(nodes, edges):
    """
    Computes Louvain communities for the graph.
    Modifies the 'community' attribute on each node in 'nodes' in-place.
    """
    n = len(nodes)
    if n == 0:
        return {}

    # Build adjacency list with weights
    adj = [[] for _ in range(n)]
    m2 = 0.0 # 2 * total weight
    for e in edges:
        from_idx, to_idx = e['from'], e['to']
        w = e.get('weight', 1.0)
        adj[from_idx].append({'node': to_idx, 'weight': w})
        adj[to_idx].append({'node': from_idx, 'weight': w})
        m2 += 2.0 * w

    if m2 == 0:
        for i, node in enumerate(nodes):
            node['community'] = i
        return {}

    # k[i] = degree (sum of weights) of node i
    k = np.zeros(n, dtype=np.float64)
    for i in range(n):
        k[i] = sum(nb['weight'] for nb in adj[i])

    # Init communities
    comm = np.arange(n, dtype=np.int32)

    sigma_in = np.zeros(n, dtype=np.float64)
    sigma_tot = k.copy()

    MAX_ITERATIONS = 20
    order = np.arange(n, dtype=np.int32)

    for _ in range(MAX_ITERATIONS):
        moved = False
        np.random.shuffle(order)

        for i in order:
            if nodes[i].get('orphan', False):
                continue

            ci = comm[i]

            neighbor_comms = {}
            ki_in = 0.0
            for nb in adj[i]:
                cj = comm[nb['node']]
                w = nb['weight']
                neighbor_comms[cj] = neighbor_comms.get(cj, 0.0) + w
                if cj == ci:
                    ki_in += w

            # Detach
            sigma_in[ci] -= 2.0 * ki_in
            sigma_tot[ci] -= k[i]

            best_comm = ci
            best_delta = 0.0

            for cj, ki_cj in neighbor_comms.items():
                delta = ki_cj - sigma_tot[cj] * k[i] / m2
                if delta > best_delta:
                    best_delta = delta
                    best_comm = cj

            comm[i] = best_comm
            ki_best = neighbor_comms.get(best_comm, 0.0)
            sigma_in[best_comm] += 2.0 * ki_best
            sigma_tot[best_comm] += k[i]

            if best_comm != ci:
                moved = True

        if not moved:
            break

    # Compact
    unique_comms = np.unique(comm)
    comm_map = {c: idx for idx, c in enumerate(unique_comms)}

    for i in range(n):
        nodes[i]['community'] = comm_map[comm[i]]

    return build_community_meta(nodes)


def build_community_meta(nodes):
    COMMUNITY_PALETTE = [
        '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231',
        '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe',
        '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000',
        '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080',
        '#ffffff', '#000000'
    ]
    meta = {}
    for n in nodes:
        c = n.get('community')
        if c is None:
            continue
        if c not in meta:
            meta[c] = {
                'id': c,
                'members': [],
                'color': COMMUNITY_PALETTE[c % len(COMMUNITY_PALETTE)],
                'label': '',
                'cx': 0.0,
                'cy': 0.0
            }
        meta[c]['members'].append(n)

    for c, cm in meta.items():
        tag_counts = {}
        for n in cm['members']:
            for t in n.get('tags', []):
                if t.lower() == 'lorebook':
                    continue
                tag_counts[t] = tag_counts.get(t, 0) + 1

        best_tag = ''
        best_count = 0
        for t, count in tag_counts.items():
            if count > best_count:
                best_tag = t
                best_count = count
        cm['label'] = best_tag if best_tag else f"Cluster {cm['id'] + 1}"

    return meta


def update_community_centroids(communities):
    if not communities:
        return
    for c, cm in communities.items():
        sx, sy, count = 0.0, 0.0, 0
        for n in cm['members']:
            if n.get('hidden', False) or n.get('orphan', False):
                continue
            sx += n.get('x', 0)
            sy += n.get('y', 0)
            count += 1
        if count > 0:
            cm['cx'] = sx / count
            cm['cy'] = sy / count


def compute_gap_analysis(nodes, edges, communities):
    edge_count_by_node = {}
    for e in edges:
        edge_count_by_node[e['from']] = edge_count_by_node.get(e['from'], 0) + 1
        edge_count_by_node[e['to']] = edge_count_by_node.get(e['to'], 0) + 1

    orphans = []
    for n in nodes:
        if edge_count_by_node.get(n['id'], 0) == 0:
            orphans.append(n['id'])

    bridges = []
    if communities and len(communities) > 1:
        cross_counts = {}
        cross_edge_idxs = {}
        for i, e in enumerate(edges):
            ca = nodes[e['from']].get('community')
            cb = nodes[e['to']].get('community')
            if ca is None or cb is None or ca == cb:
                continue
            key = (min(ca, cb), max(ca, cb))
            cross_counts[key] = cross_counts.get(key, 0) + 1
            cross_edge_idxs.setdefault(key, []).append(i)

        for key, count in cross_counts.items():
            if count == 1:
                bridges.extend(cross_edge_idxs[key])

    type_imbalance = {}
    if communities:
        for cid, cm in communities.items():
            counts = {'regular': 0, 'constant': 0, 'seed': 0, 'bootstrap': 0}
            for n in cm['members']:
                counts[n.get('type', 'regular')] += 1
            type_imbalance[cid] = {'label': cm['label'], 'total': len(cm['members']), **counts}

    missing_connections = []
    edge_set = set()
    for e in edges:
        edge_set.add((min(e['from'], e['to']), max(e['from'], e['to'])))

    candidates = [n for n in nodes if not n.get('orphan') and not n.get('hidden')]
    # Mocking vault index check for the port as it's not present here

    return {
        'orphans': orphans,
        'bridges': bridges,
        'typeImbalance': type_imbalance,
        'missingConnections': missing_connections
    }
