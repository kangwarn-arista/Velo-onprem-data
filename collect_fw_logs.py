import json
import urllib3
import requests
from requests.structures import CaseInsensitiveDict

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()

token = "Token XXX"
vco_url = "https://vco310-syd1.velocloud.net/api/search/v1"


def api_call(path, params=None):
    headers = CaseInsensitiveDict()
    headers["Authorization"] = token
    headers["Content-Type"] = "application/json"

    url = f"{vco_url}{path}"

    try:
        resp = requests.get(url, headers=headers, params=params, verify=False)

        print(f"Status code : {resp.status_code}")
        print(f"URL called  : {resp.url}")
        print(f"Raw response: {repr(resp.text[:500])}")  # first 500 chars

        if not resp.text.strip():
            print("Empty response body — check URL, token, or endpoint.")
            return None

        return resp.json()
    except Exception as e:
        print(f"Exception: {e}")
        return None


def get_edge_firewall(enterprise_uuid, from_offset=0, size=50, start_time=None, end_time=None):
    path = f"/enterprises/{enterprise_uuid}/edgeFirewall"
    params = {
        "from": from_offset,
        "size": size,
        "startTime": start_time,
        "endTime": end_time,
    }
    params = {k: v for k, v in params.items() if v is not None}

    res = api_call(path, params=params)
    if res:
        print(json.dumps(res, indent=4))


if __name__ == "__main__":
    get_edge_firewall(
        enterprise_uuid="fab4a82c-a82e-4448-8ea5-09744c99db15",
        from_offset=0,
        size=50,
        start_time="2026-05-28T09:50:06.148Z",
        end_time="2026-05-28T21:50:06.148Z",
    )
