import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.dates import resolve_dates
from app.db import Database
from app.main import create_app
from app.matcher import find_matches
from app.poller import Poller
from bmsTypes import BMSRegion, CinemaPageApiResponse, Movie, Venue

CITY = {
    "Alias": ["bangalore", "blr"],
    "AllowSales": "Y",
    "isOlaEnabled": "Y",
    "Lat": "12.9716",
    "Long": "77.5946",
    "RegionCallCenterNo": "1",
    "RegionCode": "BANG",
    "RegionName": "Bengaluru",
    "RegionSlug": "bengaluru",
    "Seq": "1",
    "HonourSubregionSlug": True,
    "GeoHash": "tdr1v",
    "SubRegions": [],
}

VENUE = {
    "VenueAddress": "Orion Mall, Rajajinagar",
    "CouponIsAllowed": "N",
    "RegionCode": "BANG",
    "CinemaIsNew": "N",
    "PostalCode": "560055",
    "VenueLongitude": "77.55",
    "VenueCode": "PVROR",
    "VenueLegends": "",
    "CinemaCodFlag": "N",
    "SubRegionCode": "",
    "VenueName": "PVR Orion",
    "City": "Bengaluru",
    "CinemaUnpaidFlag": "N",
    "CinemaCopFlag": "N",
    "VenueLatitude": "12.99",
    "MTicket": "Y",
    "CinemaAbout": "",
    "State": "KA",
    "VenueType": "M",
    "Country": "IN",
    "FoodSales": "Y",
    "tag": None,
    "isFavourite": False,
    "isDown": False,
    "CinemaIsOnlineNoTransactionMsg": "",
    "isRecommended": False,
    "mticket": "Y",
    "arrDates": [],
}


def make_showtime(date_code, show_time="7:30 PM", min_price="450", max_price="900"):
    return {
        "ShowDateTime": f"{date_code} 19:30:00",
        "CategoryRange": f"{min_price}-{max_price}",
        "Attributes": "",
        "ApplicableTimeFilters": [],
        "MinPrice": min_price,
        "UpdatedMinPrice": None,
        "SessionCopQuota": "",
        "SessionCodFlag": "N",
        "CutOffDateTime": "",
        "ChildSeats": "0",
        "BestAvailableSeats": 10,
        "CutOffFlag": "N",
        "SessionCodQuota": "",
        "SessionId": "S1",
        "BestBuy": "N",
        "SessionCopFlag": "N",
        "AvailStatus": "1",
        "ShowTime": show_time,
        "SessionPopUpDesc": "",
        "Categories": [],
        "ShowDateCode": date_code,
        "SessionUnpaidFlag": "N",
        "CoupleSeats": "0",
        "SessionUnpaidQuota": "",
        "IsAtmosEnabled": "N",
        "MaxPrice": max_price,
        "UpdatedMaxPrice": None,
        "Offers": None,
        "ApplicablePriceFilters": [],
        "ShowTimeCode": "T1",
        "SessionSubTitle": "",
        "SessionSubTitleAcronym": "",
    }


def make_response(date_code, title="Interstellar", dimension="IMAX 2D", showtimes=True):
    child = {
        "Event_strIsDefault": "Y",
        "EventSyn": "",
        "EventRAT": "",
        "EventSEQ": "1",
        "EventTrailer": "",
        "EventName": title,
        "EventGenre": {},
        "ApplicableTimeFilters": [],
        "EventCensor": "UA",
        "EventGroup": "MT",
        "EventCode": "ET1",
        "EventImageCode": "x",
        "EventDimension": dimension,
        "ShowTimes": [make_showtime(date_code)] if showtimes else [],
        "IsMovieClubEnabled": "N",
        "EventIsAtmosEnabled": "N",
        "Event_strPopUpDesc": "",
        "EventLanguage": "English",
        "EventUrl": "",
        "ApplicablePriceFilters": [],
    }
    event = {
        "EventTitle": title,
        "EventDuration": "169",
        "ChildEvents": [child],
        "EventSynopsis": "",
        "EventGenre": "",
        "ApplicablePriceFilters": [],
        "ApplicableTimeFilters": [],
        "EventCensor": "UA",
        "EventGroup": "MT",
    }
    return {
        "ShowDetails": [{"Date": date_code, "BMSOffers": None, "Event": [event]}]
    }


