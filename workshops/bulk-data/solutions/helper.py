import requests
import jwt
import datetime
import json
import fhirpathpy
from flatten_json import flatten
from typing import Optional
from collections import defaultdict
import pandas as pd

from rich import print

# Status bars for long-running cels
from tqdm.notebook import trange, tqdm

class BulkDataFetcher:
    def __init__(
        self,
        base_url: str,
        client_id: str,
        private_key: str,
        key_id: str,
        endpoint: Optional[str] = None,
        session: Optional[str] = None
    ):
        self.base_url = base_url
        self.client_id = client_id
        self.private_key = private_key
        self.key_id = key_id

        self.token = None
        self.token_expire_time = None

        if endpoint is None:
            self.endpoint = "Patient"
        else:
            self.endpoint = endpoint


        if session is None:
            self.session = requests.Session()
        else:
            self.session = session

        r = self.session.get(f'{base_url}/.well-known/smart-configuration')
        smart_config = r.json()
        self.token_endpoint = smart_config['token_endpoint']

        self.resource_types = []
        self.fhir_paths = {}

        # Store raw FHIR resource instances; populated as part of get_dataframes()
        self.resources_by_type = {}


    def get_token(self):
        if self.token and datetime.datetime.now() < self.expire_time:
            # the existing token is still valid so use it
            return self.token

        assertion = jwt.encode({
                'iss': self.client_id,
                'sub': self.client_id,
                'aud': self.token_endpoint,
                'exp': int((datetime.datetime.now() + datetime.timedelta(minutes=5)).timestamp())
        }, self.private_key, algorithm='RS384',
        headers={"kid": key_id})

        r = self.session.post(self.token_endpoint, data={
            'scope': 'system/*.read',
            'grant_type': 'client_credentials',
            'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
            'client_assertion': assertion
        })

        token_response = r.json()
        self.token = token_response['access_token']
        self.expire_time = datetime.datetime.now() + datetime.timedelta(seconds=token_response['expires_in'])

        return self.token

    def add_resource_type(self, resource_type: str, fhir_paths = None):
        self.resource_types.append(resource_type)
        if fhir_paths:
            # fhir_paths=[
            #    ("id", "identifier[0].value"),
            #    ("marital_status", "maritalStatus.coding[0].code")
            # ]
            compiled_fhir_paths = [(f[0], fhirpathpy.compile(f[1])) for f in fhir_paths]
            self.fhir_paths[resource_type] = compiled_fhir_paths

    def _invoke_request(self):
        types = ','.join(self.resource_types)
        url = f'{self.base_url}/{self.endpoint}/$export?_type={types}'
        print(f'Fetching from {url}')
        r = self.session.get(url, headers={'Authorization': f'Bearer {self.get_token()}', 'Accept': 'application/fhir+json', 'Prefer': 'respond-async'})

        self.check_url = r.headers['Content-Location']
        return self.check_url

    def _wait_until_ready(self):
        while True:
            r = self.session.get(self.check_url, headers={'Authorization': f'Bearer {self.get_token()}', 'Accept': 'application/fhir+json'})

            # There are three possible options here: http://hl7.org/fhir/uv/bulkdata/export.html#bulk-data-status-request
            # Error = 4xx or 5xx status code
            # In-Progress = 202
            # Complete = 200

            if r.status_code == 200:
                # complete
                response = r.json()
                self.output_files = response['output']
                return self.output_files

            elif r.status_code == 202:
                # in progress
                delay = r.headers['Retry-After']

                sleep(int(delay))

            else:
                raise RuntimeError(r.text)

    def get_dataframes(self):
        self._invoke_request()
        self._wait_until_ready()

        resources_by_type = {}
        self.resources_by_type = {} # Reset store of raw FHIR resources each time this is run

        for output_file in self.output_files:
            download_url = output_file['url']
            resource_type = output_file['type']

            r = self.session.get(download_url, headers={'Authorization': f'Bearer {get_token()}', 'Accept': 'application/fhir+json'})

            ndjson = r.text.strip()

            if resource_type not in resources_by_type:
                resources_by_type[resource_type] = []
                self.resources_by_type[resource_type] = []

            for line in ndjson.split('\n'):
                resource = json.loads(line)

                # Make raw resource instances available for future use
                self.resources_by_type[resource_type].append(resource)

                if resource_type in self.fhir_paths:
                    fhir_paths = self.fhir_paths[resource_type]
                    filtered_resource = {}
                    for f in fhir_paths:
                        fieldname = f[0]
                        func = f[1]
                        filtered_resource[fieldname] = func(resource)

                        if isinstance(filtered_resource[fieldname], list) and len(filtered_resource[fieldname]) == 1:
                            filtered_resource[fieldname] = filtered_resource[fieldname][0]
                    resource = filtered_resource

                resources_by_type[resource_type].append(resource)

        dfs = {}

        for resource_type, resources in resources_by_type.items():
            dfs[resource_type] = pd.json_normalize(list(map(lambda r: flatten(r), resources)))

        return dfs

    def get_example_resource(self, resource_type: str, resource_id: Optional[str] = None):
        if self.resources_by_type is None:
            print("You need to run get_dataframes() first")
            return None

        if resource_type not in self.resources_by_type:
            print(f"{resource_type} not available. Try one of these: {', '.join(self.resources_by_type.keys())}")
            return None

        if resource_id is None:
            return self.resources_by_type[resource_type][0]

        resource = [r for r in self.resources_by_type[resource_type] if r['id'] == resource_id]

        if len(resource) > 0:
            return resource[0]

        print(f"No {resource_type} with id={resource_id} was found.")
        return None

    def reprocess_dataframes(self, fhir_paths):
        return BulkDataFetcher._reprocess_dataframes(self.resources_by_type, fhir_paths)

    @classmethod
    def _reprocess_dataframes(cls, obj_resources_by_type, user_fhir_paths):
        parsed_resources_by_type = defaultdict(list)

        for this_resource_type in obj_resources_by_type.keys():
            if this_resource_type in user_fhir_paths:
                user_fhir_paths[this_resource_type] = [(f[0], fhirpathpy.compile(f[1])) for f in user_fhir_paths[this_resource_type]]
            for resource in obj_resources_by_type[this_resource_type]:
                if this_resource_type in user_fhir_paths:
                    filtered_resource = {}
                    for f in user_fhir_paths[this_resource_type]:
                        fieldname = f[0]
                        func = f[1]
                        filtered_resource[fieldname] = func(resource)

                        if isinstance(filtered_resource[fieldname], list) and len(filtered_resource[fieldname]) == 1:
                            filtered_resource[fieldname] = filtered_resource[fieldname][0]
                    parsed_resources_by_type[this_resource_type].append(filtered_resource)
                else:
                    parsed_resources_by_type[this_resource_type].append(resource)

        dfs = {}

        for t, res in parsed_resources_by_type.items():
            dfs[t] = pd.json_normalize(list(map(lambda r: flatten(r), res)))

        return dfs


