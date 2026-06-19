import os
from apify_client import ApifyClient

DEFAULT_ACTOR_ID = "PeTP8M7vkdTthJvqk"
DEFAULT_COMPANY_WEBSITE_ACTOR_ID = "UwSdACBp7ymaGUJjS"


def _get_apify_client(apify_token: str | None = None) -> ApifyClient:
    token = apify_token or os.environ.get("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN must be provided via environment or apify_token parameter")
    return ApifyClient(token)


def _run_actor(client: ApifyClient, actor_id: str, run_input: dict):
    run = client.actor(actor_id).call(run_input=run_input)
    dataset_id = None
    if isinstance(run, dict):
        dataset_id = run.get("default_dataset_id") or run.get("defaultDatasetId")
    else:
        dataset_id = getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId", None)
    if not dataset_id:
        raise RuntimeError("Unable to determine Apify dataset ID from run result")
    return list(client.dataset(dataset_id).iterate_items())


def fetch_linkedin_jobs_from_apify(
    query: str,
    location: str,
    jobs_to_fetch: int = 10,
    apify_token: str | None = None,
    actor_id: str = DEFAULT_ACTOR_ID,
):
    client = _get_apify_client(apify_token)
    run_input = {
        "searchUrls": [],
        "query": query,
        "location": location,
        "timePostedRange": "",
        "jobsToFetch": jobs_to_fetch,
        "enrichCompanyDetails": False,
        "contract": False,
        "fullTime": True,
        "partTime": False,
        "temporary": False,
        "volunteer": False,
        "internship": False,
        "internshipLevel": False,
        "entryLevel": False,
        "associate": False,
        "midSeniorLevel": False,
        "director": False,
        "executive": False,
        "onSite": True,
        "remote": False,
        "hybrid": False,
    }
    return _run_actor(client, actor_id, run_input)


def fetch_company_websites_from_apify(
    companies: list[str],
    searches: list | None = None,
    apify_token: str | None = None,
    actor_id: str = DEFAULT_COMPANY_WEBSITE_ACTOR_ID,
):
    client = _get_apify_client(apify_token)
    run_input = {
        "companies": companies,
        "searches": searches if searches is not None else [],
    }
    return _run_actor(client, actor_id, run_input)