class FakeApi:
    def __init__(self, fail=False, showtimes=True):
        self.calls = []
        self.fail = fail
        self.showtimes = showtimes

    def fetch_regions(self):
        return BMSRegion.parse_obj({"BookMyShow": {"TopCities": [CITY], "OtherCities": []}})

    def fetch_venues(self, region_code):
        return [Venue.parse_obj(VENUE)]

    def fetch_movies(self, region_code, region_slug, languages=None, lat=None, lon=None):
        return [
            Movie(
                name="Interstellar",
                event_code="ET1",
                event_group="MT",
                language="English",
                genre="Sci-Fi",
            )
        ]

    def fetch_cinema_showtimes(self, venue_code, region_code, date=None):
        self.calls.append((venue_code, region_code, date))
        if self.fail:
            raise RuntimeError("boom")
        return CinemaPageApiResponse.parse_obj(make_response(date, showtimes=self.showtimes))


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def send(self, title, message, recipient_ids=None):
        self.calls.append((title, message, recipient_ids))


WATCH_PAYLOAD = {
    "region_code": "BANG",
    "region_slug": "bengaluru",
    "lat": "12.9716",
    "lon": "77.5946",
    "venue_code": "PVROR",
    "venue_name": "PVR Orion",
    "movie_title": "Interstellar",
    "formats": ["IMAX 2D"],
    "date_mode": "today",
    "interval_seconds": 60,
    "recipient_ids": ["r1"],
}


def seed_recipients(db, recipients=None):
    db.set_json_setting(
        "pushbullet_recipients",
        recipients
        if recipients is not None
        else [{"id": "r1", "label": "Ali", "token": "tok-r1", "device": ""}],
    )


# -- units --------------------------------------------------------------
def test_resolve_dates_today():
    codes, error = resolve_dates("today", None, None, "Asia/Kolkata")
    assert error is None
    assert len(codes) == 1
    assert len(codes[0]) == 8


def test_resolve_dates_range_clamps_to_today():
    codes, error = resolve_dates("range", "20200101", "20200110", "Asia/Kolkata")
    assert codes == []
    assert "passed" in error


def test_resolve_dates_bad_order():
    codes, error = resolve_dates("range", "20301231", "20300101", "Asia/Kolkata")
    assert codes == []
    assert "before" in error


def test_find_matches_respects_format_and_title():
    response = CinemaPageApiResponse.parse_obj(make_response("20261122"))
    assert len(find_matches(response, "interstellar", None, "20261122")) == 1
    assert find_matches(response, "interstellar", ["3D"], "20261122") == []
    assert len(find_matches(response, "inter", ["IMAX 2D"], "20261122")) == 1
    assert find_matches(response, "dune", None, "20261122") == []


def test_find_matches_requires_a_showtime():
    response = CinemaPageApiResponse.parse_obj(make_response("20261122", showtimes=False))
    assert find_matches(response, "interstellar", None, "20261122") == []


# -- poller -------------------------------------------------------------
def make_poller(tmp_path, api=None, notifier=None):
    db = Database(tmp_path / "bms.db")
    db.init()
    seed_recipients(db)
    settings = Settings(database_path=tmp_path / "bms.db")
    poller = Poller(db, api or FakeApi(), settings, notifier or FakeNotifier(), tick_seconds=0.01)
    return db, poller


def test_poller_notifies_once_on_transition(tmp_path):
    api, notifier = FakeApi(), FakeNotifier()
    db, poller = make_poller(tmp_path, api, notifier)
    watch = db.create_watch(dict(WATCH_PAYLOAD))

    asyncio.run(poller.tick())
    assert len(notifier.calls) == 1
    assert "Interstellar" in notifier.calls[0][0]
    assert notifier.calls[0][2] == ["r1"], "must only push to the watch's recipients"
    assert db.get_watch(watch["id"])["state"] == "found"

    calls_after_first = len(api.calls)
    asyncio.run(poller.tick())
    assert len(notifier.calls) == 1, "found watches must not notify again"
    assert len(api.calls) == calls_after_first, "found watches must not be re-polled"


def test_poller_records_errors_without_stopping(tmp_path):
    api, notifier = FakeApi(fail=True), FakeNotifier()
    db, poller = make_poller(tmp_path, api, notifier)
    watch = db.create_watch(dict(WATCH_PAYLOAD))

    asyncio.run(poller.tick())
    stored = db.get_watch(watch["id"])
    assert notifier.calls == []
    assert stored["state"] == "watching"
    assert "boom" in stored["last_error"]


