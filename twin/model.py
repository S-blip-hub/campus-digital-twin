"""Agent-based weekday simulation of campus movement.

Each resident agent lives in a hall, belongs to a cohort and builds a daily
activity plan from its cohort timetable plus stochastic choices (attendance,
library, sports, market). Plans are resolved on a 15-minute grid. Every change
of location becomes a trip routed on the shortest road path, which gives road
usage by hour; the location grid gives building occupancy and time use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import networkx as nx
import numpy as np
import pandas as pd

from . import schedules as S
from .layers import HALLS, KIND, load_network


@dataclass(frozen=True)
class Agent:
    id: int
    hall: str
    cohort: str
    cycles: bool
    sporty: bool


@dataclass
class DayResult:
    day: str
    location: np.ndarray   # (agents, steps) index into Twin.places
    activity: np.ndarray   # (agents, steps) index into ACTIVITIES
    trips: pd.DataFrame


class CampusTwin:
    """Holds the network, the population and the simulation results."""

    def __init__(self, scale: float = 1.0, seed: int = 7):
        self.graph = load_network()
        self.rng = np.random.default_rng(seed)
        self.places: List[str] = [n for n, d in self.graph.nodes(data=True) if d["kind"] != "junction"]
        self.place_index = {p: i for i, p in enumerate(self.places)}
        self.paths: Dict[str, Dict[str, List[str]]] = dict(nx.all_pairs_dijkstra_path(self.graph, weight="length"))
        self.dist: Dict[str, Dict[str, float]] = dict(nx.all_pairs_dijkstra_path_length(self.graph, weight="length"))
        self.agents = self._population(scale)
        self.results: Dict[str, DayResult] = {}

    # ------------------------------------------------------------------ population
    def _population(self, scale: float) -> List[Agent]:
        agents, cohorts, shares = [], list(S.COHORT_SHARE), list(S.COHORT_SHARE.values())
        for hall, (_, _, cap) in HALLS.items():
            n = int(round(cap * scale))
            picks = self.rng.choice(cohorts, size=n, p=shares)
            cycles = self.rng.random(n) < S.CYCLE_SHARE
            sporty = self.rng.random(n) < 0.5
            for c, cy, sp in zip(picks, cycles, sporty):
                agents.append(Agent(len(agents), hall, str(c), bool(cy), bool(sp)))
        return agents

    # ------------------------------------------------------------------ plans
    def _plan(self, agent: Agent, day: str, rng: np.random.Generator):
        loc = [agent.hall] * S.N_STEPS
        act = ["home"] * S.N_STEPS

        def put(h0: float, h1: float, place: str, activity: str, only_if_free: bool = False):
            for s in range(max(0, S.step_of(h0)), min(S.N_STEPS, S.step_of(h1))):
                if only_if_free and act[s] != "home":
                    continue
                loc[s], act[s] = place, activity

        slots = [(h, h + d, b) for h, d, b in S.TIMETABLE[agent.cohort][day] if rng.random() < S.ATTENDANCE]
        for h0, h1, b in slots:
            put(h0, h1, b, "class")

        # free time between attended classes
        for (_, end, prev_b), (start, _, _) in zip(slots, slots[1:]):
            gap = start - end
            covers_lunch = end <= 13.0 and start >= 14.0
            if covers_lunch:
                continue                      # goes back to the hall for lunch
            if gap <= 1.0:
                stay = "Central Library" if rng.random() < 0.5 else prev_b
                put(end, start, stay, "library" if stay == "Central Library" else "study")
            elif rng.random() < S.LIBRARY_GAP:
                put(end, start, "Central Library", "library")

        for earliest, latest, dur in S.MEALS:
            start = earliest + S.STEP_H * rng.integers(0, int((latest - earliest) / S.STEP_H) + 1)
            put(start, start + dur, agent.hall, "meal", only_if_free=True)

        p_sport = S.SPORTS_EVENING * (1.6 if agent.sporty else 0.4)
        if rng.random() < p_sport:
            put(17.5, 19.0, "Sports Complex" if rng.random() < 0.6 else "Central Lawn", "sports", only_if_free=True)

        if rng.random() < S.HEALTH_VISIT:
            start = 9.0 + S.STEP_H * rng.integers(0, 29)
            put(start, start + 0.75, "Health Centre", "health", only_if_free=True)

        r = rng.random()
        if r < S.LIBRARY_NIGHT[agent.cohort]:
            put(21.0, 23.0, "Central Library", "library", only_if_free=True)
        elif r < S.LIBRARY_NIGHT[agent.cohort] + S.MARKET_NIGHT:
            put(21.0, 22.0, "Market" if rng.random() < 0.6 else "Dining Centre", "market", only_if_free=True)
        return loc, act

    # ------------------------------------------------------------------ simulation
    def run_day(self, day: str) -> DayResult:
        rng = np.random.default_rng([S.DAYS.index(day), 1234])
        n = len(self.agents)
        loc_arr = np.zeros((n, S.N_STEPS), dtype=np.int16)
        act_arr = np.zeros((n, S.N_STEPS), dtype=np.int8)
        act_index = {a: i for i, a in enumerate(S.ACTIVITIES)}
        trips = []
        for a in self.agents:
            loc, act = self._plan(a, day, rng)
            speed = S.CYCLE_SPEED_MS if a.cycles else S.WALK_SPEED_MS
            for s in range(1, S.N_STEPS):
                if loc[s] != loc[s - 1]:
                    d = self.dist[loc[s - 1]][loc[s]]
                    minutes = d / speed / 60.0
                    if minutes >= 7.5:
                        act[s - 1] = "travel"
                    arrive_min = S.hour_of(s) * 60
                    trips.append((a.id, day, arrive_min - minutes, loc[s - 1], loc[s], act[s],
                                  "cycle" if a.cycles else "walk", d, minutes))
            loc_arr[a.id] = [self.place_index[p] for p in loc]
            act_arr[a.id] = [act_index[x] for x in act]
        cols = ["agent", "day", "depart_min", "origin", "destination", "purpose", "mode", "distance_m", "minutes"]
        res = DayResult(day, loc_arr, act_arr, pd.DataFrame(trips, columns=cols))
        self.results[day] = res
        return res

    def run_week(self) -> "CampusTwin":
        for d in S.DAYS:
            self.run_day(d)
        return self

    # ------------------------------------------------------------------ outputs
    def occupancy(self) -> pd.DataFrame:
        """People present in each building at each step (long format)."""
        rows = []
        for day, r in self.results.items():
            for s in range(S.N_STEPS):
                counts = np.bincount(r.location[:, s], minlength=len(self.places))
                rows += [(day, s, S.clock(s), p, KIND[p], int(c)) for p, c in zip(self.places, counts)]
        return pd.DataFrame(rows, columns=["day", "step", "time", "place", "kind", "people"])

    def time_use(self) -> pd.DataFrame:
        """Number of agents in each activity at each step."""
        rows = []
        for day, r in self.results.items():
            for s in range(S.N_STEPS):
                counts = np.bincount(r.activity[:, s], minlength=len(S.ACTIVITIES))
                rows += [(day, s, S.clock(s), a, int(c)) for a, c in zip(S.ACTIVITIES, counts)]
        return pd.DataFrame(rows, columns=["day", "step", "time", "activity", "agents"])

    def trips(self) -> pd.DataFrame:
        return pd.concat([r.trips for r in self.results.values()], ignore_index=True)

    def road_usage(self) -> pd.DataFrame:
        """Trips crossing each road segment per day and departure hour."""
        t = self.trips()
        t["hour"] = (t["depart_min"] // 60).astype(int)
        grouped = t.groupby(["day", "hour", "origin", "destination"]).size().reset_index(name="n")
        acc: Dict[tuple, int] = {}
        for day, hour, o, dst, n in grouped.itertuples(index=False):
            path = self.paths[o][dst]
            for u, v in zip(path, path[1:]):
                key = (day, hour, self.graph.edges[u, v]["id"])
                acc[key] = acc.get(key, 0) + int(n)
        out = pd.DataFrame([(*k, n) for k, n in acc.items()], columns=["day", "hour", "segment", "trips"])
        return out.sort_values(["day", "hour", "trips"], ascending=[True, True, False], ignore_index=True)
