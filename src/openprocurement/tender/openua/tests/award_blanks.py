# -*- coding: utf-8 -*-
from datetime import timedelta
import dateutil

import mock
from iso8601 import parse_date

from openprocurement.api.constants import SANDBOX_MODE, RELEASE_2020_04_19
from openprocurement.api.utils import get_now
from openprocurement.tender.core.tests.cancellation import activate_cancellation_after_2020_04_19
from openprocurement.tender.belowthreshold.tests.base import (
    test_organization, test_author,
    test_draft_claim, test_claim,
    test_complaint, test_draft_complaint,
    test_cancellation
)
from openprocurement.tender.openua.constants import STAND_STILL_TIME


def create_tender_award(self):
    auth = self.app.authorization
    self.app.authorization = ("Basic", ("token", ""))

    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {"data": {"suppliers": [test_organization], "status": "pending", "bid_id": self.initial_bids[0]["id"]}},
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    award = response.json["data"]
    self.assertEqual(award["suppliers"][0]["name"], test_organization["name"])
    self.assertIn("id", award)
    self.assertIn(award["id"], response.headers["Location"])

    self.app.authorization = auth

    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"][-1], award)

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "active", "qualified": True, "eligible": True}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], u"active")

    response = self.app.get("/tenders/{}".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], u"active.awarded")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "cancelled"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], u"cancelled")
    self.assertIn("Location", response.headers)


def patch_tender_award(self):
    auth = self.app.authorization
    self.app.authorization = ("Basic", ("token", ""))
    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {
            "data": {
                "suppliers": [test_organization],
                "status": u"pending",
                "bid_id": self.initial_bids[0]["id"],
                "value": {"amount": 500},
            }
        },
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    award = response.json["data"]

    self.app.authorization = auth
    response = self.app.patch_json(
        "/tenders/{}/awards/some_id".format(self.tender_id), {"data": {"status": "unsuccessful"}}, status=404
    )
    self.assertEqual(response.status, "404 Not Found")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"], [{u"description": u"Not Found", u"location": u"url", u"name": u"award_id"}]
    )

    response = self.app.patch_json("/tenders/some_id/awards/some_id", {"data": {"status": "unsuccessful"}}, status=404)
    self.assertEqual(response.status, "404 Not Found")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"], [{u"description": u"Not Found", u"location": u"url", u"name": u"tender_id"}]
    )

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"awardStatus": "unsuccessful"}},
        status=422,
    )
    self.assertEqual(response.status, "422 Unprocessable Entity")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(
        response.json["errors"], [{"location": "body", "name": "awardStatus", "description": "Rogue field"}]
    )

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "unsuccessful"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)
    new_award_location = response.headers["Location"]

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "pending"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"], "Can't update award in current (unsuccessful) status")

    request_path = "/tenders/{}/awards".format(self.tender_id)
    response = self.app.get(request_path)
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(len(response.json["data"]), 2)
    self.assertIn(response.json["data"][1]["id"], new_award_location)
    new_award = response.json["data"][-1]
    old_date = new_award["date"]

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, new_award["id"], self.tender_token),
        {"data": {"status": "active", "qualified": True, "eligible": True}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertNotEqual(old_date, response.json["data"]["date"])
    old_date = response.json["data"]["date"]

    response = self.app.get(request_path)
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(len(response.json["data"]), 2)

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, new_award["id"], self.tender_token),
        {"data": {"status": "cancelled"}},
    )
    self.assertNotEqual(old_date, response.json["data"]["date"])
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)

    response = self.app.get(request_path)
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(len(response.json["data"]), 3)

    self.set_status("complete")

    response = self.app.get("/tenders/{}/awards/{}".format(self.tender_id, award["id"]))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["value"]["amount"], 500)

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "unsuccessful"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(
        response.json["errors"][0]["description"], "Can't update award in current (complete) tender status"
    )


def check_tender_award_complaint_period_dates(self):

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, self.award_id, self.tender_token),
        {"data": {"status": "unsuccessful"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)

    updated_award = response.json["data"]
    self.assertIn("endDate", updated_award["complaintPeriod"])
    new_complaint_period_start_date = dateutil.parser.parse(updated_award["complaintPeriod"]["startDate"])
    new_complaint_period_end_date = dateutil.parser.parse(updated_award["complaintPeriod"]["endDate"])

    self.assertGreater(new_complaint_period_start_date, self.old_complaint_period_start_date)
    self.assertGreater(new_complaint_period_end_date, new_complaint_period_start_date)


def patch_tender_award_active(self):
    auth = self.app.authorization
    self.app.authorization = ("Basic", ("token", ""))
    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {
            "data": {
                "suppliers": [test_organization],
                "status": u"pending",
                "bid_id": self.initial_bids[0]["id"],
                "value": {"amount": 500},
            }
        },
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    award = response.json["data"]

    self.app.authorization = auth
    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "unsuccessful"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)
    new_award_location = response.headers["Location"]

    response = self.app.patch_json(
        new_award_location[-81:] + "?acc_token={}".format(self.tender_token),
        {"data": {"status": "active", "qualified": True, "eligible": True}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertNotIn("Location", response.headers)

    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(len(response.json["data"]), 2)

    bid_token = self.initial_bids_tokens[self.initial_bids[0]["id"]]
    response = self.app.post_json(
        new_award_location[-81:] + "/complaints?acc_token={}".format(bid_token),
        {
            "data": test_complaint
        },
    )
    self.assertEqual(response.status, "201 Created")
    complaint_id = response.json["data"]["id"]
    now = get_now()
    if RELEASE_2020_04_19 < now:
        self.assertEqual(response.json["data"]["status"], "draft")
        owner_token = response.json["access"]["token"]

        response = self.app.patch_json(
            new_award_location[-81:] + "/complaints/{}?acc_token={}".format(complaint_id, owner_token),
            {"data": {"status": "pending"}},
        )
        self.assertEqual(response.status, "200 OK")
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.json["data"]["status"], "pending")

    self.app.authorization = ("Basic", ("reviewer", ""))
    data = {"status": "accepted"}
    if RELEASE_2020_04_19 < now:
        data.update({
            "reviewDate": now.isoformat(),
            "reviewPlace": "some",
        })

    response = self.app.patch_json(
        new_award_location[-81:] + "/complaints/{}".format(complaint_id),
        {"data": data},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.json["data"]["status"], "accepted")
    if RELEASE_2020_04_19 < now:
        self.assertEqual(response.json["data"]["reviewPlace"], "some")
        self.assertEqual(response.json["data"]["reviewDate"], now.isoformat())

    response = self.app.patch_json(
        new_award_location[-81:] + "/complaints/{}".format(response.json["data"]["id"]),
        {"data": {"status": "satisfied"}},
    )
    self.assertEqual(response.status, "200 OK")

    self.app.authorization = ("Basic", ("token", ""))
    response = self.app.patch_json(new_award_location[-81:], {"data": {"status": "cancelled"}})
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)
    new_award_location = response.headers["Location"]

    response = self.app.patch_json(new_award_location[-81:], {"data": {"status": "unsuccessful"}})
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)
    new_award_location = response.headers["Location"]

    response = self.app.patch_json(new_award_location[-81:], {"data": {"status": "unsuccessful"}})
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertNotIn("Location", response.headers)

    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(len(response.json["data"]), 4)


