import bisect
from collections import Counter
import itertools as it
import timeit

die = ((1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (5, 1))
nside = len(die)
face_to_ind = {die[I1]: I1 for I1 in range(nside)}

tile_costs = ((21, 1), (22, 1), (23, 1), (24, 1), (25, 1), (26, 1), (27, 1), (28, 1),
              (29, 1), (30, 1), (31, 1), (32, 1), (33, 1), (34, 1), (35, 1), (36, 1))

tile_values = (1, ) * 4 + (2, ) * 4 + (3, ) * 4 + (4, ) * 4
max_points = max(tile_values)

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
        self.child_labels = []

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
            self.child_labels.append(str(play))

    def dice_state_counts(self):
        counts = [0 for _ in range(nside)]
        for die in self.dice_state:
            counts[face_to_ind[die]] += 1
        return tuple(counts)

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
        self.ID2 = tuple(self.current_totals)
        self.state_master[self.ID] = self

        self.children = []

        self.die_stats = die_stats
        assert self.die_stats is not None

        self.initalize_children()

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

    def calculate_strategy(self, mode, input_val, cache=None, decision_cache=None):
        # ==============================================================================================================
        # == Input Modes ===============================================================================================
        # ==============================================================================================================
        #   1:  Sniper - Try to hit target value.
        #           input_val = target
        #   2:  Threshold - Try to hit at or above a set threshold.
        #           input_val = threshold
        #   3:  Expectation - Maximize expectation value of points
        #           input_val = cost of "bust"
        if cache is None:
            cache = {}

        if self.ID2 in cache:
            return cache[self.ID2]

        if decision_cache is None:
            decision_cache = {}

        pass_value = 0.
        bust_cost = 0.
        if mode == 3:
            bust_cost = input_val
            pass_value = input_val
        current_value = self.calculate_value()
        if mode == 1 and current_value[1] > 0 and current_value == input_val:
            return 1.
        elif mode == 2 and current_value[1] > 0 and current_value >= input_val:
            return 1.
        elif mode == 3 and current_value[1] > 0:
            best_ind = bisect.bisect_right(tile_costs, (current_value[0], max_points))
            if best_ind > 0:
                pass_value = tile_values[best_ind - 1]

        total_p = 0.
        choice = ""
        decision_by_outcome = {}
        for child in self.children:
            options = [(bust_cost, "bust")]
            for I1, decision in enumerate(child.children):
                options.append((decision.calculate_strategy(mode=mode, input_val=input_val,
                                                           cache=cache, decision_cache=decision_cache), child.child_labels[I1]))
            choice = max(options)
            total_p += child.connection_p * choice[0]
            decision_by_outcome[child.dice_state_counts()] = choice[1]

        best_outcome = max([total_p, pass_value])
        cache[self.ID2] = best_outcome
        if total_p >= pass_value:
            decision_cache[self.ID2] = (decision_by_outcome, best_outcome)
        else:
            decision_cache[self.ID2] = ("pass", best_outcome)
        return best_outcome

class BruteForceTree:
    def __init__(self, n_dice=8):
        st = timeit.default_timer()
        self.n_dice = n_dice
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
        decision_cache = {}
        return self.head.calculate_strategy(mode=1, input_val=(target, 1), decision_cache=decision_cache)

    def maximize_expectation(self, bust_cost):
        decision_cache = {}
        outcome = self.head.calculate_strategy(mode=3, input_val=bust_cost, decision_cache=decision_cache)
        return outcome, decision_cache

    def get_strategy(self):
        decision_caches = {}
        try:
            while True:

                run = input("Run turn? ")
                if run.lower() not in ("y", "yes"):
                    break
                bust_cost = input("  Cost on bust: ")
                bust_cost = int(bust_cost)
                if bust_cost not in decision_caches:
                    _, decision_caches[bust_cost] = self.maximize_expectation(bust_cost)

                current_counts = [0 for _ in range(nside)]
                while True:
                    cc = tuple(current_counts)
                    if decision_caches[bust_cost][cc] == "pass":
                        print("You should pass")
                        break

                    roll_counts = input("Roll counts: ")
                    roll_counts = tuple(int(m) for m in roll_counts.split())

                    expectation = decision_caches[bust_cost][cc][1]
                    choice = decision_caches[bust_cost][cc][0][roll_counts]
                    print("Expectation: {}".format(expectation))
                    print("Engine choice: {}".format(choice))


        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    bf_tree = BruteForceTree()
    bf_tree.get_strategy()

