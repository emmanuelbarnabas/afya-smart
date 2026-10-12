#!/usr/bin/env bash
# Push historia safi (1 commit, bila pointer za AI) kwenye GitLab ya Emmanuel.
# Hatua: GitLab → Settings → Access Tokens → weka token (scope: write_repository),
# kisha badilisha TOKEN na NAMBA_HAPA (namespace/project) chini, na endesha:
#   ./push-gitlab.sh
set -e
TOKEN="BADILISHA_TOKEN_HAPA"
NAMBA="BADILISHA_NAMESPACE/afya-smart"   # mf: emmanuelb/afya-smart
cd /tmp/afya-clean
git push -u "http://oauth2:${TOKEN}@102.223.8.140:9000/${NAMBA}.git" main