def patch_tender_award_unsuccessful(self):
    auth = self.app.authorization
    self.app.authorization = ("Basic", ("token", ""))
    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {
            "data": {
                "suppliers": [test_organization],
                "status": u"pending",
                "bid_id": self.initial_bids[0]["id"],
                "value": {"amount": 500},
            }
        },
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    award = response.json["data"]

    self.app.authorization = auth
    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "unsuccessful"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)
    new_award_location = response.headers["Location"]

    response = self.app.patch_json(
        new_award_location[-81:] + "?acc_token={}".format(self.tender_token),
        {"data": {"status": "active", "qualified": True, "eligible": True}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertNotIn("Location", response.headers)

    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(len(response.json["data"]), 2)

    bid_token = self.initial_bids_tokens[self.initial_bids[0]["id"]]
    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, award["id"], bid_token),
        {
            "data": test_complaint
        },
    )
    self.assertEqual(response.status, "201 Created")
    complaint_id = response.json["data"]["id"]

    now = get_now()
    if RELEASE_2020_04_19 < now:
        self.assertEqual(response.json["data"]["status"], "draft")
        owner_token = response.json["access"]["token"]

        response = self.app.patch_json(
            "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
                self.tender_id, award["id"], complaint_id, owner_token),
            {"data": {"status": "pending"}},
        )
        self.assertEqual(response.status, "200 OK")
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.json["data"]["status"], "pending")

    self.app.authorization = ("Basic", ("reviewer", ""))
    data = {"status": "accepted"}
    if RELEASE_2020_04_19 < now:
        data.update({
            "reviewDate": now.isoformat(),
            "reviewPlace": "some",
        })
    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}".format(self.tender_id, award["id"], complaint_id),
        {"data": data},
    )
    self.assertEqual(response.status, "200 OK")
    if RELEASE_2020_04_19 < now:
        self.assertEqual(response.json["data"]["reviewPlace"], "some")
        self.assertEqual(response.json["data"]["reviewDate"], now.isoformat())

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}".format(self.tender_id, award["id"], complaint_id),
        {"data": {"status": "satisfied"}},
    )
    self.assertEqual(response.status, "200 OK")

    self.app.authorization = ("Basic", ("token", ""))
    response = self.app.post_json(
        "{}/complaints".format(new_award_location[-81:]),
        {"data": test_draft_claim},
    )
    self.assertEqual(response.status, "201 Created")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}".format(self.tender_id, award["id"]), {"data": {"status": "cancelled"}}
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)
    new_award_location = response.headers["Location"]

    response = self.app.patch_json(new_award_location[-81:], {"data": {"status": "unsuccessful"}})
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)
    new_award_location = response.headers["Location"]

    response = self.app.patch_json(new_award_location[-81:], {"data": {"status": "unsuccessful"}})
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertNotIn("Location", response.headers)

    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(len(response.json["data"]), 4)


def create_tender_award_no_scale_invalid(self):
    self.app.authorization = ("Basic", ("token", ""))
    suppliers = [{key: value for key, value in test_organization.iteritems() if key != "scale"}]
    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {"data": {"status": "pending", "bid_id": self.initial_bids[0]["id"], "suppliers": suppliers}},
        status=422,
    )
    self.assertEqual(response.status, "422 Unprocessable Entity")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"],
        [{u"location": u"body", u"name": u"suppliers", u"description": [{u"scale": [u"This field is required."]}]}],
    )


# TenderAwardResourceScaleTest


@mock.patch("openprocurement.api.models.ORGANIZATION_SCALE_FROM", get_now() + timedelta(days=1))
def create_tender_award_with_scale_not_required(self):
    self.app.authorization = ("Basic", ("token", ""))
    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {"data": {"status": "pending", "bid_id": self.initial_bids[0]["id"], "suppliers": [test_organization]}},
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    self.assertNotIn("scale", response.json["data"])


@mock.patch("openprocurement.api.models.ORGANIZATION_SCALE_FROM", get_now() + timedelta(days=1))
def create_tender_award_no_scale(self):
    self.app.authorization = ("Basic", ("token", ""))
    suppliers = [{key: value for key, value in test_organization.iteritems() if key != "scale"}]
    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {"data": {"status": "pending", "bid_id": self.initial_bids[0]["id"], "suppliers": suppliers}},
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    self.assertNotIn("scale", response.json["data"]["suppliers"][0])


# TenderLotAwardResourceTest


def create_tender_lot_award(self):
    auth = self.app.authorization
    self.app.authorization = ("Basic", ("token", ""))
    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {"data": {"suppliers": [test_organization], "status": "pending", "bid_id": self.initial_bids[0]["id"]}},
        status=422,
    )
    self.assertEqual(response.status, "422 Unprocessable Entity")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(
        response.json["errors"], [{"location": "body", "name": "lotID", "description": ["This field is required."]}]
    )

    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {
            "data": {
                "suppliers": [test_organization],
                "status": "pending",
                "bid_id": self.initial_bids[0]["id"],
                "lotID": self.initial_lots[0]["id"],
            }
        },
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    award = response.json["data"]
    self.assertEqual(award["suppliers"][0]["name"], test_organization["name"])
    self.assertEqual(award["lotID"], self.initial_lots[0]["id"])
    self.assertIn("id", award)
    self.assertIn(award["id"], response.headers["Location"])

    self.app.authorization = auth
    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"][-1], award)

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "active", "qualified": True, "eligible": True}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], u"active")

    response = self.app.get("/tenders/{}".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], u"active.awarded")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "cancelled"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], u"cancelled")
    self.assertIn("Location", response.headers)


