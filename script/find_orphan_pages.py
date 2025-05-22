import os
import re

# Get a list of all files and their absolute paths
all_files = []
for root, dirs, files in os.walk("."):
    for file in files:
        # process all the qmd files and the site navbar (_quarto.yml)
        if file.endswith(".qmd") or file == "_quarto.yml":
            all_files.append(os.path.abspath(os.path.join(root, file)))

# A regex pattern to match qmd or html links
link_pattern = re.compile(r"\b([-\w/.]*\.(qmd|html))\b")

all_links = []
for file_path in all_files:
    with open(file_path, "r") as file:
        data = file.read()
        links = link_pattern.findall(data)

        # turn relative paths into absolute paths to account for cross-linking at different directory depths
        absolute_links = [
            os.path.abspath(os.path.join(os.path.dirname(file_path), link[0]))
            for link in links
        ]
        all_links.extend(absolute_links)


all_files = [os.path.normpath(f) for f in all_files]
# those links that were html pages post render, replace the extension back with .qmd
all_links = [os.path.normpath(l).replace(".html", ".qmd") for l in all_links]

# Exclude 'index.qmd' and '_quarto.yml' from orphans
exclude_files = [os.path.abspath("./index.qmd"), os.path.abspath("./_quarto.yml")]
all_files = [f for f in all_files if f not in exclude_files]

orphans = set(all_files) - set(all_links)

print("Orphaned QMD files:")
for orphan in sorted(list(orphans)):
    print(orphan)