def test_poller_skips_when_no_showtimes(tmp_path):
    api, notifier = FakeApi(showtimes=False), FakeNotifier()
    db, poller = make_poller(tmp_path, api, notifier)
    db.create_watch(dict(WATCH_PAYLOAD))
    asyncio.run(poller.tick())
    assert notifier.calls == []


def test_notification_failure_keeps_watch_retrying(tmp_path):
    class FailingNotifier:
        def send(self, title, message, recipient_ids=None):
            raise RuntimeError("push down")

    db, poller = make_poller(tmp_path, FakeApi(), FailingNotifier())
    watch = db.create_watch(dict(WATCH_PAYLOAD))

    asyncio.run(poller.tick())

    stored = db.get_watch(watch["id"])
    assert stored["state"] == "watching", "a failed alert must be retried"
    assert "push down" in stored["last_error"]
    assert stored["matched_detail"] is not None


def test_watch_with_missing_recipient_reports_error(tmp_path):
    from app.notify import PushbulletSender

    db, poller = make_poller(tmp_path, FakeApi())
    poller.notifier = PushbulletSender(db)
    watch = db.create_watch(dict(WATCH_PAYLOAD))
    db.remove_recipient_from_watches("r1")

    asyncio.run(poller.tick())

    stored = db.get_watch(watch["id"])
    assert stored["state"] == "watching"
    assert "no pushbullet recipient" in stored["last_error"].lower()


# -- HTTP API -----------------------------------------------------------
def make_client(tmp_path, app_token="secret", api=None, notifier=None, recipients=None):
    if recipients is None:
        seed = Database(tmp_path / "bms.db")
        seed.init()
        seed_recipients(seed)

    settings = Settings(
        app_token=app_token,
        database_path=tmp_path / "bms.db",
        poll_tick_seconds=3600,
    )
    app = create_app(settings, api=api or FakeApi(), notifier=notifier)
    return TestClient(app)


def test_auth_gate(tmp_path):
    with make_client(tmp_path) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/api/watches").status_code == 401
        assert client.post("/api/login", json={"token": "nope"}).status_code == 401
        assert client.post("/api/login", json={"token": "secret"}).status_code == 200
        assert client.get("/api/watches").status_code == 200


def test_watch_crud_and_check(tmp_path):
    api, notifier = FakeApi(), FakeNotifier()
    with make_client(tmp_path, api=api, notifier=notifier) as client:
        client.post("/api/login", json={"token": "secret"})

        created = client.post("/api/watches", json=WATCH_PAYLOAD)
        assert created.status_code == 201, created.text
        watch = created.json()
        assert watch["state"] == "watching"
        assert watch["formats"] == ["IMAX 2D"]

        listed = client.get("/api/watches").json()
        assert [w["id"] for w in listed] == [watch["id"]]

        result = client.post(f"/api/watches/{watch['id']}/check").json()
        assert len(result["matches"]) == 1
        assert result["matches"][0]["format"] == "IMAX 2D"
        assert result["notified"] is False
        assert result["watch"]["state"] == "found"
        assert result["watch"]["matched_detail"]["url"].startswith(
            "https://in.bookmyshow.com/buytickets/pvr-orion/cinema-bang-PVROR-MT/"
        )

        history = client.get(f"/api/watches/{watch['id']}/history").json()
        assert history and history[0]["found"] is True

        paused = client.patch(f"/api/watches/{watch['id']}", json={"enabled": False}).json()
        assert paused["enabled"] is False and paused["state"] == "paused"

        assert client.delete(f"/api/watches/{watch['id']}").status_code == 200
        assert client.get("/api/watches").json() == []


def test_watch_validation_and_not_found(tmp_path):
    with make_client(tmp_path) as client:
        client.post("/api/login", json={"token": "secret"})
        assert client.post("/api/watches", json={**WATCH_PAYLOAD, "movie_title": "  "}).status_code == 400
        assert client.post("/api/watches", json={**WATCH_PAYLOAD, "interval_seconds": 5}).status_code == 400
        assert client.post("/api/watches", json={**WATCH_PAYLOAD, "date_mode": "whenever"}).status_code == 400
        assert client.get("/api/watches/9999").status_code == 404
        assert client.delete("/api/watches/9999").status_code == 404
        assert client.post("/api/watches/9999/check").status_code == 404


