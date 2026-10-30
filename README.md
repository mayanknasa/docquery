# DocQuery: GenAI Document Q&A API

An async FastAPI service. Upload a PDF or text file, then ask questions about it. The service splits the document into chunks, turns them into embeddings, finds the chunks closest to your question, and asks an LLM to answer using only those chunks (Retrieval Augmented Generation, or RAG).

## Architecture

    Client
      |
      v
    Application Load Balancer (public, port 80)
      |
      v
    ECS Fargate service (FastAPI in Docker, private security group)
      |-- S3 bucket           raw uploaded files
      |-- DynamoDB table      document metadata + chunk text + embeddings
      |-- Secrets Manager     OPENAI_API_KEY, API_KEY
      |-- CloudWatch Logs     JSON request logs, plus a 5xx alarm

Request flow for an upload: extract text (worker thread) -> chunk -> embed batches in parallel (asyncio.gather
with a semaphore) -> save file to S3 and chunks to DynamoDB.
Request flow for a question: embed the question -> load the document's chunks -> cosine similarity -> top K
chunks -> LLM answer with sources.

## Project layout

    app/main.py                 app factory, startup, request logging middleware, /health
    app/config.py               settings from environment variables
    app/security.py             API key check (constant time compare)
    app/routers/documents.py    HTTP endpoints only, no business logic
    app/services/pipeline.py    ingest and question answering flow, parallel embedding
    app/services/chunking.py    overlapping text splitter
    app/services/extract.py     PDF and text extraction
    app/services/llm.py         LLM client interface, OpenAI client, offline mock client
    app/services/store.py       storage interface, in memory store, S3 + DynamoDB store
    app/services/retrieval.py   cosine similarity search
    tests/test_app.py           pytest tests (run offline with the mock client)
    infra/                      Terraform for all AWS resources
    Dockerfile                  container image, runs as a non root user

## Run locally (no AWS account or API key needed)

### macOS/Linux

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements-dev.txt
    pytest
    uvicorn app.main:app --reload

### Windows PowerShell

    .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
    .\.venv\Scripts\python.exe -m pytest
    .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

To activate the virtual environment first, use:

    .\.venv\Scripts\Activate.ps1

Then the commands can be run without the `.venv\Scripts\python.exe` prefix:

    pip install -r requirements-dev.txt
    pytest
    uvicorn app.main:app --reload

### Windows Command Prompt

    .venv\Scripts\activate.bat
    python -m pip install -r requirements-dev.txt
    python -m pytest
    python -m uvicorn app.main:app --reload

Open http://localhost:8000/docs for the interactive API page.

    curl -F "file=@notes.pdf" http://localhost:8000/documents
    curl -X POST http://localhost:8000/documents/<doc_id>/ask \
      -H "Content-Type: application/json" \
      -d '{"question": "What is this document about?"}'

The default mock provider gives fake answers (it returns the best matching passage). For real answers set
LLM_PROVIDER=openai and OPENAI_API_KEY in a .env file (see .env.example).

## Deploy to AWS

Prerequisites: AWS CLI configured, Docker, Terraform 1.5 or newer.
Set a billing alert in your AWS account first. An ALB and Fargate task cost money while they run.

    cd infra

    # 1. Create the registry and the secret first
    terraform init
    terraform apply -target=aws_ecr_repository.app -var="openai_api_key=sk-..."

    # 2. Build and push the image
    REPO=$(terraform output -raw ecr_repository_url)
    aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${REPO%%/*}
    docker build --platform linux/amd64 -t $REPO:latest ..
    docker push $REPO:latest

    # 3. Create everything else
    terraform apply -var="openai_api_key=sk-..." -var="api_key=choose-a-long-random-string"

    # 4. Try it
    curl http://$(terraform output -raw alb_dns_name)/health

Use -var="llm_provider=mock" if you want a free demo without an OpenAI key.
Terraform state holds the secret values, so do not commit terraform.tfstate.

Watch logs: CloudWatch, log group /ecs/docquery.

Tear everything down when you are done:

    terraform destroy -var="openai_api_key=sk-..."

## Design decisions

* Storage and LLM sit behind small interfaces, so local tests need no cloud and providers can be swapped.
* Blocking work (PDF parsing, boto3 calls) runs through asyncio.to_thread so the event loop stays free.
* IAM is split: an execution role (pull image, write logs, read secret) and a task role (only this bucket
  and table).
* Secrets come from Secrets Manager, not from the image or the repo.

## Known limits and next steps

* Vectors are compared in application memory, which is fine for documents of a few hundred chunks. A vector
  database (OpenSearch, pgvector) is the next step for large collections.
* Uploads are processed inside the request. For big files, move ingestion to a queue (SQS) and a worker.
* HTTP only on the ALB. Add an ACM certificate and an HTTPS listener for real use.
* Add authentication per user, rate limiting, and a CI pipeline.
* Amazon Bedrock could replace the OpenAI client by adding one class that implements the same interface.
