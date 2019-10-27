#!/usr/bin/env bash

set -e
set -x
set -v
set -o pipefail

gcloud pubsub subscriptions create pubsub-webhook-integration-test \
  --topic webhooks

gcloud functions call cloud-build-status --data '{"foo": "bar"}'

gcloud pubsub subscriptions pull pubsub-webhook-integration-test \
  --format json | \
  jq '.[0].message.data' -r | \
    base64 -d | \
      jq -e '.foo == "bar"'