def test_catalogue_endpoints(tmp_path):
    with make_client(tmp_path) as client:
        client.post("/api/login", json={"token": "secret"})
        regions = client.get("/api/regions?q=bang").json()
        assert regions[0]["code"] == "BANG"
        venues = client.get("/api/venues?region=BANG&q=pvr").json()
        assert venues[0]["name"] == "PVR Orion"
        movies = client.get("/api/movies?region=BANG&q=inter").json()
        assert movies[0]["title"] == "Interstellar"


def test_pushbullet_recipients_crud_and_test(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.notify.PushbulletNotifier.send",
        lambda self, title, message: sent.append((self.token, title)),
    )
    with make_client(tmp_path, recipients=[]) as client:
        client.post("/api/login", json={"token": "secret"})
        assert client.get("/api/settings").json()["pushbullet_recipients"] == []
        assert client.post("/api/settings/pushbullet", json={"token": "  "}).status_code == 400

        created = client.post(
            "/api/settings/pushbullet",
            json={"label": "Ali", "token": "abcdef123456", "device": "dev-1"},
        )
        assert created.status_code == 201, created.text
        recipient = created.json()
        assert recipient["token_hint"] == "••••3456"
        assert recipient["label"] == "Ali"
        assert "abcdef123456" not in created.text

        duplicate = client.post("/api/settings/pushbullet", json={"token": "abcdef123456"})
        assert duplicate.status_code == 409

        settings = client.get("/api/settings").json()
        assert settings["token_configured"] is True
        assert len(settings["pushbullet_recipients"]) == 1
        assert "abcdef123456" not in str(settings)

        test_response = client.post("/api/notifications/test")
        assert test_response.status_code == 200, test_response.text
        assert test_response.json()["result"]["sent"] == 1
        assert sent == [("abcdef123456", "BMS watcher test")]

        assert client.delete(f"/api/settings/pushbullet/{recipient['id']}").status_code == 200
        assert client.get("/api/settings").json()["pushbullet_recipients"] == []


def make_sender(tmp_path, recipients, env_token=""):
    from app.notify import PushbulletSender

    db = Database(tmp_path / "bms.db")
    db.init()
    db.set_json_setting("pushbullet_recipients", recipients)
    return db, PushbulletSender(db, env_token)


def test_sender_fans_out_to_every_recipient(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.notify.PushbulletNotifier.send",
        lambda self, title, message: sent.append((self.token, self.device_iden)),
    )
    _, sender = make_sender(
        tmp_path,
        [
            {"id": "a", "label": "A", "token": "tok-a", "device": ""},
            {"id": "b", "label": "B", "token": "tok-b", "device": "dev-b"},
        ],
    )
    result = sender.send("T", "M")
    assert sent == [("tok-a", None), ("tok-b", "dev-b")]
    assert result["sent"] == 2 and result["total"] == 2
    assert all(item["ok"] for item in result["results"])


def test_sender_survives_partial_failure(tmp_path, monkeypatch):
    def flaky(self, title, message):
        if self.token == "tok-a":
            raise RuntimeError("nope")

    monkeypatch.setattr("app.notify.PushbulletNotifier.send", flaky)
    _, sender = make_sender(
        tmp_path,
        [
            {"id": "a", "label": "A", "token": "tok-a", "device": ""},
            {"id": "b", "label": "B", "token": "tok-b", "device": ""},
        ],
    )
    result = sender.send("T", "M")
    assert result["sent"] == 1
    assert result["total"] == 2
    assert [item["ok"] for item in result["results"]] == [False, True]


def test_sender_raises_when_every_recipient_fails(tmp_path, monkeypatch):
    def boom(self, title, message):
        raise RuntimeError("down")

    monkeypatch.setattr("app.notify.PushbulletNotifier.send", boom)
    _, sender = make_sender(
        tmp_path, [{"id": "a", "label": "A", "token": "tok-a", "device": ""}]
    )
    with pytest.raises(RuntimeError, match="every recipient"):
        sender.send("T", "M")


def test_sender_without_recipients_points_to_settings(tmp_path):
    _, sender = make_sender(tmp_path, [])
    with pytest.raises(RuntimeError, match="Settings"):
        sender.send("T", "M")


def test_env_token_is_an_extra_deduplicated_recipient(tmp_path):
    _, sender = make_sender(
        tmp_path,
        [{"id": "a", "label": "A", "token": "tok-a", "device": ""}],
        env_token="tok-env",
    )
    recipients = sender.recipients()
    assert [item["token"] for item in recipients] == ["tok-a", "tok-env"]
    assert recipients[1]["source"] == "env"

    _, duplicate = make_sender(
        tmp_path / "b",
        [{"id": "a", "label": "A", "token": "tok-a", "device": ""}],
        env_token="tok-a",
    )
    assert len(duplicate.recipients()) == 1