class SyntheaDataFetcher:
    def __init__(self, ndjson_file_path):
        self.resources_by_type = {}

        num_lines = sum(1 for line in open(ndjson_file_path,'r'))
        with open(ndjson_file_path, 'r') as file:
            for line in tqdm(file, total=num_lines):
                json_obj = json.loads(line)
                this_resource_type = json_obj['resourceType']
                if this_resource_type not in self.resources_by_type:
                    self.resources_by_type[this_resource_type] = []
                self.resources_by_type[this_resource_type].append(json_obj)

        print("Resources available: ")
        print('\n'.join(['- '+ x for x in self.resources_by_type.keys()]))

    def get_example_resource(self, resource_type: str, resource_id: Optional[str] = None):
        if self.resources_by_type is None:
            print("You need to run get_dataframes() first")
            return None

        if resource_type not in self.resources_by_type:
            print(f"{resource_type} not available. Try one of these: {', '.join(self.resources_by_type.keys())}")
            return None

        if resource_id is None:
            return self.resources_by_type[resource_type][0]

        resource = [r for r in self.resources_by_type[resource_type] if r['id'] == resource_id]

        if len(resource) > 0:
            return resource[0]

        print(f"No {resource_type} with id={resource_id} was found.")
        return None

    def reprocess_dataframes(self, user_fhir_paths):
        return BulkDataFetcher._reprocess_dataframes(self.resources_by_type, user_fhir_paths)