def patch_tender_lot_award(self):
    auth = self.app.authorization
    self.app.authorization = ("Basic", ("token", ""))
    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {
            "data": {
                "suppliers": [test_organization],
                "status": u"pending",
                "bid_id": self.initial_bids[0]["id"],
                "lotID": self.initial_lots[0]["id"],
                "value": {"amount": 500},
            }
        },
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    award = response.json["data"]

    self.app.authorization = auth
    response = self.app.patch_json(
        "/tenders/{}/awards/some_id?acc_token={}".format(self.tender_id, self.tender_token),
        {"data": {"status": "unsuccessful"}},
        status=404,
    )
    self.assertEqual(response.status, "404 Not Found")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"], [{u"description": u"Not Found", u"location": u"url", u"name": u"award_id"}]
    )

    response = self.app.patch_json("/tenders/some_id/awards/some_id", {"data": {"status": "unsuccessful"}}, status=404)
    self.assertEqual(response.status, "404 Not Found")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"], [{u"description": u"Not Found", u"location": u"url", u"name": u"tender_id"}]
    )

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"awardStatus": "unsuccessful"}},
        status=422,
    )
    self.assertEqual(response.status, "422 Unprocessable Entity")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(
        response.json["errors"], [{"location": "body", "name": "awardStatus", "description": "Rogue field"}]
    )

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"title": "title", "description": "description", "status": "unsuccessful"}},
    )

    self.assertEqual(response.json["data"]["title"], "title")
    self.assertEqual(response.json["data"]["description"], "description")
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)
    new_award_location = response.headers["Location"]

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "pending"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"], "Can't update award in current (unsuccessful) status")

    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(len(response.json["data"]), 2)
    self.assertIn(response.json["data"][-1]["id"], new_award_location)
    new_award = response.json["data"][-1]

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, new_award["id"], self.tender_token),
        {"data": {"status": "active", "eligible": True}},
        status=422,
    )
    self.assertEqual(response.status, "422 Unprocessable Entity")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(
        response.json["errors"], [{"location": "body", "name": "qualified", "description": ["This field is required."]}]
    )
    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, new_award["id"], self.tender_token),
        {"data": {"title": "title", "description": "description", "qualified": True, "eligible": True}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["qualified"], True)
    self.assertEqual(response.json["data"]["eligible"], True)
    self.assertEqual(response.json["data"]["title"], "title")
    self.assertEqual(response.json["data"]["description"], "description")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, new_award["id"], self.tender_token),
        {"data": {"status": "active", "qualified": True, "eligible": True}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")

    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(len(response.json["data"]), 2)

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, new_award["id"], self.tender_token),
        {"data": {"status": "cancelled"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)

    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(len(response.json["data"]), 3)

    self.set_status("complete")

    response = self.app.get("/tenders/{}/awards/{}".format(self.tender_id, award["id"]))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["value"]["amount"], 500)

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "unsuccessful"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(
        response.json["errors"][0]["description"], "Can't update award in current (complete) tender status"
    )


def patch_tender_lot_award_unsuccessful(self):
    auth = self.app.authorization
    self.app.authorization = ("Basic", ("token", ""))

    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {
            "data": {
                "suppliers": [test_organization],
                "status": u"pending",
                "bid_id": self.initial_bids[0]["id"],
                "lotID": self.initial_lots[0]["id"],
                "value": {"amount": 500},
            }
        },
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    award = response.json["data"]

    self.app.authorization = auth
    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "unsuccessful"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)
    new_award_location = response.headers["Location"]

    response = self.app.patch_json(
        new_award_location[-81:] + "?acc_token={}".format(self.tender_token),
        {"data": {"status": "active", "qualified": True, "eligible": True}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertNotIn("Location", response.headers)

    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(len(response.json["data"]), 2)

    bid_token = self.initial_bids_tokens[self.initial_bids[0]["id"]]
    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, award["id"], bid_token),
        {
            "data": test_complaint
        },
    )
    self.assertEqual(response.status, "201 Created")
    complaint_id = response.json["data"]["id"]

    now = get_now()
    if RELEASE_2020_04_19 < now:
        self.assertEqual(response.json["data"]["status"], "draft")
        owner_token = response.json["access"]["token"]

        response = self.app.patch_json(
            "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
                self.tender_id, award["id"], complaint_id, owner_token),
            {"data": {"status": "pending"}},
        )
        self.assertEqual(response.status, "200 OK")
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.json["data"]["status"], "pending")

    self.app.authorization = ("Basic", ("reviewer", ""))
    now = get_now()
    data = {"status": "accepted"}
    if RELEASE_2020_04_19 < now:
        data.update({
            "reviewDate": now.isoformat(),
            "reviewPlace": "some",
        })
    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}".format(self.tender_id, award["id"], complaint_id),
        {"data": data},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.json["data"]["status"], "accepted")
    if RELEASE_2020_04_19 < now:
        self.assertEqual(response.json["data"]["reviewPlace"], "some")
        self.assertEqual(response.json["data"]["reviewDate"], now.isoformat())

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}".format(self.tender_id, award["id"], complaint_id),
        {"data": {"status": "satisfied"}},
    )
    self.assertEqual(response.status, "200 OK")

    self.app.authorization = ("Basic", ("token", ""))
    response = self.app.post_json(
        "{}/complaints".format(new_award_location[-81:]),
        {"data": test_draft_claim},
    )
    self.assertEqual(response.status, "201 Created")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}".format(self.tender_id, award["id"]), {"data": {"status": "cancelled"}}
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)
    new_award_location = response.headers["Location"]

    response = self.app.patch_json(new_award_location[-81:], {"data": {"status": "unsuccessful"}})
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertIn("Location", response.headers)
    new_award_location = response.headers["Location"]

    response = self.app.patch_json(new_award_location[-81:], {"data": {"status": "unsuccessful"}})
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertNotIn("Location", response.headers)

    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(len(response.json["data"]), 4)


# Tender2LotAwardResourceTest


