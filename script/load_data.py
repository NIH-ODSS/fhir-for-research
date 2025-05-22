#!/usr/bin/env python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fhirclient",
# ]
# ///
# coding: utf-8

"""
FHIR Bundle Processor and Uploader

This script loads FHIR (Fast Healthcare Interoperability Resources) bundles from JSON files
and uploads them to a FHIR server. It includes functionality to fix references in Synthea-generated
bundles and resolve search parameter references by creating necessary resources.

This version uses PUT instead of POST for updating or creating resources to avoid duplicates.
"""

import re
import uuid
import json
import hashlib
from datetime import datetime
from pathlib import Path
import requests
import os

# Import FHIR client libraries
from fhirclient import client, models
from fhirclient.models.organization import Organization
from fhirclient.models.location import Location
from fhirclient.models.practitioner import Practitioner
from fhirclient.models import bundle as fhir_bundle


# Load the FHIR server URL from environment variables
API_BASE = os.environ.get("FHIR_SERVER")

# Check if the environment variable exists
if API_BASE is None:
    raise ValueError("FHIR_SERVER environment variable is not set")

# Now you can use the FHIR server URL in your script
print(f"Using FHIR server at: {API_BASE}")

# Initialize FHIR client
settings = {
    "app_id": "my_web_app",
    "api_base": API_BASE,
}
smart = client.FHIRClient(settings=settings)


