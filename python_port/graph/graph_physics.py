import math
import numpy as np

class GraphPhysics:
    def __init__(self, nodes, edges):
        self.nodes = nodes
        self.edges = edges
        self.alpha = 1.0
        self.max_delta = 0.0
        self.has_spring_energy = True
        self.W = 1000
        self.H = 1000
        self.communities = None

        self.n_nodes = len(self.nodes)
        if self.n_nodes > 0:
            self.x = np.array([n.get('x', 0) for n in self.nodes], dtype=np.float32)
            self.y = np.array([n.get('y', 0) for n in self.nodes], dtype=np.float32)
            self.vx = np.array([n.get('vx', 0) for n in self.nodes], dtype=np.float32)
            self.vy = np.array([n.get('vy', 0) for n in self.nodes], dtype=np.float32)

            self.pinned = np.array([n.get('pinned', False) for n in self.nodes], dtype=bool)
            self.hidden = np.array([n.get('hidden', False) for n in self.nodes], dtype=bool)
            self.orphan = np.array([n.get('orphan', False) for n in self.nodes], dtype=bool)
            self.radii = np.array([n.get('_radius', 10) * n.get('_revealScale', 1) + 8 for n in self.nodes], dtype=np.float32)

            self.movable = ~(self.pinned | self.hidden | self.orphan)

            if len(self.edges) > 0:
                edge_from = np.array([e['from'] for e in self.edges], dtype=np.int32)
                edge_to = np.array([e['to'] for e in self.edges], dtype=np.int32)
                valid_edges = ~(self.hidden[edge_from] | self.hidden[edge_to])
                self.e_from = edge_from[valid_edges]
                self.e_to = edge_to[valid_edges]
            else:
                self.e_from = np.array([], dtype=np.int32)
                self.e_to = np.array([], dtype=np.int32)

            self.comm_indices = {}
            self.comm_centers_x = {}
            self.comm_centers_y = {}
            self.update_comm_indices()

    def update_comm_indices(self):
        if not self.communities:
            return
        for comm_id, cm in self.communities.items():
            if len(cm['members']) < 2:
                continue
            idx = [self.nodes.index(n) for n in cm['members'] if not (n.get('pinned') or n.get('hidden') or n.get('orphan'))]
            self.comm_indices[comm_id] = np.array(idx, dtype=np.int32)

    def simulate(self, steps=1, tag_pairs=None, shared_neighbor_pairs=None, update_community_centroids_fn=None):
        if self.n_nodes == 0: return

        VELOCITY_DECAY = 0.4
        MAX_DISP = 30.0
        GLOBAL_GRAVITY = 0.0003
        hub_cluster_mul = 1.0
        ideal_dist = 60.0

        for _ in range(steps):
            if self.alpha < 0.001:
                break

            # Spring forces
            if len(self.e_from) > 0:
                ddx = self.x[self.e_to] - self.x[self.e_from]
                ddy = self.y[self.e_to] - self.y[self.e_from]
                dist_sq = ddx*ddx + ddy*ddy

                # Avoid sqrt on non-interacting edges, and zero division
                mask = dist_sq >= ideal_dist*ideal_dist
                if np.any(mask):
                    dist = np.sqrt(dist_sq[mask])
                    force = np.log(dist / ideal_dist) * self.alpha * 2

                    fx = ddx[mask] / dist * force
                    fy = ddy[mask] / dist * force

                    np.add.at(self.vx, self.e_from[mask], fx)
                    np.add.at(self.vy, self.e_from[mask], fy)
                    np.subtract.at(self.vx, self.e_to[mask], fx)
                    np.subtract.at(self.vy, self.e_to[mask], fy)

            # Community force
            if self.communities and len(self.communities) > 1 and update_community_centroids_fn:
                update_community_centroids_fn(self.communities)
                cluster_strength = 0.02 * hub_cluster_mul * self.alpha
                for comm_id, cm in self.communities.items():
                    idx = self.comm_indices.get(comm_id)
                    if idx is not None and len(idx) > 0:
                        self.vx[idx] += (cm['cx'] - self.x[idx]) * cluster_strength
                        self.vy[idx] += (cm['cy'] - self.y[idx]) * cluster_strength

            # Gravity
            self.vx[self.movable] -= self.x[self.movable] * GLOBAL_GRAVITY * self.alpha
            self.vy[self.movable] -= self.y[self.movable] * GLOBAL_GRAVITY * self.alpha

            # Friction & Clamp
            self.vx[self.movable] *= (1 - VELOCITY_DECAY)
            self.vy[self.movable] *= (1 - VELOCITY_DECAY)

            speed = np.sqrt(self.vx[self.movable]**2 + self.vy[self.movable]**2)
            clamp_mask = speed > MAX_DISP

            if np.any(clamp_mask):
                clamped_speed = speed[clamp_mask]
                factor = MAX_DISP / clamped_speed
                movable_indices = np.where(self.movable)[0]
                clamped_indices = movable_indices[clamp_mask]
                self.vx[clamped_indices] *= factor
                self.vy[clamped_indices] *= factor

            self.x[self.movable] += self.vx[self.movable]
            self.y[self.movable] += self.vy[self.movable]

            bound = max(self.W, self.H) * 3
            np.clip(self.x[self.movable], -bound, bound, out=self.x[self.movable])
            np.clip(self.y[self.movable], -bound, bound, out=self.y[self.movable])

            total_speed = np.sum(np.sqrt(self.vx[self.movable]**2 + self.vy[self.movable]**2))
            if len(self.vx[self.movable]) > 0:
                self.max_delta = max(np.max(np.abs(self.vx[self.movable])), np.max(np.abs(self.vy[self.movable])))
            else:
                self.max_delta = 0

            self.has_spring_energy = total_speed > max(0.1, self.n_nodes * 0.005)

        # Write back to nodes (in JS, this happens implicitly on reference, in python we must copy)
        for i, n in enumerate(self.nodes):
            n['x'] = float(self.x[i])
            n['y'] = float(self.y[i])
            n['vx'] = float(self.vx[i])
            n['vy'] = float(self.vy[i])