def create_tender_lots_award(self):
    cancellation = dict(**test_cancellation)
    cancellation.update({
        "status": "active",
        "cancellationOf": "lot",
        "relatedLot": self.initial_lots[0]["id"],
    })
    response = self.app.post_json(
        "/tenders/{}/cancellations?acc_token={}".format(self.tender_id, self.tender_token),
        {"data": cancellation},
    )
    self.assertEqual(response.status, "201 Created")
    cancellation_id = response.json["data"]["id"]

    if RELEASE_2020_04_19 < get_now():
        activate_cancellation_after_2020_04_19(self, cancellation_id)

    auth = self.app.authorization
    self.app.authorization = ("Basic", ("token", ""))
    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {
            "data": {
                "suppliers": [test_organization],
                "status": "pending",
                "bid_id": self.initial_bids[0]["id"],
                "lotID": self.initial_lots[0]["id"],
            }
        },
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"], "Can create award only in active lot status")

    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {
            "data": {
                "suppliers": [test_organization],
                "status": "pending",
                "bid_id": self.initial_bids[0]["id"],
                "lotID": self.initial_lots[1]["id"],
            }
        },
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    award = response.json["data"]
    self.assertEqual(award["suppliers"][0]["name"], test_organization["name"])
    self.assertEqual(award["lotID"], self.initial_lots[1]["id"])
    self.assertIn("id", award)
    self.assertIn(award["id"], response.headers["Location"])

    self.app.authorization = auth
    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"][-1], award)

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "active", "qualified": True, "eligible": True}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], u"active")

    response = self.app.get("/tenders/{}".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], u"active.awarded")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "cancelled"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], u"cancelled")
    self.assertIn("Location", response.headers)


def patch_tender_lots_award(self):

    auth = self.app.authorization
    self.app.authorization = ("Basic", ("token", ""))

    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {
            "data": {
                "suppliers": [test_organization],
                "status": u"pending",
                "bid_id": self.initial_bids[0]["id"],
                "lotID": self.initial_lots[0]["id"],
                "value": {"amount": 500},
            }
        },
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    award = response.json["data"]

    self.app.authorization = auth
    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award["id"], self.tender_token),
        {"data": {"status": "active", "qualified": True, "eligible": True}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")

    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(len(response.json["data"]), 2)
    new_award = response.json["data"][-1]

    cancellation = dict(**test_cancellation)
    cancellation.update({
        "status": "active",
        "cancellationOf": "lot",
        "relatedLot": self.initial_lots[1]["id"],
    })
    response = self.app.post_json(
        "/tenders/{}/cancellations?acc_token={}".format(self.tender_id, self.tender_token),
        {"data": cancellation},
    )
    self.assertEqual(response.status, "201 Created")
    cancellation_id = response.json["data"]["id"]

    if RELEASE_2020_04_19 < get_now():
        activate_cancellation_after_2020_04_19(self, cancellation_id)

    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, new_award["id"], self.tender_token),
        {"data": {"status": "unsuccessful"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"], "Can update award only in active lot status")


# TenderAwardComplaintResourceTest


def create_tender_award_claim(self):
    auth = self.app.authorization
    self.app.authorization = ("Basic", ("token", ""))
    self.app.patch_json(
        "/tenders/{}/awards/{}".format(self.tender_id, self.award_id), {"data": {"status": "cancelled"}}
    )

    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    award_id = [i["id"] for i in response.json["data"] if i["status"] == "pending"][-1]
    bid_token = self.initial_bids_tokens[self.initial_bids[1]["id"]]
    self.app.authorization = auth

    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, award_id, bid_token),
        {
            "data": test_claim
        },
        status=403,
    )
    self.assertEqual(
        response.json["errors"],
        [
            {
                u"description": u"Claim submission is not allowed on pending award",
                u"location": u"body",
                u"name": u"data",
            }
        ],
    )

    auth = self.app.authorization
    self.app.authorization = ("Basic", ("token", ""))

    self.app.patch_json("/tenders/{}/awards/{}".format(self.tender_id, award_id), {"data": {"status": "unsuccessful"}})
    self.app.authorization = auth

    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, award_id, bid_token),
        {
            "data": test_claim
        },
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"],
        [
            {
                u"description": u"Can add claim only on unsuccessful award of your bid",
                u"location": u"body",
                u"name": u"data",
            }
        ],
    )

    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, award_id, bid_token),
        {
            "data": test_draft_claim
        },
    )
    self.assertEqual(response.status, "201 Created")
    complaint = response.json["data"]
    owner_token = response.json["access"]["token"]

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, award_id, complaint["id"], owner_token
        ),
        {"data": {"status": "claim"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"],
        [
            {
                u"description": u"Can add claim only on unsuccessful award of your bid",
                u"location": u"body",
                u"name": u"data",
            }
        ],
    )


def create_tender_award_complaint_not_active(self):
    auth = self.app.authorization
    self.app.authorization = ("Basic", ("token", ""))
    self.app.patch_json(
        "/tenders/{}/awards/{}".format(self.tender_id, self.award_id), {"data": {"status": "cancelled"}}
    )
    self.app.authorization = auth

    response = self.app.get("/tenders/{}/awards".format(self.tender_id))
    award_id = [i["id"] for i in response.json["data"] if i["status"] == "pending"][-1]

    if RELEASE_2020_04_19 > get_now():
        response = self.app.post_json(
            "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, award_id, self.bid_token),
            {
                "data": test_complaint
            },
            status=403,
        )
    else:
        response = self.app.post_json(
            "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, award_id, self.bid_token),
            {
                "data": {
                    "title": "complaint title",
                    "description": "complaint description",
                    "type": "complaint",
                    "author": test_author,
                }
            },
        )
        self.assertEqual(response.status, "201 Created")
        owner_token = response.json["access"]["token"]

        response = self.app.patch_json(
            "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
                self.tender_id, award_id, response.json["data"]["id"], owner_token),
            {"data": {"status": "pending"}},
            status=403
        )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"],
        [
            {
                u"description": u"Complaint submission is allowed only after award activation.",
                u"location": u"body",
                u"name": u"data",
            }
        ],
    )


def create_tender_award_complaint(self):
    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, self.award_id, self.bid_token),
        {
            "data": test_complaint
        },
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    complaint = response.json["data"]
    self.assertEqual(complaint["author"]["name"], test_author["name"])
    self.assertIn("id", complaint)
    self.assertIn(complaint["id"], response.headers["Location"])

    self.set_status("active.awarded")

    response = self.app.get("/tenders/{}".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], "active.awarded")

    self.set_status("unsuccessful")

    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, self.award_id, self.bid_token),
        {"data": test_draft_claim},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(
        response.json["errors"][0]["description"], "Can't add complaint in current (unsuccessful) tender status"
    )


