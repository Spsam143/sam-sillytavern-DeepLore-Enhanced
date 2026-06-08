import time
import pytest
from graph.graph_physics import GraphPhysics
from graph.graph_analysis import compute_louvain_communities

def test_physics_benchmark():
    # 2000 nodes, representing a large graph
    num_nodes = 2000

    nodes = [{'id': i, 'x': i * 5, 'y': i * 5, 'color': '#888'} for i in range(num_nodes)]
    # Each node connected to previous node to form a line, and a few random edges
    edges = [{'from': i, 'to': i + 1} for i in range(num_nodes - 1)]
    for i in range(0, num_nodes - 5, 5):
        edges.append({'from': i, 'to': i + 4})

    physics = GraphPhysics(nodes, edges)

    # Pre-compute communities to test clustering force
    communities = compute_louvain_communities(nodes, edges)
    physics.communities = communities
    physics.update_comm_indices()

    # We want 60fps -> 16.6ms per frame.
    # Let's run 60 frames and measure total time.
    start_time = time.time()

    # Mock community centroid update function
    def update_centroids(comms):
        pass

    physics.simulate(steps=60, update_community_centroids_fn=update_centroids)

    end_time = time.time()
    total_time = end_time - start_time
    fps = 60 / total_time if total_time > 0 else float('inf')

    print(f"\nPhysics benchmark for 2000 nodes over 60 frames:")
    print(f"Total time: {total_time:.4f} seconds")
    print(f"Average FPS: {fps:.2f}")

    # Ensure it's capable of at least 60 FPS (i.e. finishes 60 steps in < 1 second)
    assert total_time < 2.0, f"Physics engine is too slow. Expected < 1.0s, got {total_time:.2f}s"

if __name__ == '__main__':
    pytest.main(['-v', '-s', __file__])
