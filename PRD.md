### DevOps & Infrastructure Agent Requirements

## Task list

**1. Local Development Environment (Docker & LocalStack)**
* [ ]**Dockerization:** Create a functional `Dockerfile` for the backend application, ensuring it is optimized and ready for deployment to AWS.
* [ ]**Local AWS Emulation:** Configure a `docker-compose.yml` file that integrates LocalStack to emulate the necessary AWS services (Message Queue and Database) for local development.
* **Zero-Config Startup:** Guarantee that the entire local infrastructure and application can be started seamlessly using only the `docker compose up` command. The system must start without requiring any extra manual configuration.
* [ ]**Environment Variables:** Create a `.env.example` file to manage all environment variables properly. 
* [ ]You must ensure that no sensitive credentials or secrets are ever hardcoded or committed into the repository.

**2. CI/CD Pipeline & AWS Deployment**
* [ ]**Automated Pipeline:** Build a functional CI/CD pipeline using GitHub Actions. [ ]The pipeline must automatically trigger and deploy the application to a real AWS production environment whenever code is pushed to the main branch.
* [ ]**Public URL:** Configure the AWS infrastructure so that the deployed application is live and accessible from the internet via a public URL.
* [ ]**Cost Optimization:** Select and configure AWS services that ideally operate within the AWS Free Tier, ensuring the total cost remains under $10 USD
* **Reviewer Access:** Include the necessary Infrastructure as Code (IaC) or instructions to create an IAM user with `AdministratorAccess` permissions. [ ]This is required to share the Access Key ID and Secret Access Key securely with the reviewers.


**1. REST API Development (FastAPI)**
* [ ]Implement a REST API using Python 3.11+ and FastAPI.
* [ ]Implement basic authentication using JWT (no external OAuth required).
* [ ]Use Pydantic v2 for all payload validations.
* [ ]Implement centralized error handling using global handlers (avoid scattered try/except blocks).
* Create the endpoint `POST /jobs` to create a new report job. [ ]It must publish a message to the queue and return `{ "job_id": "...", "status": "PENDING" }`.
* [ ]Create the endpoint `GET /jobs/{job_id}` to return the current status and the result url (if completed) of a specific job.
* Create the endpoint `GET /jobs` to list all jobs for the authenticated user. [ ]This endpoint must be paginated with a minimum of 20 items per page.

**2. Persistence (AWS Database)**
* [ ]Integrate an AWS database service to persist the state of each job.
* [ ]Implement the following minimum data model: `job_id`, `user_id`, `status`, `report_type`, `created_at`, `updated_at`, `result_url`.
* [ ]Ensure queries to list jobs by `user_id` are highly efficient.
* [ ]Provide a script or clear programmatic instructions to initialize the database schema from scratch.

**3. Message Queue & Asynchronous Workers (AWS)**
* [ ]Ensure the API publishes a message to an AWS messaging/queue service immediately upon creating a new job.
* [ ]Create worker scripts to consume these messages and process the jobs asynchronously. [ ]Note: The actual "report processing" can be simulated using a random sleep of 5-30 seconds and dummy data generation.
* [ ]The worker must update the job status in the database as it progresses: from `PROCESSING` to `COMPLETED` or `FAILED`.
* [ ]Implement concurrency mechanisms so the system can process at least 2 messages in parallel without one blocking the other.
* [ ]Implement a robust strategy (like a Dead Letter Queue) to handle messages that fail repeatedly, ensuring they do not block the main queue.

**4. Senior Bonus Challenges**
* [ ]**B1 - Priority Queues:** Implement high and standard priority channels based on report type, ensuring workers prioritize high-priority jobs.
* [ ]**B2 - Circuit Breaker:** Implement a Circuit Breaker pattern in the worker to pause processing a specific report type if it fails N consecutive times.
* [ ]**B4 - Exponential Back-off:** Add exponential back-off logic in the worker before retrying a failed message.
* [ ]**B5 - Observability:** Add structured logging, business metrics, and a `GET /health` endpoint reporting the status of dependencies.
* [ ]**B6 - Advanced Testing:** Achieve >= 70% backend code coverage using `pytest`, including unit tests for the worker, integration tests for the `POST /jobs` endpoint, and at least one test simulating a processing failure.

**5. Core Setup & Technologies**
* [cite_start]You must build the application using React 18+. 
* You are allowed to initialize the project using Vite+React, or CRA.
* Structure the application logically. It is recommended to organize the source code into `components/` for the UI, `hooks/` for custom hooks, and `services/` for API calls.
* [cite_start]Manage environment variables correctly, ensuring a `.env.example` file is used and no secrets are hardcoded.

**6. Report Request Form**
* [cite_start]Build a form that allows the user to request a report.
* [cite_start]The form must contain the following specific fields: `report_type`, `date_range`, and `format`.
* [cite_start]Upon submission, the frontend must handle the immediate response containing the job identifier and initial state, ensuring the user is not blocked while the report is being processed.

**7. Job List & Visual Feedback**
* [cite_start]Build a list view to display the jobs.
* [cite_start]You must implement colored badges to visually represent the current state of each job: `PENDING`, `PROCESSING`, `COMPLETED`, or `FAILED`.
* Implement proper error handling that provides clear visual feedback to the user. [cite_start]Using the browser's native `alert()` function is explicitly forbidden.

**8. Automatic State Updates (Core)**
* [cite_start]The job list must reflect state changes automatically.
* [cite_start]The user must never have to manually reload the page to see the updated status of their reports.

**9. Responsive Design**
* Ensure the entire application features a responsive design. [cite_start]It must look and function perfectly on both mobile devices and desktop screens.

**10. Senior Bonus Challenge**
* **B3 — Real-time notifications:** Replace traditional frontend polling with a push strategy, such as WebSockets or another similar mechanism. [cite_start]Configure the application so that the server proactively notifies the frontend whenever a job's status changes.

## Project Status
- Current Milestone: Scaffolding
- Last Update: Agentic Orchestrator initialized.