def patch_tender_award_complaint(self):
    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, self.award_id, self.bid_token),
        {"data": test_draft_complaint},
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    complaint = response.json["data"]
    owner_token = response.json["access"]["token"]

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, complaint["id"], self.tender_token
        ),
        {"data": {"status": "cancelled", "cancellationReason": "reason"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"], "Forbidden")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, complaint["id"], owner_token
        ),
        {"data": {"title": "claim title"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.json["data"]["title"], "claim title")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, complaint["id"], owner_token
        ),
        {"data": {"status": "pending"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], "pending")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, complaint["id"], owner_token
        ),
        {"data": {"status": "stopping", "cancellationReason": "reason"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], "stopping")
    self.assertEqual(response.json["data"]["cancellationReason"], "reason")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/some_id".format(self.tender_id, self.award_id),
        {"data": {"status": "resolved", "resolution": "resolution text"}},
        status=404,
    )
    self.assertEqual(response.status, "404 Not Found")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"], [{u"description": u"Not Found", u"location": u"url", u"name": u"complaint_id"}]
    )

    response = self.app.patch_json(
        "/tenders/some_id/awards/some_id/complaints/some_id",
        {"data": {"status": "resolved", "resolution": "resolution text"}},
        status=404,
    )
    self.assertEqual(response.status, "404 Not Found")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"], [{u"description": u"Not Found", u"location": u"url", u"name": u"tender_id"}]
    )

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, complaint["id"], owner_token
        ),
        {"data": {"status": "cancelled", "cancellationReason": "reason"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"],
                     "Can't update complaint from stopping to cancelled status")

    response = self.app.patch_json(
        "/tenders/{}/awards/some_id/complaints/some_id".format(self.tender_id),
        {"data": {"status": "resolved", "resolution": "resolution text"}},
        status=404,
    )
    self.assertEqual(response.status, "404 Not Found")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"], [{u"description": u"Not Found", u"location": u"url", u"name": u"award_id"}]
    )

    response = self.app.get(
        "/tenders/{}/awards/{}/complaints/{}".format(self.tender_id, self.award_id, complaint["id"])
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], "stopping")
    self.assertEqual(response.json["data"]["cancellationReason"], "reason")

    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, self.award_id, self.bid_token),
        {"data": test_draft_claim},
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    complaint = response.json["data"]
    owner_token = response.json["access"]["token"]

    self.set_status("complete")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, complaint["id"], owner_token
        ),
        {"data": {"status": "claim"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(
        response.json["errors"][0]["description"], "Can't update complaint in current (complete) tender status"
    )


def review_tender_award_complaint(self):
    for status in ["invalid", "stopped", "declined", "satisfied"]:
        self.app.authorization = ("Basic", ("broker", ""))
        response = self.app.post_json(
            "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, self.award_id, self.bid_token),
            {
                "data": test_complaint
            },
        )
        self.assertEqual(response.status, "201 Created")
        self.assertEqual(response.content_type, "application/json")
        complaint = response.json["data"]
        now = get_now()

        if RELEASE_2020_04_19 < now:
            self.assertEqual(response.json["data"]["status"], "draft")
            owner_token = response.json["access"]["token"]

            response = self.app.patch_json(
                "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
                    self.tender_id, self.award_id, complaint["id"], owner_token),
                {"data": {"status": "pending"}},
            )
            self.assertEqual(response.status, "200 OK")
            self.assertEqual(response.content_type, "application/json")
            self.assertEqual(response.json["data"]["status"], "pending")

        self.app.authorization = ("Basic", ("reviewer", ""))
        response = self.app.patch_json(
            "/tenders/{}/awards/{}/complaints/{}".format(self.tender_id, self.award_id, complaint["id"]),
            {"data": {"decision": "{} complaint".format(status), "rejectReasonDescription": "reject reason"}},
        )
        self.assertEqual(response.status, "200 OK")
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.json["data"]["decision"], "{} complaint".format(status))
        self.assertEqual(response.json["data"]["rejectReasonDescription"], "reject reason")

        if status in ["declined", "satisfied", "stopped"]:
            data = {"status": "accepted"}
            if RELEASE_2020_04_19 < now:
                data.update({
                    "reviewDate": now.isoformat(),
                    "reviewPlace": "some",
                })
            response = self.app.patch_json(
                "/tenders/{}/awards/{}/complaints/{}".format(self.tender_id, self.award_id, complaint["id"]),
                {"data": data},
            )
            self.assertEqual(response.status, "200 OK")
            self.assertEqual(response.content_type, "application/json")
            self.assertEqual(response.json["data"]["status"], "accepted")
            if RELEASE_2020_04_19 < now:
                self.assertEqual(response.json["data"]["reviewPlace"], "some")
                self.assertEqual(response.json["data"]["reviewDate"], now.isoformat())

            now = get_now()
            data = {"decision": "accepted:{} complaint".format(status)}
            if RELEASE_2020_04_19 > now:
                data.update({
                    "reviewDate": now.isoformat(),
                    "reviewPlace": "some",
                })
            response = self.app.patch_json(
                "/tenders/{}/awards/{}/complaints/{}".format(self.tender_id, self.award_id, complaint["id"]),
                {"data": data},
            )
            self.assertEqual(response.status, "200 OK")
            self.assertEqual(response.content_type, "application/json")
            self.assertEqual(response.json["data"]["decision"], "accepted:{} complaint".format(status))
            if RELEASE_2020_04_19 > now:
                self.assertEqual(response.json["data"]["reviewPlace"], "some")
                self.assertEqual(response.json["data"]["reviewDate"], now.isoformat())

            self.app.authorization = ("Basic", ("token", ""))
            response = self.app.patch_json(
                "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, self.award_id, self.tender_token),
                {"data": {"status": "active", "qualified": True, "eligible": True}},
                status=403,
            )
            self.assertEqual(response.status, "403 Forbidden")
            self.assertEqual(response.content_type, "application/json")
            self.assertEqual(response.json["errors"][0]["description"], "Can't update award with accepted complaint")

        self.app.authorization = ("Basic", ("reviewer", ""))
        now = get_now()
        data = {"status": status}
        if RELEASE_2020_04_19 < now:
            if status in ["invalid", "stopped"]:
                data.update({
                    "rejectReason": "tenderCancelled",
                    "rejectReasonDescription": "reject reason description"
                })
        response = self.app.patch_json(
            "/tenders/{}/awards/{}/complaints/{}".format(self.tender_id, self.award_id, complaint["id"]),
            {"data": data},
        )
        self.assertEqual(response.status, "200 OK")
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.json["data"]["status"], status)


