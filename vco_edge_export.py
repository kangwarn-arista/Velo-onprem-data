import json
import urllib3
import requests
import pandas as pd

from dotenv import load_dotenv
from datetime import datetime
from requests.structures import CaseInsensitiveDict
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()

# Load .env file
load_dotenv()

# Read variables from .env
token = os.getenv("VCO_TOKEN")
vco_url = os.getenv("VCO_URL")

OUTPUT_XLSX = "edges_output.xlsx"


def api_call(method, params):

    headers = CaseInsensitiveDict()
    headers["Authorization"] = token
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    data = {
        "id": 0,
        "jsonrpc": "2.0",
        "method": method,
        "params": params
    }

    try:

        resp = requests.post(
            vco_url,
            headers=headers,
            data=json.dumps(data),
            verify=False
        )

        return resp.json()

    except Exception as e:

        print(f"API Error: {e}")
        return {}


def get_enterprise_ids():

    method = "enterprise/getEnterprisesWithProperty"

    params = {
        "name": "vco.enterprise.edgeImageManagement.enable",
        "value": "true"
    }

    parsed = api_call(method, params)

    return [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "logicalId": item.get("logicalId", "")
        }
        for item in parsed.get("result", [])
    ]


def get_enterprise_details(ent_id):

    method = "enterprise/getEnterprise"

    params = {
        "id": ent_id,
        "with": [
            "enterpriseProxy"
        ]
    }

    return api_call(method, params)


def get_edges(ent):

    method = "enterprise/getEnterpriseEdgeList"

    params = {
        "enterpriseId": ent["id"],
        "with": [
            "site",
            "ha",
            "configuration",
            "recentLinks",
            "cloudServices",
            "nvsFromEdge",
            "vnfs",
            "certificateSummary",
            "secureDeviceSecrets"
        ],
        "sortBy": [
            {
                "attribute": "edgeState",
                "type": "ASC"
            }
        ],
        "_filterSpec": True
    }

    return api_call(method, params)


def get_edge_licenses(ent_id):

    method = "license/getEnterpriseEdgeLicenses"

    params = {
        "enterpriseId": ent_id
    }

    return api_call(method, params)


def safe_get(d, *keys):

    for key in keys:

        if isinstance(d, dict):
            d = d.get(key, "")
        else:
            return ""

    return d if d is not None else ""


def format_date(date_string):

    if not date_string:
        return ""

    try:

        dt = datetime.strptime(
            date_string,
            "%Y-%m-%dT%H:%M:%S.000Z"
        )

        return dt.strftime("%m/%d/%y")

    except Exception:

        return date_string


def clean_vco_url(url):

    url = url.replace("https://", "")
    url = url.replace("http://", "")
    url = url.replace("/portal/", "")
    url = url.replace("/portal", "")

    return url.rstrip("/")


if __name__ == "__main__":

    # Validate .env variables
    if not token:

        print("ERROR: VCO_TOKEN not found in .env")
        exit(1)

    if not vco_url:

        print("ERROR: VCO_URL not found in .env")
        exit(1)

    output_rows = []

    cleaned_vco_url = clean_vco_url(vco_url)

    enterprise_ids = get_enterprise_ids()

    print(f"Found {len(enterprise_ids)} enterprises")

    for ent in enterprise_ids:

        print(
            f"\nFetching enterprise details: "
            f"{ent['name']} (id={ent['id']})"
        )

        # Enterprise Details
        ent_details = get_enterprise_details(ent["id"])

        ent_result = ent_details.get("result", {})

        partner_name = safe_get(
            ent_result,
            "enterpriseProxy",
            "name"
        )

        print(f"Partner Name: {partner_name}")

        # Licenses
        print("Fetching licenses...")

        license_response = get_edge_licenses(ent["id"])

        licenses = license_response.get("result", [])

        # Build lookup:
        # license.id -> sku
        license_lookup = {}

        for lic in licenses:

            lic_id = lic.get("id")

            if lic_id is not None:

                license_lookup[lic_id] = lic.get(
                    "sku",
                    ""
                )

        print(f"Licenses Found: {len(license_lookup)}")

        # Edges
        print("Fetching edges...")

        edges = get_edges(ent)

        edge_data = edges.get("result", {}).get("data", [])

        print(f"Edges Found: {len(edge_data)}")

        for edge in edge_data:

            # Match edge.id -> license.id
            edge_id = edge.get("id")

            edge_license_sku = license_lookup.get(
                edge_id,
                ""
            )

            row = {

                # Extra Fields
                "Serial Number": edge.get(
                    "serialNumber",
                    ""
                ),

                "Edge Logical ID": edge.get(
                    "logicalId",
                    ""
                ),

                "Edge Status": edge.get(
                    "edgeState",
                    ""
                ),

                # Main Fields
                "Edge Activation Date": format_date(
                    edge.get(
                        "activationTime",
                        ""
                    )
                ),

                "Type": "",

                "Name": edge.get(
                    "name",
                    ""
                ),

                "Description": "",

                # Location
                "Country": safe_get(
                    edge,
                    "site",
                    "country"
                ),

                "State": safe_get(
                    edge,
                    "site",
                    "state"
                ),

                "City": safe_get(
                    edge,
                    "site",
                    "city"
                ),

                # HA
                "HA Serial Number": edge.get(
                    "haSerialNumber",
                    ""
                ),

                # Hardware
                "Model Number": edge.get(
                    "modelNumber",
                    ""
                ),

                # License
                "License": edge_license_sku,

                "License Set By Maestro": "",

                # VCO
                "VCO URL": cleaned_vco_url,

                "VCO Enterprise Name": ent["name"],

                # UUID
                "Customer UUID": ent["logicalId"],

                # Partner
                "VCO Partner Name": partner_name,

                # Remaining Columns
                "Last Sync": "",
                "Ship Date": "",
                "RMA Date": "",
                "Shipped Order Number": "",
                "Configured BW Total MBPS": "",
                "Bandwidth Over-utilized": "",
                "License Tier Over-utilized": "",
                "EFS": "",
                "Calculated License": ""
            }

            output_rows.append(row)

    if output_rows:

        df = pd.DataFrame(output_rows)

        # Export XLSX
        df.to_excel(
            OUTPUT_XLSX,
            index=False
        )

        print(
            f"\nDone. "
            f"{len(output_rows)} edges written to "
            f"'{OUTPUT_XLSX}'"
        )

    else:

        print("No edge data found.")
