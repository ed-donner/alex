# Alex vs Alex-sam

[Ed Donner’s Alex course](https://github.com/ed-donner/alex) (the original `alex`) and this repo [Alex SAM](https://github.com/Mo-Eltoum/alex-sam) are the same product: a multi-agent financial planner on AWS. The agents, Aurora schema, SageMaker embeddings, S3 Vectors index, Clerk frontend, and Bedrock Nova Pro model are the same ideas.

What changed is **how the infrastructure is built and wired**. The course teaches each AWS service in its own Terraform directory. This repo groups long-lived platform resources in one Terraform root and puts every Lambda in one AWS SAM application. SSM Parameter Store is the handshake between those two tools.

Destroy the course stack before the first deploy here. Both projects use the `alex-*` names, so they cannot run side by side in one account.

## Side by side


|                    | Course (Ed Donner)                                                                        | This repo                                                                                 |
| ------------------ | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Terraform          | Seven directories (`2_sagemaker` … `8_enterprise`), each with its own state file          | One root: `infra/terraform/`, one `terraform.tfstate`                                     |
| Lambdas            | Zip built by `package_docker.py`, then Terraform taint + `deploy_all_lambdas.py`          | `sam build --use-container` and `sam deploy`                                              |
| Researcher         | App Runner, or a public Lambda Function URL                                               | Image Lambda on the same HTTP API as the other functions (`POST /research`)               |
| Wiring             | Copy `terraform output` ARNs into the next directory’s `terraform.tfvars` and into `.env` | Terraform writes `/alex/*` parameters. SAM reads those names at deploy time               |
| IAM                | One shared role, `alex-lambda-agents-role`                                                | One IAM policy per function, declared next to that function in the SAM template           |
| Local Lambda check | `uv run test_simple.py` on your machine                                                   | Same `uv` tests, plus `sam local invoke` inside the real Lambda container                 |
| Frontend API       | CloudFront behavior added by pasting the API URL into Terraform                           | Same CloudFront pattern. The URL is `http_api_url` in `terraform.tfvars` after SAM deploy |


The application code (planner, tagger, reporter, charter, retirement, ingest, FastAPI, Next.js) was ported, not rewritten. `uv` is still how you run Python. There is no `pip install` and no `package_docker.py`.

## What Terraform owns

`infra/terraform/` creates things that are **not** a good fit for a Lambda template:

- SageMaker serverless embedding endpoint
- Aurora Serverless v2 (Data API on)
- The S3 Vectors bucket name and the ingest API key (the vector bucket itself is created by `scripts/bootstrap_vectors.py`, because it is an S3 Vectors bucket, not a normal `aws_s3_bucket`)
- CloudFront + the frontend S3 website, including `/api/*` forwarded to the HTTP API
- CloudWatch dashboards
- SSM parameters under `/alex/`

One state file means `terraform apply` and `terraform destroy` see the whole platform. In the course, forgetting one of the seven directories left orphaned resources and a bill.

## What SAM owns

`infra/sam/template.yaml` is one serverless application:

- HTTP API (API Gateway v2) for ingest, the FastAPI app, and the researcher
- SQS queue and dead-letter queue for the planner
- Zip Lambdas: ingest, tagger, reporter, charter, retirement, planner, API, optional scheduler
- One **image** Lambda for the researcher (Playwright does not fit in a zip layer)
- Two Lambda layers: Python dependencies, and the `alex-database` package mounted at `/opt/python/src`

Zip and image functions share this template. `Runtime` is set on each zip function. It is not in `Globals`, because an image function is invalid if it inherits `Runtime`, `Handler`, or `Layers`.

### Why SAM instead of `package_docker.py`

The course flow was: build a Linux zip in Docker, upload it, taint the Lambda in Terraform, apply again. Every code change repeated that. SAM does the build, the upload, and the CloudFormation update in `sam build` / `sam deploy`.

`sam local invoke` runs the zip in Amazon’s Python 3.12 image with the layers mounted. `uv run test_simple.py` only proves the agent works on your Mac. The local invoke proves the import path and the event shape match Lambda. That is what the README calls Lambda-runtime parity.

## What SSM is for

SSM Parameter Store is a small key/value service in the same account. Terraform writes values after it creates resources. The SAM template does not contain account-specific ARNs. Its parameters look like this:

```yaml
AuroraClusterArn:
  Type: AWS::SSM::Parameter::Value<String>
  Default: /alex/aurora_cluster_arn
```

At deploy time CloudFormation reads `/alex/aurora_cluster_arn` and injects the real ARN into the Lambda environment. You press Enter on `sam deploy --guided`. You do not paste ARNs into the prompts.

That only works for SSM type **String**. `SecureString` cannot be resolved by `AWS::SSM::Parameter::Value<String>`. `/alex/ingest_api_key` is therefore a plain String for now. The password still is not in git; it lives in Parameter Store.

Useful keys:


| Name                                                                 | Written by                | Used for                          |
| -------------------------------------------------------------------- | ------------------------- | --------------------------------- |
| `/alex/aurora_cluster_arn`, `/alex/aurora_secret_arn`                | Terraform                 | Data API                          |
| `/alex/vector_bucket`, `/alex/sagemaker_endpoint`                    | Terraform                 | Ingest                            |
| `/alex/bedrock_region`, `/alex/bedrock_model_id`, `/alex/aws_region` | Terraform                 | LiteLLM / Nova Pro                |
| `/alex/ingest_api_key`                                               | Terraform                 | `x-api-key` on ingest             |
| `/alex/http_api_url`                                                 | SAM, after the API exists | Researcher, scheduler, CloudFront |
| `/alex/sqs_queue_url`                                                | SAM                       | API enqueue                       |


`.env` is only for commands you run on your laptop (`uv run test_simple.py`). Deployed Lambdas do not read that file.

## Benefits

- **One deploy path for code.** Change an agent, then `sam build` and `sam deploy`. No Docker zip script and no Terraform taint.
- **No copied ARNs.** Renaming or recreating Aurora updates the SSM value. The next SAM deploy picks it up. In the course, a stale ARN in `tfvars` failed later with “cluster not found”.
- **Least privilege per function.** The tagger can call Bedrock and the Data API. It cannot send to SQS. The ingest function can call SageMaker and S3 Vectors. It cannot read the database secret. The course shared one role that could do all of that.
- **One API hostname.** Ingest, the portfolio API, and research are routes on one HTTP API. CloudFront sends `/api/`* to that API and everything else to S3. The course researcher was a separate App Runner URL you had to thread through env vars.
- **Local debugging that matches Lambda.** `sam local invoke` uses the same runtime, layers, and event JSON AWS will use.
- **Cheaper teardown.** `terraform destroy` in one directory plus `sam delete` removes the platform and the functions. The course needed seven destroys in reverse order.



## Tradeoffs students will feel

These are consequences of the split, not bugs in the agents.

- **SAM does not replace Terraform.** SageMaker, Aurora, and CloudFront stay in Terraform. SAM cannot create an Aurora cluster in this template.
- **Deploy order matters.** SAM fails if `/alex/aurora_cluster_arn` (and the region, Bedrock, and Clerk parameters) do not exist yet. Apply those SSM parameters before the first `sam deploy`.
- **Do not put the HTTP API URL in a Lambda environment with** `!Sub`**.** Researcher and the scheduler are also routes on that API. A template reference to the API URL makes a CloudFormation cycle. They read `/alex/http_api_url` at runtime instead.
- **HTTP API calls time out at 30 seconds.** Health checks are fine. A Playwright research run is longer, so API Gateway returns `503 Service Unavailable` while the Lambda is still working. The course avoided this by using App Runner, which has no 30-second cap.
- `eu.amazon.nova-pro-v1:0` **only works in an EU Bedrock region.** `BEDROCK_REGION=us-west-2` with an `eu.` model id returns “model identifier is invalid”.
- **CloudFront needs** `http_api_url`**.** If that variable is empty, `/api/`* is served from S3 as `index.html`. The browser then throws `Unexpected token '<'` because it tried to parse HTML as JSON.



## What we deliberately did not add

Remote Terraform state, GitHub Actions, WAF, and extra Terraform modules were left out. One local state file and one SAM stack are enough to see the difference from the course. Add those when you need a shared team environment, not to make the first deploy succeed.