def review_tender_award_stopping_complaint(self):
    now = get_now()
    if RELEASE_2020_04_19 > now:
        statuses = ["satisfied", "stopped", "declined", "mistaken", "invalid"]
    else:
        statuses = ["satisfied", "declined", "invalid"]
    for status in statuses:
        self.app.authorization = ("Basic", ("broker", ""))
        response = self.app.post_json(
            "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, self.award_id, self.bid_token),
            {
                "data": test_complaint
            },
        )
        self.assertEqual(response.status, "201 Created")
        self.assertEqual(response.content_type, "application/json")
        complaint = response.json["data"]
        owner_token = response.json["access"]["token"]

        url_patch_complaint = "/tenders/{}/awards/{}/complaints/{}".format(
            self.tender_id, self.award_id, complaint["id"]
        )

        if RELEASE_2020_04_19 < now:
            self.assertEqual(response.json["data"]["status"], "draft")
            owner_token = response.json["access"]["token"]

            response = self.app.patch_json(
                "{}?acc_token={}".format(url_patch_complaint, owner_token),
                {"data": {"status": "pending"}},
            )
            self.assertEqual(response.status, "200 OK")
            self.assertEqual(response.content_type, "application/json")
            self.assertEqual(response.json["data"]["status"], "pending")

        response = self.app.patch_json(
            "{}?acc_token={}".format(url_patch_complaint, owner_token),
            {"data": {"status": "stopping", "cancellationReason": "reason"}},
        )
        self.assertEqual(response.status, "200 OK")
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.json["data"]["status"], "stopping")
        self.assertEqual(response.json["data"]["cancellationReason"], "reason")

        self.app.authorization = ("Basic", ("reviewer", ""))
        now = get_now()
        data = {"decision": "decision", "status": status}
        if RELEASE_2020_04_19 < now:
            if status in ["invalid", "stopped"]:
                data.update({
                    "rejectReason": "tenderCancelled",
                    "rejectReasonDescription": "reject reason description"
                })
        response = self.app.patch_json(url_patch_complaint, {"data": data})
        self.assertEqual(response.status, "200 OK")
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.json["data"]["status"], status)
        self.assertEqual(response.json["data"]["decision"], "decision")


def review_tender_award_claim(self):
    for status in ["invalid", "resolved", "declined"]:
        self.app.authorization = ("Basic", ("token", ""))
        response = self.app.post_json(
            "/tenders/{}/awards/{}/complaints".format(self.tender_id, self.award_id),
            {
                "data": test_claim
            },
        )
        self.assertEqual(response.status, "201 Created")
        self.assertEqual(response.content_type, "application/json")
        complaint = response.json["data"]
        complaint_token = response.json["access"]["token"]

        self.app.authorization = ("Basic", ("broker", ""))
        response = self.app.patch_json(
            "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
                self.tender_id, self.award_id, complaint["id"], self.tender_token
            ),
            {
                "data": {
                    "status": "answered",
                    "resolutionType": status,
                    "resolution": "resolution text for {} status".format(status),
                }
            },
        )
        self.assertEqual(response.status, "200 OK")
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.json["data"]["resolutionType"], status)

        self.app.authorization = ("Basic", ("token", ""))
        response = self.app.patch_json(
            "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
                self.tender_id, self.award_id, complaint["id"], complaint_token
            ),
            {"data": {"satisfied": "i" in status}},
        )
        self.assertEqual(response.status, "200 OK")
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.json["data"]["satisfied"], "i" in status)


# TenderLotAwardComplaintResourceTest


def create_tender_lot_award_complaint(self):
    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, self.award_id, self.bid_token),
        {
            "data": test_complaint
        },
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    complaint = response.json["data"]
    self.assertEqual(complaint["author"]["name"], test_organization["name"])
    self.assertIn("id", complaint)
    self.assertIn(complaint["id"], response.headers["Location"])

    self.set_status("active.awarded")

    response = self.app.get("/tenders/{}".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], "active.awarded")

    self.set_status("unsuccessful")

    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, self.award_id, self.bid_token),
        {"data": test_draft_claim},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(
        response.json["errors"][0]["description"], "Can't add complaint in current (unsuccessful) tender status"
    )


