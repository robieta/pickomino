from collections import Counter
import itertools as it
import timeit

die = ((1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (5, 1))
nside = len(die)
face_to_ind = {die[I1]:I1 for I1 in range(nside)}

class DieStats:
    def __init__(self):
        self.distribution = []

    def get_dist(self, n):
        while len(self.distribution) <= n:
            self.distribution.append(None)

        roll_counts = Counter()
        if self.distribution[n] is None:
            total = 0
            for roll in it.product(*[die for _ in range(n)]):
                roll_counts[tuple(sorted(roll))] += 1.
                total += 1

            for key in roll_counts:
                roll_counts[key] /= total

            self.distribution[n] = roll_counts

        return self.distribution[n]

class DecisionNode:
    def __init__(self, p=None, dice_state=None, current_totals=None, parent=None, state_master=None, shared_stats=None, die_stats=None):
        self.connection_p = p   #  Probability of reaching this state given the spawning state node
        self.dice_state = dice_state
        self.current_totals = current_totals

        self.parent = parent
        self.children = []

        self.state_master = state_master
        self.shared_stats = shared_stats

        self.die_stats = die_stats

        assert self.connection_p is not None
        assert self.dice_state is not None
        assert self.current_totals is not None
        assert self.parent is not None
        assert self.state_master is not None
        assert self.die_stats is not None

        self.rolled_dice = set(self.dice_state)

        self.initialize_children()

    def get_legal_play(self):
        return self.rolled_dice.intersection([side for I1, side in enumerate(die) if self.current_totals[I1] == 0])

    def initialize_children(self):
        for play in self.get_legal_play():
            n_taken = self.dice_state.count(play)
            new_state = [ct for ct in self.current_totals]
            new_state[face_to_ind[play]] += n_taken
            new_n_dice = len(self.dice_state) - n_taken
            new_ID = (new_n_dice, tuple(new_state))
            if new_ID in self.state_master:
                self.children.append(self.state_master[new_ID])
            else:
                state_node = StateNode(n_dice=new_n_dice, current_totals=new_state, die_stats=self.die_stats,
                                       state_master=self.state_master, shared_stats=self.shared_stats)
                self.children.append(state_node)
                self.state_master[new_ID] = state_node
                self.shared_stats["n_state_nodes"] += 1
            self.children[-1].parents.append(self)


class StateNode:
    def __init__(self, n_dice, current_totals=None, parents=None, die_stats=None, state_master=None, shared_stats=None):
        self.parents = parents
        if self.parents is None:
            self.parents = []
        self.children = []

        self.state_master = state_master
        self.shared_stats = shared_stats
        assert self.state_master is not None

        self.n_dice = n_dice
        self.current_totals = current_totals
        if self.current_totals is None:
            self.current_totals = [0 for _ in range(nside)]

        # Insert node pointer into the master list of state nodes
        self.ID = (self.n_dice, tuple(self.current_totals))
        self.state_master[self.ID] = self

        self.children = []

        self.die_stats = die_stats
        assert self.die_stats is not None

        self.initalize_children()

        #===============================================================================================================
        #== Sniper Variables ===========================================================================================
        # ===============================================================================================================
        self.p_target = None

    def initalize_children(self):
        outcomes = self.die_stats.get_dist(self.n_dice)
        for state, p in outcomes.items():
            child = DecisionNode(p=p, dice_state=state, current_totals=self.current_totals, parent=self,
                                 state_master=self.state_master, shared_stats=self.shared_stats, die_stats=self.die_stats)
            self.children.append(child)
            self.shared_stats["n_decision_nodes"] += 1

    def depth(self):
        return nside - self.current_totals.count(0)

    def calculate_value(self):
        worms = sum([self.current_totals[I1] * die[I1][1] for I1 in range(nside)])
        worm = [1 if worms > 0 else 0][0]
        counts = sum([self.current_totals[I1] * die[I1][0] for I1 in range(nside)])
        return counts, worm

    def calculate_p_target(self, target, cache=None):
        if cache is None:
            cache = {}
        if self.calculate_value() == target:
            return 1.

        if self.ID in cache:
            return cache[self.ID]

        total_p = 0.
        for child in self.children:
            options = [0]
            for decision in child.children:
                options.append(child.connection_p * decision.calculate_p_target(target=target, cache=cache))
            total_p += max(options)

        cache[self.ID] = total_p
        return total_p

class BruteForceTree:
    def __init__(self, n_dice=8):
        st = timeit.default_timer()
        self.die_stats = DieStats()
        self.state_master = {}
        self.shared_stats = {
            "n_state_nodes": 0,
            "n_decision_nodes": 0,
        }
        self.head = StateNode(n_dice=n_dice, die_stats=self.die_stats, state_master=self.state_master,
                              shared_stats=self.shared_stats)

        self.states_by_level = [[] for _ in range(nside+1)]
        self.initalize_state_levels()

        self.init_time = timeit.default_timer() - st

        print(self.init_time)
        print(self.shared_stats)

    def initalize_state_levels(self):
        for ID, node in self.state_master.items():
            self.states_by_level[node.depth()].append(node)

    def snipe_target(self, target):
        return self.head.calculate_p_target(target=(target,1))


if __name__ == "__main__":
    bf_tree = BruteForceTree()

    x = []
    y = []
    for i1 in range(21, 41+1):
        x.append(i1)
        y.append(bf_tree.snipe_target(i1))
        print(x[-1], y[-1])

    from matplotlib import pyplot as plt
    plt.plot(x, y, ".:k")
    plt.show()

