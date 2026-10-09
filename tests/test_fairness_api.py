"""Contract tests for the /api/fairness endpoint.

templates/fairness.html reads these keys from the JSON payload:

    data.total_completed, data.overall_avg_minutes, data.overall_median_minutes,
    data.flagged_groups, data.flagged (list), data.groups

A missing key made `data.flagged.length` throw inside `render()`, so the page
showed the four summary numbers but silently drew no flagged cards, no charts
and no detail table. These tests pin the contract so that cannot regress.
"""

import pytest

import app as appmod


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    """Fresh SQLite DB per test (same pattern as test_ussd.py)."""
    monkeypatch.setattr(appmod, "DATABASE_PATH", str(tmp_path / "test.db"))
    appmod.init_db()
    yield


@pytest.fixture()
def client():
    appmod.app.config["TESTING"] = True
    return appmod.app.test_client()


def test_fairness_payload_has_every_key_the_page_reads(client):
    res = client.get("/api/fairness")
    assert res.status_code == 200
    data = res.get_json()

    # Scalars the summary cards read.
    assert isinstance(data["total_completed"], int)
    assert isinstance(data["overall_avg_minutes"], (int, float))
    assert isinstance(data["overall_median_minutes"], (int, float))
    assert isinstance(data["flagged_groups"], int)

    # The lists the page iterates. `flagged` used to be missing entirely.
    assert isinstance(data["flagged"], list)
    assert isinstance(data["groups"], list)
    assert data["flagged_groups"] == len(data["flagged"])


def test_flagged_items_expose_the_fields_the_card_template_interpolates(client):
    res = client.get("/api/fairness")
    assert res.status_code == 200
    data = res.get_json()

    # fairness.html builds each card from these exact properties.
    for g in data["flagged"]:
        assert "facility" in g
        assert "level" in g
        assert "sex" in g
        assert "age_group" in g
        assert "avg_wait_minutes" in g

    # The charts and the detail table read data.groups.
    for g in data["groups"]:
        assert "level" in g
        assert "sex" in g
        assert "age_group" in g
        assert "avg_wait_minutes" in g
        assert "flagged" in g


def test_fairness_page_still_serves_and_loads_the_script(client):
    res = client.get("/fairness")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    # The page must keep asking for the endpoint these tests pin down.
    assert "/api/fairness" in html