def patch_tender_lot_award_complaint(self):
    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, self.award_id, self.bid_token),
        {"data": test_draft_complaint},
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    complaint = response.json["data"]
    owner_token = response.json["access"]["token"]

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, complaint["id"], owner_token
        ),
        {"data": {"status": "pending"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], "pending")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, complaint["id"], owner_token
        ),
        {"data": {"status": "stopping", "cancellationReason": "reason"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], "stopping")
    self.assertEqual(response.json["data"]["cancellationReason"], "reason")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/some_id?acc_token={}".format(self.tender_id, self.award_id, owner_token),
        {"data": {"status": "resolved", "resolution": "resolution text"}},
        status=404,
    )
    self.assertEqual(response.status, "404 Not Found")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"], [{u"description": u"Not Found", u"location": u"url", u"name": u"complaint_id"}]
    )

    response = self.app.patch_json(
        "/tenders/some_id/awards/some_id/complaints/some_id",
        {"data": {"status": "resolved", "resolution": "resolution text"}},
        status=404,
    )
    self.assertEqual(response.status, "404 Not Found")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"], [{u"description": u"Not Found", u"location": u"url", u"name": u"tender_id"}]
    )

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, complaint["id"], owner_token
        ),
        {"data": {"status": "cancelled", "cancellationReason": "reason"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"],
                     "Can't update complaint from stopping to cancelled status")

    response = self.app.patch_json(
        "/tenders/{}/awards/some_id/complaints/some_id?acc_token={}".format(self.tender_id, owner_token),
        {"data": {"status": "resolved", "resolution": "resolution text"}},
        status=404,
    )
    self.assertEqual(response.status, "404 Not Found")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(
        response.json["errors"], [{u"description": u"Not Found", u"location": u"url", u"name": u"award_id"}]
    )

    response = self.app.get(
        "/tenders/{}/awards/{}/complaints/{}".format(self.tender_id, self.award_id, complaint["id"])
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], "stopping")
    self.assertEqual(response.json["data"]["cancellationReason"], "reason")

    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(self.tender_id, self.award_id, self.bid_token),
        {"data": test_draft_claim},
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    complaint = response.json["data"]
    owner_token = response.json["access"]["token"]

    self.set_status("complete")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, complaint["id"], owner_token
        ),
        {"data": {"status": "claim"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(
        response.json["errors"][0]["description"], "Can't update complaint in current (complete) tender status"
    )


# Tender2LotAwardComplaintResourceTest


def create_tender_lots_award_complaint(self):
    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(
            self.tender_id, self.award_id, self.initial_bids_tokens[self.initial_bids[0]["id"]]
        ),
        {
            "data": test_complaint
        },
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    complaint = response.json["data"]
    owner_token = response.json["access"]["token"]
    self.assertEqual(complaint["author"]["name"], test_organization["name"])
    self.assertIn("id", complaint)
    self.assertIn(complaint["id"], response.headers["Location"])

    if RELEASE_2020_04_19 < get_now():
        self.assertEqual(response.json["data"]["status"], "draft")

        response = self.app.patch_json(
            "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
                self.tender_id, self.award_id, complaint["id"], owner_token),
            {"data": {"status": "pending"}},
        )
        self.assertEqual(response.status, "200 OK")
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.json["data"]["status"], "pending")

    # set complaint status to stopping to be able to cancel the lot
    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, complaint["id"], owner_token
        ),
        {"data": {
            "status": "stopping",
            "cancellationReason": "want this test to pass",
        }},
    )
    assert response.status_code == 200

    self.set_status("active.awarded")

    response = self.app.get("/tenders/{}".format(self.tender_id))
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["status"], "active.awarded")

    cancellation = dict(**test_cancellation)
    cancellation.update({
        "status": "active",
        "cancellationOf": "lot",
        "relatedLot": self.initial_lots[0]["id"],
    })
    response = self.app.post_json(
        "/tenders/{}/cancellations?acc_token={}".format(self.tender_id, self.tender_token),
        {"data": cancellation},
    )
    self.assertEqual(response.status, "201 Created")
    cancellation_id = response.json["data"]["id"]

    if RELEASE_2020_04_19 < get_now():
        activate_cancellation_after_2020_04_19(self, cancellation_id)

    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(
            self.tender_id, self.award_id, self.initial_bids_tokens[self.initial_bids[0]["id"]]
        ),
        {"data": test_draft_claim},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"], "Can add complaint only in active lot status")


