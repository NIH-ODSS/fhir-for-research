#! /usr/bin/env bash

cd /Users/mmasnick/git/fhir-for-research-public
git merge --squash --allow-unrelated-histories main --strategy-option theirs
git commit -m "$(date)"

cd /Users/mmasnick/git/fhir-for-research-github
git pull /Users/mmasnick/git/fhir-for-research public --allow-unrelated-histories -m "$(date)"
git push