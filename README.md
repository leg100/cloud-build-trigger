# cloud-build-trigger

![Cloud Build](https://storage.googleapis.com/louis-garman-ci-badges/builds/cloud-build-trigger/branches/master.svg)

A Cloud Function trigger for Cloud Build

Massively scale out jjjjjjjjjjjjj

## Requirements

* Github or Bitbucket Cloud
* Google Cloud

## Summary

Google Cloud Build has [build triggers](https://cloud.google.com/cloud-build/docs/running-builds/automate-builds). A trigger runs a build whenever there are changes pushed to a git repository. However, they suffer from several shortcomings. If you're using Github or Bitbucket, then you're required to setup a mirror in Cloud Source Repositories. Setting up that mirror is a manual non-automatible process. There is a Github app that doesn't require a mirror, but this too is a manual process. Build triggers have limited configuration options too.

`cloud-build-trigger` instead is a Cloud Function that performs the same role as build triggers. Because it is a Cloud Function you can automate its deployment. Nor does it require a mirror.

This opens up new possibilities for Cloud Build. You can deploy the function in all your projects and then have it run builds in each respective project.

Fanning out Cloud Build makes good sense. Builds can be run in projects where appropriate. For instance, you can run your dev deployments in your dev project, and your prod deployments in your prod project. IAM permissions can be assigned to the Cloud Build service account restricting access to resources in the projects in which it resides. In this way, the principle of least privilege is adhered to. And this provides for a very scalable CI/CD pipeline system, triggering builds across your Google Cloud organization in response to repository events.

As with build triggers, you need to configure a webhook in your git repository. You'll need to do this for each function. Although this can be automated too, there is another approach: configure just one webhook and point it at another cloud function, [pubsub-webhook](https://github.com/leg100/pubsub-webhook), which propagates the webhook event as a Pub/Sub message. `cloud-build-trigger` functions can then subscribe to these messages. The advantage of this approach is that you're then exposing one webhook to the internet.

## Installation

These instructions apply to both Github and Bitbucket. It's recommended that you set the following environment variables first:

* `GOOGLE_CLOUD_PROJECT`: the project in which cloud resources are created, e.g. `my-uniquely-named-project`
* `CREDENTIALS_BUCKET`: the GCS bucket in which to store encrypted credentials, e.g. `my-uniquely-named-credentials-bucket`
* `BUILD_STATUS_KEYRING`: the name of the KMS keyring, e.g. `production`
* `BUILD_STATUS_KEY`: the name of the KMS key, e.g. `cloud-build-status`

### Setup Cloud Build

Follow these [instructions](https://cloud.google.com/cloud-build/docs/running-builds/automate-builds). Once you've done so, you'll have:

  * A Github or Bitbucket repository mirrored to Cloud Source Repositories
  * A Cloud Build config file (e.g. `cloudbuild.yaml`) in the repository
  * A Cloud Build trigger to run a build when a commit is pushed

Make a note of the Google Cloud project you decide to use. From hereon in, all resources are configured in the context of this project.


### Enable Google Cloud APIs

If you have not previously used Cloud Functions, Cloud KMS, or Cloud Storage, enable the APIs on your Google Cloud Project:

```bash
gcloud services enable \
  cloudfunctions.googleapis.com \
  cloudkms.googleapis.com \
  storage-component.googleapis.com
```

### Create KMS keys

Create KMS keyring and key:

```bash
gcloud kms keyrings create ${BUILD_STATUS_KEYRING} --location global

gcloud kms keys create ${BUILD_STATUS_KEY} \
  --location global \
  --keyring ${BUILD_STATUS_KEYRING} \
  --purpose encryption
```

### Create Storage Bucket

Create Google Cloud Storage bucket in which to store encrypted credentials (the ciphertext):

```bash
gsutil mb gs://${CREDENTIALS_BUCKET}/
```

Next, change the default bucket permissions. By default, anyone with access to the project has access to the data in the bucket. You must do this before storing any data in the bucket!

```bash
gsutil defacl set private gs://${CREDENTIALS_BUCKET}/
```

### Setup Credentials

The function needs credentials with which to authenticate with the Github or Bitbucket API. The credentials need not be the same as that used for mirroring.

Note: this step can be repeated whenever you want to rotate the credentials. There is a make task to perform the rotation: `make rotate`.

#### Github

Nominate a Github user account for this purpose. Create a [personal access token](https://github.com/settings/tokens). Assign it the `repo:status` scope.

Encrypt the username and token and upload the resulting ciphertext to the bucket:

```bash
echo '{"username": "username", "password": "********"}' | \
  gcloud kms encrypt \
  --location global \
  --keyring=${BUILD_STATUS_KEYRING} \
  --key=${BUILD_STATUS_KEY} \
  --ciphertext-file=- \
  --plaintext-file=- | \
  gsutil cp - gs://${CREDENTIALS_BUCKET}/github
```

#### Bitbucket

Nominate a Bitbucket user account for this purpose.  Create an [app password](https://confluence.atlassian.com/bitbucket/app-passwords-828781300.html). Assign it the `repository:read` scope.

Encrypt the username and app password and upload the resulting ciphertext to the bucket:

```bash
echo '{"username": "username", "password": "********"}' | \
  gcloud kms encrypt \
  --location global \
  --keyring=${BUILD_STATUS_KEYRING} \
  --key=${BUILD_STATUS_KEY} \
  --ciphertext-file=- \
  --plaintext-file=- | \
  gsutil cp - gs://${CREDENTIALS_BUCKET}/bitbucket
```

### Configure IAM

Create a new service account for use by the Cloud Function:

```bash
gcloud iam service-accounts create cloud-build-status
```

Grant permissions to read from the bucket:

```bash
gsutil iam ch serviceAccount:cloud-build-status@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com:legacyBucketReader,legacyObjectReader gs://${CREDENTIALS_BUCKET}
```

Grant minimal permissions to decrypt data using the KMS key created above:

```bash
gcloud kms keys add-iam-policy-binding ${BUILD_STATUS_KEY} \
    --location global \
    --keyring ${BUILD_STATUS_KEYRING} \
    --member "serviceAccount:cloud-build-status@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --role roles/cloudkms.cryptoKeyDecrypter
```

The function now has the permissions to both read the ciphertext from the bucket as well as to decrypt the ciphertext.

## Deploy

Deploy the function:

```bash
gcloud functions deploy cloud-build-status \
    --source . \
    --runtime python37 \
    --entry-point build_status \
    --service-account cloud-build-status@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com \
    --set-env-vars KMS_CRYPTO_KEY_ID=projects/${GOOGLE_CLOUD_PROJECT}/locations/global/keyRings/${BUILD_STATUS_KEYRING}/cryptoKeys/${BUILD_STATUS_KEY},CREDENTIALS_BUCKET=${CREDENTIALS_BUCKET} \
    --trigger-topic=cloud-builds
```

## Test

There are `make` tasks for running integration tests against a deployed function:

```bash
make integration # run both github and bitbucket tests
make integration-github # run only github tests
make integration-bitbucket # run only bitbucket tests
```

Ensure the following environment variables are set first, according to whether you're running tests against Github, Bitbucket, or both:

* `BB_REPO`: the name of an existing Bitbucket repository
* `BB_REPO_OWNER`: the owner of an existing Bitbucket repository
* `BB_COMMIT_SHA`: an existing commit against which to set and test build statuses
* `BB_USERNAME`: Bitbucket username for API authentication
* `BB_PASSWORD`: Bitbucket (app) password for API authentication
* `GITHUB_REPO`: the name of an existing Bitbucket repository
* `GITHUB_REPO_OWNER`: the owner of an existing Bitbucket repository
* `GITHUB_COMMIT_SHA`: an existing commit against which to set and test build statuses
* `GITHUB_USERNAME`: Github username for API authentication
* `GITHUB_PASSWORD`: Github token for API authentication