def patch_tender_lots_award_complaint(self):
    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(
            self.tender_id, self.award_id, self.initial_bids_tokens[self.initial_bids[0]["id"]]
        ),
        {"data": test_draft_claim},
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    complaint = response.json["data"]
    owner_token = response.json["access"]["token"]

    with mock.patch("openprocurement.tender.core.validation.RELEASE_2020_04_19", get_now() - timedelta(days=1)):
        response = self.app.patch_json(
            "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
                self.tender_id, self.award_id, complaint["id"], owner_token
            ),
            {"data": {"status": "pending"}},
            status=403
        )
        self.assertEqual(
            response.json,
            {"status": "error", "errors": [
                {"location": "body", "name": "data", "description": "Can't update claim to complaint"}]}
        )

    with mock.patch("openprocurement.tender.core.validation.RELEASE_2020_04_19", get_now() + timedelta(days=1)):
        self.app.patch_json(
            "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
                self.tender_id, self.award_id, complaint["id"], owner_token
            ),
            {"data": {"status": "pending"}},
        )
        # set complaint status to stopping to be able to cancel the lot
        response = self.app.patch_json(
            "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
                self.tender_id, self.award_id, complaint["id"], owner_token
            ),
            {"data": {
                "status": "stopping",
                "cancellationReason": "want this test to pass",
            }},
        )
        assert response.status_code == 200

    response = self.app.post_json(
        "/tenders/{}/awards/{}/complaints?acc_token={}".format(
            self.tender_id, self.award_id, self.initial_bids_tokens[self.initial_bids[0]["id"]]
        ),
        {"data": test_draft_claim},
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    complaint = response.json["data"]
    owner_token = response.json["access"]["token"]

    cancellation = dict(**test_cancellation)
    cancellation.update({
        "status": "active",
        "cancellationOf": "lot",
        "relatedLot": self.initial_lots[0]["id"],
    })
    response = self.app.post_json(
        "/tenders/{}/cancellations?acc_token={}".format(self.tender_id, self.tender_token),
        {"data": cancellation},
    )
    self.assertEqual(response.status, "201 Created")
    cancellation_id = response.json["data"]["id"]

    if RELEASE_2020_04_19 < get_now():
        activate_cancellation_after_2020_04_19(self, cancellation_id)

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, complaint["id"], owner_token
        ),
        {"data": {"status": "pending"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"], "Can update complaint only in active lot status")


# TenderAwardComplaintDocumentResourceTest


def patch_tender_award_complaint_document(self):
    response = self.app.post(
        "/tenders/{}/awards/{}/complaints/{}/documents?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, self.complaint_owner_token
        ),
        upload_files=[("file", "name.doc", "content")],
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    doc_id = response.json["data"]["id"]
    self.assertIn(doc_id, response.headers["Location"])

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.tender_token
        ),
        {"data": {"description": "document description"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"], "Can update document only author")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.complaint_owner_token
        ),
        {"data": {"description": "document description"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(doc_id, response.json["data"]["id"])

    response = self.app.get(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id
        )
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(doc_id, response.json["data"]["id"])
    self.assertEqual("document description", response.json["data"]["description"])

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, self.complaint_owner_token
        ),
        {"data": {"status": "pending"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.json["data"]["status"], "pending")

    response = self.app.put(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.complaint_owner_token
        ),
        "content",
        content_type="application/msword",
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")

    self.set_status("complete")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.complaint_owner_token
        ),
        {"data": {"description": "document description"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(
        response.json["errors"][0]["description"], "Can't update document in current (complete) tender status"
    )


# Tender2LotAwardComplaintDocumentResourceTest


def put_tender_lots_award_complaint_document(self):
    response = self.app.post(
        "/tenders/{}/awards/{}/complaints/{}/documents?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, self.complaint_owner_token
        ),
        upload_files=[("file", "name.doc", "content")],
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    doc_id = response.json["data"]["id"]
    self.assertIn(doc_id, response.headers["Location"])

    response = self.app.put(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.complaint_owner_token
        ),
        status=404,
        upload_files=[("invalid_name", "name.doc", "content")],
    )
    self.assertEqual(response.status, "404 Not Found")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["status"], "error")
    self.assertEqual(response.json["errors"], [{u"description": u"Not Found", u"location": u"body", u"name": u"file"}])

    response = self.app.put(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.tender_token
        ),
        upload_files=[("file", "name.doc", "content2")],
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"], "Can update document only author")

    response = self.app.put(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.complaint_owner_token
        ),
        upload_files=[("file", "name.doc", "content2")],
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(doc_id, response.json["data"]["id"])
    key = response.json["data"]["url"].split("?")[-1]

    response = self.app.get(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?{}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, key
        )
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/msword")
    self.assertEqual(response.content_length, 8)
    self.assertEqual(response.body, "content2")

    response = self.app.get(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id
        )
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(doc_id, response.json["data"]["id"])
    self.assertEqual("name.doc", response.json["data"]["title"])

    response = self.app.put(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.complaint_owner_token
        ),
        "content3",
        content_type="application/msword",
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(doc_id, response.json["data"]["id"])
    key = response.json["data"]["url"].split("?")[-1]

    response = self.app.get(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?{}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, key
        )
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/msword")
    self.assertEqual(response.content_length, 8)
    self.assertEqual(response.body, "content3")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, self.complaint_owner_token
        ),
        {"data": {"status": "pending"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.json["data"]["status"], "pending")

    response = self.app.put(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.complaint_owner_token
        ),
        "content",
        content_type="application/msword",
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")

    # set complaint status stopping to be able to cancel the lot
    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, self.complaint_owner_token
        ),
        {"data": {
            "status": "stopping",
            "cancellationReason": "want this test to pass",
        }},
    )
    assert response.status_code == 200

    cancellation = dict(**test_cancellation)
    cancellation.update({
        "status": "active",
        "cancellationOf": "lot",
        "relatedLot": self.initial_lots[0]["id"],
    })
    response = self.app.post_json(
        "/tenders/{}/cancellations?acc_token={}".format(self.tender_id, self.tender_token),
        {"data": cancellation},
    )
    self.assertEqual(response.status, "201 Created")
    cancellation_id = response.json["data"]["id"]

    if RELEASE_2020_04_19 < get_now():
        activate_cancellation_after_2020_04_19(self, cancellation_id)

    response = self.app.put(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.complaint_owner_token
        ),
        upload_files=[("file", "name.doc", "content3")],
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"], "Can update document only in active lot status")


def patch_tender_lots_award_complaint_document(self):
    response = self.app.post(
        "/tenders/{}/awards/{}/complaints/{}/documents?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, self.complaint_owner_token
        ),
        upload_files=[("file", "name.doc", "content")],
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    doc_id = response.json["data"]["id"]
    self.assertIn(doc_id, response.headers["Location"])

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.tender_token
        ),
        {"data": {"description": "document description"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"], "Can update document only author")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.complaint_owner_token
        ),
        {"data": {"description": "document description"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(doc_id, response.json["data"]["id"])

    response = self.app.get(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id
        )
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(doc_id, response.json["data"]["id"])
    self.assertEqual("document description", response.json["data"]["description"])

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, self.complaint_owner_token
        ),
        {"data": {"status": "pending"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.json["data"]["status"], "pending")

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.complaint_owner_token
        ),
        {"data": {"description": "document description2"}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["data"]["description"], "document description2")

    # set complaint status stopping to be able to cancel the lot
    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, self.complaint_owner_token
        ),
        {"data": {
            "status": "stopping",
            "cancellationReason": "want this test to pass",
        }},
    )
    assert response.status_code == 200

    cancellation = dict(**test_cancellation)
    cancellation.update({
        "status": "active",
        "cancellationOf": "lot",
        "relatedLot": self.initial_lots[0]["id"],
    })
    response = self.app.post_json(
        "/tenders/{}/cancellations?acc_token={}".format(self.tender_id, self.tender_token),
        {"data": cancellation},
    )
    self.assertEqual(response.status, "201 Created")
    cancellation_id = response.json["data"]["id"]

    if RELEASE_2020_04_19 < get_now():
        activate_cancellation_after_2020_04_19(self, cancellation_id)

    response = self.app.patch_json(
        "/tenders/{}/awards/{}/complaints/{}/documents/{}?acc_token={}".format(
            self.tender_id, self.award_id, self.complaint_id, doc_id, self.complaint_owner_token
        ),
        {"data": {"description": "document description"}},
        status=403,
    )
    self.assertEqual(response.status, "403 Forbidden")
    self.assertEqual(response.content_type, "application/json")
    self.assertEqual(response.json["errors"][0]["description"], "Can update document only in active lot status")


def tender_award_complaint_period(self):
    auth = self.app.authorization
    self.app.authorization = ("Basic", ("token", ""))
    response = self.app.post_json(
        "/tenders/{}/awards".format(self.tender_id),
        {
            "data": {
                "suppliers": [test_organization],
                "status": u"pending",
                "bid_id": self.initial_bids[0]["id"],
                "value": {"amount": 500},
            }
        },
    )
    self.assertEqual(response.status, "201 Created")
    self.assertEqual(response.content_type, "application/json")
    award_id = response.json["data"]["id"]

    self.app.authorization = auth
    response = self.app.patch_json(
        "/tenders/{}/awards/{}?acc_token={}".format(self.tender_id, award_id, self.tender_token),
        {"data": {"status": "active", "qualified": True, "eligible": True}},
    )
    self.assertEqual(response.status, "200 OK")
    self.assertEqual(response.content_type, "application/json")
    award = response.json["data"]

    start = parse_date(award["complaintPeriod"]["startDate"])
    end = parse_date(award["complaintPeriod"]["endDate"])
    delta = end - start
    self.assertEqual(delta.days, 0 if SANDBOX_MODE else STAND_STILL_TIME.days)