def analyze_references(entry):
    """
    Extract all references from an entry by recursively traversing the object

    Args:
        entry: The FHIR entry to analyze

    Returns:
        list: All reference values found in the entry
    """
    refs = []

    def extract_refs(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "reference" and isinstance(value, str):
                    refs.append(value)
                elif isinstance(value, (dict, list)):
                    extract_refs(value)
        elif isinstance(obj, list):
            for item in obj:
                extract_refs(item)

    extract_refs(entry)
    return refs


def process_synthea_bundle(bundle_data):
    """
    Pre-process a Synthea-generated bundle to fix URN references

    Args:
        bundle_data (dict): The FHIR bundle to process

    Returns:
        dict: The processed bundle with fixed references
    """
    # Track references that need to be fixed
    references_map = {}

    # First pass: build a map of fullUrl to resource ID and type
    for entry in bundle_data.get("entry", []):
        full_url = entry.get("fullUrl", "")
        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")

        if full_url.startswith("urn:uuid:") and resource_type and resource_id:
            # Map the URN to a proper reference
            direct_ref = f"{resource_type}/{resource_id}"
            references_map[full_url] = direct_ref

    print(f"Found {len(references_map)} URN references to fix")

    # Second pass: fix all references
    def fix_references(obj):
        """Recursively update references in an object"""
        if isinstance(obj, dict):
            for key, value in list(obj.items()):
                if key == "reference" and isinstance(value, str):
                    # Fix URN references
                    if value in references_map:
                        obj[key] = references_map[value]
                elif isinstance(value, (dict, list)):
                    fix_references(value)
        elif isinstance(obj, list):
            for item in obj:
                fix_references(item)

    # Update all references in the bundle
    fix_references(bundle_data)

    # Clean up fullUrl fields to avoid confusion
    for entry in bundle_data.get("entry", []):
        if "fullUrl" in entry and entry["fullUrl"].startswith("urn:uuid:"):
            resource = entry.get("resource", {})
            resource_type = resource.get("resourceType")
            resource_id = resource.get("id")
            if resource_type and resource_id:
                entry["fullUrl"] = f"{resource_type}/{resource_id}"

    return bundle_data


def resolve_search_references(bundle_data):
    """
    Replace search parameter references with direct references by creating necessary resources

    Args:
        bundle_data (dict): The FHIR bundle to process

    Returns:
        tuple: (processed bundle, count of created resources)
    """
    # Find all unique search parameter references
    search_refs = {}  # Map of search ref to created resource

    # Create a map of existing resources by identifier
    existing_resources = {}

    # First, index existing resources by their identifiers
    for entry in bundle_data.get("entry", []):
        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType")
        identifiers = resource.get("identifier", [])

        for identifier in identifiers:
            system = identifier.get("system")
            value = identifier.get("value")
            if system and value:
                key = f"{resource_type}?identifier={system}|{value}"
                existing_resources[key] = f"{resource_type}/{resource.get('id')}"

    # Find all search parameter references in the bundle
    for entry in bundle_data.get("entry", []):
        refs = analyze_references(entry)
        for ref in refs:
            if "?" in ref and "identifier=" in ref:
                # Only process search refs not already in existing resources
                if ref not in existing_resources and ref not in search_refs:
                    search_refs[ref] = None

    # Create the missing resources
    new_entries = []
    created = 0

    for ref in search_refs:
        # Parse the reference
        if "?" not in ref or "identifier=" not in ref:
            continue

        parts = ref.split("?")
        resource_type = parts[0]

        # Extract identifier from search parameter
        identifier_parts = parts[1].split("=")
        if len(identifier_parts) != 2:
            continue

        system_value = identifier_parts[1]
        if "|" not in system_value:
            continue

        system, value = system_value.split("|", 1)

        # Create a reproducible ID based on the reference
        hash_input = f"{resource_type}-{system}-{value}"
        resource_id = hashlib.md5(hash_input.encode("utf-8")).hexdigest()

        # Create basic resource structure based on type
        if resource_type == "Practitioner":
            new_resource = {
                "resourceType": "Practitioner",
                "id": resource_id,
                "identifier": [{"system": system, "value": value}],
                "active": True,
                "name": [{"family": "Generated", "given": ["Practitioner"]}],
            }
        elif resource_type == "Organization":
            new_resource = {
                "resourceType": "Organization",
                "id": resource_id,
                "identifier": [{"system": system, "value": value}],
                "active": True,
                "name": "Generated Organization",
            }
        elif resource_type == "Location":
            new_resource = {
                "resourceType": "Location",
                "id": resource_id,
                "identifier": [{"system": system, "value": value}],
                "status": "active",
                "name": "Generated Location",
            }
        else:
            # Skip unsupported resource types
            print(f"Skipping unsupported resource type: {resource_type}")
            continue

        # Add the new resource to our new entries list with PUT request
        new_entries.append(
            {
                "resource": new_resource,
                "request": {"method": "PUT", "url": f"{resource_type}/{resource_id}"},
            }
        )

        # Map this search reference to the direct reference
        direct_ref = f"{resource_type}/{resource_id}"
        search_refs[ref] = direct_ref
        created += 1

    # Update all search parameter references in the bundle
    def update_search_refs(obj):
        """Update all search parameter references in a nested object"""
        if isinstance(obj, dict):
            for key, value in list(obj.items()):
                if key == "reference" and isinstance(value, str):
                    # Check if this is a search parameter reference we're resolving
                    if value in search_refs and search_refs[value] is not None:
                        obj[key] = search_refs[value]
                    # Or check if it's a reference to an existing resource
                    elif value in existing_resources:
                        obj[key] = existing_resources[value]
                elif isinstance(value, (dict, list)):
                    update_search_refs(value)
        elif isinstance(obj, list):
            for item in obj:
                update_search_refs(item)

    # Update all references in the bundle
    update_search_refs(bundle_data)

    # Add the new entries to the beginning of the bundle
    # This ensures they're created before they're referenced
    if new_entries:
        bundle_data["entry"] = new_entries + bundle_data.get("entry", [])

    return bundle_data, created


def process_and_upload_file(
    file_path,
    base_url,
    fix_references=True,
    loinc_code="55232-3",
    saveDebugOutput=False,
):
    """
    Process and upload a FHIR bundle as a single transaction using PUT for update/create

    Args:
        file_path (Path): Path to the FHIR JSON file
        base_url (str): Base URL of the FHIR server
        fix_references (bool): Whether to fix references in the bundle
        loinc_code (str): Required LOINC code (skip files without this code)
        saveDebugOutput (bool): Whether to save processed bundle for debugging

    Returns:
        tuple: (success boolean, error message or None)
    """
    print(f"\nProcessing {file_path.name}...")

    try:
        with open(file_path, "r") as file:
            bundle_data = json.load(file)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in file: {str(e)}")

    # Check if bundle contains required LOINC code
    if loinc_code and loinc_code not in json.dumps(bundle_data):
        raise ValueError(f"Bundle does not contain required LOINC code {loinc_code}")

    num_entries = len(bundle_data.get("entry", []))

    # Apply reference fixing if requested
    if fix_references:
        # Fix URN references
        bundle_data = process_synthea_bundle(bundle_data)

        # Fix search parameter references
        bundle_data, created_resources = resolve_search_references(bundle_data)

        num_entries = len(bundle_data.get("entry", []))

    # Count resource types in the bundle
    resource_types = {}
    for entry in bundle_data.get("entry", []):
        resource_type = entry["resource"]["resourceType"]
        resource_types[resource_type] = resource_types.get(resource_type, 0) + 1

    # Make sure every entry has a request section with PUT method and proper URL
    for entry in bundle_data.get("entry", []):
        if "request" not in entry or entry["request"].get("method") != "PUT":
            resource = entry["resource"]
            resource_type = resource["resourceType"]
            resource_id = resource["id"]

            # Update to use PUT with resource ID in URL
            entry["request"] = {
                "method": "PUT",
                "url": f"{resource_type}/{resource_id}",
            }

    # Save the processed bundle for debugging
    if saveDebugOutput:
        debug_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = Path(f"processed_bundle_{debug_timestamp}.json")
        with open(debug_file, "w") as f:
            json.dump(bundle_data, f, indent=2)
        print(f"Saved processed bundle for debugging to: {debug_file}")

    # Upload the bundle
    try:
        headers = {
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json",
            "Prefer": "return=minimal",  # Minimize response size
        }

        response = requests.post(
            base_url,
            json=bundle_data,
            headers=headers,
            timeout=300,  # 5 minutes timeout for large bundles
        )

        # Check for HTTP errors
        response.raise_for_status()

        print(f"Upload response status: {response.status_code}")
        return True, None

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response status code: {e.response.status_code}")

        # Log detailed error information
        try:
            error_content = e.response.json()
            error_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_file = Path(f"error_{error_timestamp}.json")
            with open(error_file, "w") as f:
                json.dump(error_content, f, indent=2)
            print(f"Error details saved to: {error_file}")

            # Extract and print the main issue
            if "issue" in error_content:
                for issue in error_content["issue"][:3]:  # Show first 3 issues only
                    print(
                        f"- {issue.get('severity', 'error')}: {issue.get('diagnostics', 'Unknown error')}"
                    )
        except (json.JSONDecodeError, KeyError, AttributeError):
            print(f"Failed to parse error response: {e.response.content[:200]}")

        return False, str(e)

    except Exception as e:
        print(f"Unexpected error during upload: {str(e)}")
        return False, str(e)


def run_fhir_upload(
    directory_path, base_url, max_files=5, fix_references=True, loinc_code="55232-3"
):
    """
    Run the FHIR upload process for JSON files in a directory

    Args:
        directory_path (str): Path to directory containing FHIR JSON files
        base_url (str): Base URL of the FHIR server
        max_files (int): Maximum number of files to process
        fix_references (bool): Whether to fix references in bundles
        loinc_code (str): Required LOINC code (skip files without this code)

    Returns:
        tuple: (list of successful files, list of failed files with errors)
    """
    # Path to your FHIR JSON files
    directory = Path(directory_path)

    # Process files
    successful_files = []
    failed_files = []
    processed_count = 0

    print(f"Searching for JSON files in {directory}...")
    json_files = list(directory.glob("*.json"))
    print(f"Found {len(json_files)} JSON files")

    for file_path in json_files:
        if processed_count >= max_files:
            print(f"Reached maximum file limit ({max_files})")
            break

        try:
            # Process and upload file - the LOINC check happens inside this function
            success, error = process_and_upload_file(
                file_path, base_url, fix_references, loinc_code
            )

            processed_count += 1

            if success:
                successful_files.append(file_path.name)
                print(f"Successfully processed {file_path.name}")
            else:
                error_summary = error if error else "Unknown error"
                failed_files.append((file_path.name, error_summary))
                print(f"Failed to process {file_path.name}: {error_summary[:200]}")

        except ValueError as ve:
            # Skip files that don't contain the required LOINC code
            print(f"Skipping {file_path.name}: {str(ve)}")
            continue
        except Exception as e:
            print(f"Error processing {file_path.name}: {str(e)}")
            failed_files.append((file_path.name, str(e)))

    # Print summary
    print("\n======= UPLOAD RESULTS =======")
    print(f"Successfully uploaded files: {len(successful_files)}")
    for file in successful_files:
        print(f"- {file}")

    print(f"\nFailed files: {len(failed_files)}")
    if failed_files:
        for file_name, error in failed_files:
            print(f"- {file_name}: {error[:100]}...")

    return successful_files, failed_files


def test_fhir_connection():
    """
    Test the connection to the FHIR server by requesting Patient resources

    Returns:
        dict: The response from the FHIR server
    """
    # Simple request to test connection
    try:
        patient_bundle = smart.server.request_json("Patient")
        print("FHIR server connection successful")
        return patient_bundle
    except Exception as e:
        print(f"Error connecting to FHIR server: {str(e)}")
        return None


if __name__ == "__main__":
    # Execute code only when running as a script, not when imported

    # Test connection first http://localhost:8080/fhir/Patient
    test_result = test_fhir_connection()

    if test_result is not None:
        # Run the uploader with default settings
        print("\nStarting FHIR bundle upload process...")
        run_fhir_upload("./fhir-data", API_BASE, max_files=5, fix_references=True)
    else:
        print("Aborting due to connection failure.")
        exit(1)
