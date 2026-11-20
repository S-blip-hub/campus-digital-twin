import json

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from twin import LAYER_NAMES, CampusTwin, build_layers, load_network, places_table, write_layers
from twin import schedules as S
from twin.store import load_queries, run_queries, write_db


@pytest.fixture(scope="module")
def twin():
    return CampusTwin(scale=0.05, seed=3).run_week()


def test_six_layers_round_trip(tmp_path):
    layers = build_layers()
    assert tuple(layers) == LAYER_NAMES
    write_layers(tmp_path)
    for name in LAYER_NAMES:
        fc = json.loads((tmp_path / f"{name}.geojson").read_text())
        assert fc["type"] == "FeatureCollection" and fc["features"]
    g_disk, g_mem = load_network(tmp_path), load_network()
    assert g_disk.number_of_edges() == g_mem.number_of_edges()


def test_network_connects_every_place():
    g = load_network()
    assert nx.is_connected(g)
    assert {p["place"] for p in places_table()} <= set(g.nodes)


def test_timetable_slots_fit_the_day():
    for cohort in S.COHORTS:
        for day in S.DAYS:
            for h, d, b in S.TIMETABLE[cohort][day]:
                assert S.DAY_START_H <= h and h + d <= 18
                assert b in load_network()


def test_everyone_is_somewhere_every_step(twin):
    occ = twin.occupancy()
    per_step = occ.groupby(["day", "step"])["people"].sum()
    assert (per_step == len(twin.agents)).all()


def test_nobody_in_class_at_midnight_hours(twin):
    tu = twin.time_use()
    late = tu[(tu["step"] >= S.step_of(23.0)) & (tu["activity"] == "class")]
    assert late["agents"].sum() == 0


def test_trips_match_location_changes(twin):
    trips = twin.trips()
    for day, r in twin.results.items():
        changes = int((np.diff(r.location, axis=1) != 0).sum())
        assert changes == (trips["day"] == day).sum()
    assert (trips["origin"] != trips["destination"]).all()
    assert (trips["distance_m"] > 0).all()


def test_road_usage_counts_path_edges(twin):
    trips, road = twin.trips(), twin.road_usage()
    expected = sum(len(twin.paths[o][d]) - 1 for o, d in zip(trips["origin"], trips["destination"]))
    assert road["trips"].sum() == expected


def test_runs_are_reproducible():
    a = CampusTwin(scale=0.02, seed=11).run_day("Tue").trips
    b = CampusTwin(scale=0.02, seed=11).run_day("Tue").trips
    pd.testing.assert_frame_equal(a, b)


def test_sql_queries(twin):
    con = write_db({"trips": twin.trips(), "occupancy": twin.occupancy(), "time_use": twin.time_use(),
                    "road_usage": twin.road_usage(), "places": pd.DataFrame(places_table())})
    results = run_queries(con)
    assert set(results) == set(load_queries())
    assert results["mode_split"]["share_pct"].sum() == pytest.approx(100, abs=0.2)
    assert len(results["busiest_segments"]) == 10
