from typing import Any, Literal, TypedDict

CIT_SAPJobTitle = TypedDict(
    "CIT_SAPJobTitle", {"id": int, "text": str, "sap_text_sha1": str}
)
CIT_JobTitleLocalization = TypedDict(
    "CIT_JobTitleLocalization", {"short_job_title": str, "full_job_title": str}
)
CIT_JobTitle = TypedDict(
    "CIT_JobTitle",
    {
        "id": int,
        "id_2": str,
        "sap_text_hash": str,
        "localization": dict[str, CIT_JobTitleLocalization],
    },
)
CIT_BoolString = Literal["0", "1"]
CIT_Relation = TypedDict(
    "CIT_Relation",
    {
        "id": int,
        "user_id": str,
        "workplace_id": str,
        "job_title_id": str,
        "default": CIT_BoolString,
        "is_leader": CIT_BoolString,
        "full_time_job": CIT_BoolString,
        "part_time_job": CIT_BoolString,
        "daily_student": CIT_BoolString,
        "external_student": CIT_BoolString,
        "job_type_id": str,
    },
)
CIT_User = TypedDict(
    "CIT_User",
    {
        "id": int,
        "uoc": str,
        "login": str,
        "first_name": str,
        "middle_name": str | None,
        "last_name": str,
        "title_before": str,
        "title_after": str,
    },
)
CIT_WorkplaceLocalization = TypedDict(
    "CIT_WorkplaceLocalization",
    {
        "abbreviation": str,
        "title": str,
    },
)
CIT_Workplace = TypedDict(
    "CIT_Workplace",
    {
        "id": int,
        "parent": str,
        "cdo_id": str,
        "treePath": str,
        "localization": dict[str, CIT_WorkplaceLocalization],
    },
)
CIT_Contact = TypedDict(
    "CIT_Contact",
    {
        "id": int,
        "language": str | None,
        "cdo_id": str,
        "contact_type_id": str,
        "value": Any,
        "workplace_user_id": str,
    },
)
