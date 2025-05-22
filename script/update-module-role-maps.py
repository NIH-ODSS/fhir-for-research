#!/usr/bin/env python
#
# USAGE:
#   uv run python ./update-module-role-maps.py
#
# This script does 3 things:
# 1. parses sidebar from _quarto.yml for an ordered list of modules/workshops/webinars
# 2. parses roles from the frontmatter of all *.qmd files in directories and sub-directories (but not sub-sub-directories)
# 3. writes modules/mappings.js with all the encoded information. Then scripts.html uses the info for website features
#
# Example roles frontmatter:
# ---
# title: "FHIR from 1,000 Feet"
#
# roles:
#   - Investigator
#   - Informaticist
#   - Software Engineer
#   - Clinician Scientist/Trainee
# ---
#
# See mappings.js encoding format.
# See scripts.html for features and feature hooks.

import os
import glob
import yaml
import json
from collections.abc import Iterable


# Set root project path
root_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Define the role to slug mapping
role_mapping = {
    "Investigator": "investigator",
    "Research Leaders": "research-leader",
    "Informaticist": "informaticist",
    "Software Engineer": "software-engineer",
    "Clinician Scientist/Trainee": "clinician-scientist"
}

# Define the role module map
role_module_map = []

# Helpers
def flatten(irregular_array):
    flattened = []

    def _flatten(item):
        if isinstance(item, (list, tuple)):
            for sub_item in item:
                _flatten(sub_item)
        elif isinstance(item, set):
            flattened.append(item)  # Preserve the set as-is
        elif isinstance(item, dict):
            flattened.append(item)  # Preserve the dictionary as-is
        else:
            flattened.append(item)

    _flatten(irregular_array)
    return flattened

# Read in the _quarto.yml file
quarto_file = os.path.join(root_path, "_quarto.yml")
with open(quarto_file, "r") as f:
    try:
        quarto_yaml = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(e)

# Collapse sidebar down to just the filenames so we can get the ordering
a = [menu['contents'] for menu in quarto_yaml['website']['sidebar']]
a = flatten(a)
b = [x['contents'] for x in a if type(x) is dict and 'contents' in x]
b = flatten(b)
c = [x if type(x) is dict else {'file': x} for x in b]
c = flatten(c)
d = [x['contents'] if type(x) is dict and 'contents' in x else x for x in c] # Sub-sub levels need to be replaced and collapsed.
d = flatten(d)
e = [x['file'] if type(x) is dict else x for x in d]
e = flatten(e)
ordering = {}
for x in e:
    if x != "null" and x is not None:
        ordering[x.replace('.qmd', '')] = {"slug": x}

for pos, k in enumerate(ordering.keys()):
    ordering[k]['position'] = pos


# Loop through each *.qmd file
searchable_paths = glob.glob(os.path.join(root_path, "**/*.qmd")) + glob.glob(os.path.join(root_path, "**/**/*.qmd"))

for filename in searchable_paths:

    module_slug = os.path.splitext(os.path.relpath(filename, root_path))[0]

    # Skip file if not in _quarto.yml sidebar
    if module_slug not in ordering:
        continue

    with open(filename, "r") as f:
        # Read the file content
        content = f.read()

        # Parse the YAML frontmatter
        _, frontmatter, markdown = content.split("---", 2)
        frontmatter = yaml.safe_load(frontmatter.strip())

        # Extract the roles from the frontmatter
        roles = frontmatter.get("roles")

        # If the roles exist, add the filename to the corresponding role in the role module map
        if roles:
            for role in roles:
                role_slug = role_mapping.get(role)
                if role_slug:
                    existing_role = next(
                        (r for r in role_module_map if r["role"] == role_slug),
                        None)
                    text = ordering[module_slug].get('text', frontmatter['title'])
                    if text == "Introduction":
                        text = frontmatter['title']
                    entry = {
                        "slug": module_slug,
                        "position": ordering[module_slug]['position'],
                        "text": text
                    }
                    if not existing_role:
                        role_module_map.append({
                            "role": role_slug,
                            "modules": [entry]
                        })
                    else:
                        existing_role["modules"].append(entry)

# Sort the role module map by role
role_module_map = sorted(role_module_map, key=lambda r: r["role"])

# Sort within roles by position
for m in role_module_map:
    m['modules'] = sorted(m['modules'], key=lambda r: r["position"])

# Convert the role module map to a JavaScript variable
js_var = "const role_module_map = " + json.dumps(role_module_map, indent=2) + ";"

# Write the JavaScript variable to mappings.js
with open(os.path.join(root_path, "modules", "mappings.js"), "w") as f:
    f.write(js_var)