def test_legacy_single_token_is_migrated(tmp_path):
    from app.notify import PushbulletSender

    db = Database(tmp_path / "bms.db")
    db.init()
    db.set_setting("pushbullet_token", "legacy-token")
    db.set_setting("pushbullet_device", "legacy-device")
    db.migrate()

    recipients = db.get_json_setting("pushbullet_recipients")
    assert recipients[0]["token"] == "legacy-token"
    assert recipients[0]["device"] == "legacy-device"
    assert db.get_setting("pushbullet_token") is None
    assert PushbulletSender(db).recipients()[0]["token"] == "legacy-token"


def test_migration_backfills_existing_watches_with_all_recipients(tmp_path):
    db = Database(tmp_path / "bms.db")
    db.init()
    seed_recipients(db)
    watch = db.create_watch(dict(WATCH_PAYLOAD))
    # Simulate a row written before per-watch routing existed.
    with db.session() as conn:
        conn.execute("UPDATE watches SET recipient_ids = '[]' WHERE id = ?", (watch["id"],))

    db.migrate()

    assert db.get_watch(watch["id"])["recipient_ids"] == ["r1"]


def test_watch_requires_a_known_recipient(tmp_path):
    with make_client(tmp_path) as client:
        client.post("/api/login", json={"token": "secret"})

        missing = client.post("/api/watches", json={**WATCH_PAYLOAD, "recipient_ids": []})
        assert missing.status_code == 400
        assert "recipient" in missing.json()["detail"]

        unknown = client.post("/api/watches", json={**WATCH_PAYLOAD, "recipient_ids": ["nope"]})
        assert unknown.status_code == 400
        assert "nope" in unknown.json()["detail"]

        created = client.post("/api/watches", json=WATCH_PAYLOAD)
        assert created.status_code == 201
        assert created.json()["recipient_ids"] == ["r1"]


def test_each_watch_notifies_only_its_own_recipients(tmp_path):
    class CapturingNotifier:
        def __init__(self):
            self.calls = []

        def send(self, title, message, recipient_ids=None):
            self.calls.append(recipient_ids)
            return {"sent": 1, "total": 1, "results": []}

    with make_client(tmp_path) as client:
        client.post("/api/login", json={"token": "secret"})
        second = client.post(
            "/api/settings/pushbullet", json={"label": "Bob", "token": "tok-bob"}
        ).json()

        mine = client.post("/api/watches", json=WATCH_PAYLOAD).json()
        theirs = client.post(
            "/api/watches", json={**WATCH_PAYLOAD, "recipient_ids": [second["id"]]}
        ).json()

        poller = client.app.state.poller
        capture = CapturingNotifier()
        poller.notifier = capture

        asyncio.run(poller.check_watch(mine["id"], notify=True))
        asyncio.run(poller.check_watch(theirs["id"], notify=True))

        assert capture.calls == [["r1"], [second["id"]]]


def test_deleting_recipient_strips_it_from_watches(tmp_path):
    with make_client(tmp_path) as client:
        client.post("/api/login", json={"token": "secret"})
        watch = client.post("/api/watches", json=WATCH_PAYLOAD).json()
        assert watch["recipient_ids"] == ["r1"]

        assert client.delete("/api/settings/pushbullet/r1").status_code == 200

        updated = client.get(f"/api/watches/{watch['id']}").json()
        assert updated["recipient_ids"] == []


def test_auth_disabled_allows_access(tmp_path):
    with make_client(tmp_path, app_token="") as client:
        assert client.get("/api/watches").status_code == 200
        assert client.get("/api/settings").json()["auth_enabled"] is False


def test_non_search_patch_keeps_found_state(tmp_path):
    with make_client(tmp_path) as client:
        client.post("/api/login", json={"token": "secret"})
        watch = client.post("/api/watches", json=WATCH_PAYLOAD).json()
        client.post(f"/api/watches/{watch['id']}/check")

        edited = client.patch(
            f"/api/watches/{watch['id']}", json={"interval_seconds": 120}
        ).json()
        assert edited["state"] == "found"
        assert edited["interval_seconds"] == 120

        changed = client.patch(
            f"/api/watches/{watch['id']}", json={"movie_title": "Dune"}
        ).json()
        assert changed["state"] == "watching"
        assert changed["matched_detail"] is None

