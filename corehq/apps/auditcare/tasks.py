import logging

from couchdbkit.ext.django.loading import get_db

from dimagi.utils.couch.database import retry_on_couch_error
from dimagi.utils.dates import force_to_datetime
from dimagi.utils.logging import notify_exception

from corehq.apps.auditcare.models import (
    ACCESS_FAILED,
    ACCESS_LOGIN,
    ACCESS_LOGOUT,
    AccessAudit,
    NavigationEventAudit,
)
from corehq.apps.auditcare.utils.migration import (
    AuditCareMigrationUtil,
    get_formatted_datetime_string,
)
from corehq.util.soft_assert import soft_assert

log = logging.getLogger(__name__)

ACCESS_LOOKUP = {
    "login": ACCESS_LOGIN,
    "logout": ACCESS_LOGOUT,
    "login_failed": ACCESS_FAILED,
}

COUCH_QUERY_LIMIT = 1000


def get_couch_key(time):
    if not time:
        return
    return [time.year, time.month, time.day, time.hour, time.minute, time.second]


def get_migration_key(start_time, end_time):
    return get_formatted_datetime_string(start_time) + '_' + get_formatted_datetime_string(end_time)


@retry_on_couch_error
def _get_couch_docs(start_key, end_key):
    db = get_db("auditcare")
    result = db.view(
        "auditcare/all_events",
        startkey=start_key,
        endkey=end_key,
        reduce=False,
        include_docs=True,
        limit=COUCH_QUERY_LIMIT
    )
    return list(result)


def get_events_from_couch(start_key, end_key):
    navigation_objects = []
    audit_objects = []
    count = 0
    next_start_time = None
    couch_docs = _get_couch_docs(start_key, end_key)
    for result in couch_docs:
        doc = result["doc"]
        try:
            next_start_time = force_to_datetime(doc.get("event_date"))
            kwargs = _pick(doc, ["user", "domain", "ip_address", "session_key",
                                "headers", "status_code", "user_agent"])
            kwargs.update({
                "event_date": next_start_time,
                "couch_id": doc["_id"],
            })

            if doc["doc_type"] == "NavigationEventAudit":
                if NavigationEventAudit.objects.filter(couch_id=doc["_id"]).exists():
                    continue
                kwargs.update(_pick(doc, ["headers", "status_code", "view", "view_kwargs"]))
                path, _, params = doc.get("request_path", "").partition("?")
                kwargs.update({
                    "path": path,
                    "params": params,
                })
                navigation_objects.append(NavigationEventAudit(**kwargs))
            elif doc["doc_type"] == "AccessAudit":
                if AccessAudit.objects.filter(couch_id=doc["_id"]).exists():
                    continue
                kwargs.update(_pick(doc, ["http_accept", "trace_id"]))
                access_type = doc.get('access_type')
                kwargs.update({
                    "access_type": ACCESS_LOOKUP.get(doc.get("access_type")),
                    "path": doc.get("path_info"),
                })
                if access_type == "logout":
                    kwargs.update({"path": "accounts/logout"})
                audit_objects.append(AccessAudit(**kwargs))
            count += 1
        except Exception:
            raise Exception(doc['_id'])
    res_obj = {
        "navigation_events": navigation_objects,
        "audit_events": audit_objects,
        "break_query": count < COUCH_QUERY_LIMIT or not next_start_time,
        "next_start_key": get_couch_key(next_start_time),
        "count": count
    }
    return res_obj


def copy_events_to_sql(start_time, end_time):
    util = AuditCareMigrationUtil()
    print(f"Starting batch: {start_time} - {end_time}")
    key = get_migration_key(start_time, end_time)
    end_key = get_couch_key(end_time)
    start_key = get_couch_key(start_time)
    next_start_key = start_key
    util.log_batch_start(key)
    break_query = False
    count = 0
    try:
        while not break_query:
            events_info = get_events_from_couch(next_start_key, end_key)
            next_start_key = events_info['next_start_key']
            NavigationEventAudit.objects.bulk_create(events_info['navigation_events'], ignore_conflicts=True)
            AccessAudit.objects.bulk_create(events_info['audit_events'], ignore_conflicts=True)
            count += events_info['count']
            break_query = events_info['break_query']
    except Exception as e:
        message = f"Error in copy_events_to_sql on doc {str(e)}"
        notify_exception(None, message=message)
        _soft_assert = soft_assert(to="{}@{}.com".format('aphulera', 'dimagi'), notify_admins=False)
        _soft_assert(False, message)
        util.set_batch_as_errored(key)
        return
    util.set_batch_as_finished(key, count)


def _pick(doc, keys):
    return {key: doc.get(key) for key in keys if doc.get(key)}
