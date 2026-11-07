import asyncio

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

    def send(self, title, message):
        self.calls.append((title, message))


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
}


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


# -- HTTP API -----------------------------------------------------------
def make_client(tmp_path, app_token="secret", api=None, notifier=None):
    settings = Settings(
        app_token=app_token,
        database_path=tmp_path / "bms.db",
        poll_tick_seconds=3600,
    )
    app = create_app(settings, api=api or FakeApi(), notifier=notifier or FakeNotifier())
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


def test_settings_mask_and_test_push(tmp_path):
    notifier = FakeNotifier()
    with make_client(tmp_path, notifier=notifier) as client:
        client.post("/api/login", json={"token": "secret"})

        settings = client.get("/api/settings").json()
        assert settings["token_configured"] is False

        client.patch("/api/settings", json={"pushbullet_token": "abcdef123456"})
        settings = client.get("/api/settings").json()
        assert settings["token_configured"] is True
        assert settings["token_hint"] == "••••3456"
        assert "abcdef123456" not in str(settings)

        assert client.post("/api/notifications/test").status_code == 200
        assert len(notifier.calls) == 1


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
            f"/api/watches/{watch['id']}", json={"pushbullet_device": "device-1"}
        ).json()
        assert edited["state"] == "found"
        assert edited["pushbullet_device"] == "device-1"

        cleared = client.patch(
            f"/api/watches/{watch['id']}", json={"pushbullet_device": None}
        ).json()
        assert cleared["pushbullet_device"] is None
        assert cleared["state"] == "found"

        changed = client.patch(
            f"/api/watches/{watch['id']}", json={"movie_title": "Dune"}
        ).json()
        assert changed["state"] == "watching"
        assert changed["matched_detail"] is None

