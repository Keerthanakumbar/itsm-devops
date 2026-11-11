# ITSM DevOps Project – Flask CRUD App

This is my project for the IT Security Management & DevOps course.
I rewrote the CRUD app from the lectures (originally Node.js) in Python using Flask.
The app stores names in a MariaDB database. I packaged it with Docker, ran it with
Docker Compose, deployed it on Kubernetes using Minikube, made it reachable through
an Ingress, and tested it under load with k6.

---

## What is in this repository

```
itsm-devops/
├── app/
│   ├── app.py               # the Flask app (CRUD API + health checks)
│   ├── requirements.txt     # Python packages
│   ├── Dockerfile           # builds the app image
│   └── .dockerignore        # files that should not go into the image
├── k8s/
│   ├── namespace.yaml       # creates the "crud" namespace
│   ├── mariadb.yaml         # MariaDB database (storage, deployment, service)
│   ├── deployment.yaml      # the app deployment (resources, probes)
│   ├── service.yaml         # the app service (ClusterIP)
│   └── ingress.yaml         # Ingress (host crud.local → crud-app)
├── load-test/
│   ├── load-test.js         # k6 load test script
│   ├── k6-pod.yaml          # runs k6 inside the cluster
│   └── report.html          # k6 HTML dashboard with charts
├── docs/screenshots/        # screenshots used in my report
├── docker-compose.yaml      # runs the app and MariaDB together
└── README.md
```

---

## API endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Checks if the app and the database are working (200 = ok, 503 = database not reachable) |
| GET | `/health/live` | Simple check that the app is running |
| GET | `/api/names` | Lists all names |
| POST | `/api/names` | Adds a name, e.g. `{"name": "Alice"}` |
| PUT | `/api/names/<id>` | Changes a name, e.g. `{"name": "Bob"}` |
| DELETE | `/api/names/<id>` | Deletes a name |

---

## Tools and versions

- Python 3.12 and Flask 3.1
- gunicorn 23 as the web server (2 workers)
- MariaDB 11 (official `mariadb` Docker image)
- Docker and Docker Compose
- Kubernetes with Minikube, and ingress-nginx for the Ingress
- k6 for load testing

---

## Environment variables

The app reads its database settings from these environment variables.
If they are not set, the default values are used.

| Variable | Default | Meaning |
|---|---|---|
| `DB_HOST` | `localhost` | Address of the database (`db` in Compose, `mariadb` in Kubernetes) |
| `DB_PORT` | `3306` | Database port |
| `DB_NAME` | `namelist` | Database name (I use `crud` in Compose and Kubernetes) |
| `DB_USER` | `appuser` | Database user |
| `DB_PASSWORD` | `apppass` | Database password |

---

## How to run it

### With Docker Compose

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:5000/health
```

Both containers should show `(healthy)`.
To stop everything, run `docker compose down`. The data stays saved in the `db-data` volume.

### On Kubernetes (Minikube)

```bash
minikube start --driver=docker
minikube addons enable metrics-server

docker build -t crud-app:latest ./app
minikube image load crud-app:latest

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
kubectl get pods,svc -n crud
```

Both pods should show `1/1 Running`.
The service is ClusterIP, so to test it directly from my laptop I use port-forward:

```bash
kubectl port-forward svc/crud-app 5000:5000 -n crud
curl http://localhost:5000/health
```

### Through the Ingress

The Ingress makes the app reachable by name (`crud.local`) instead of an IP address.

```bash
minikube addons enable ingress
kubectl apply -f k8s/ingress.yaml
kubectl get ingress -n crud
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80
```

Then add `127.0.0.1 crud.local` to the Windows hosts file
(`C:\Windows\System32\drivers\etc\hosts`) and open `http://crud.local:8080/health`.

### Load test

```bash
kubectl create configmap k6-script --from-file=load-test/load-test.js -n crud
kubectl apply -f load-test/k6-pod.yaml
kubectl logs -f k6 -n crud
kubectl top pods -n crud
kubectl cp crud/k6:/tmp/report.html load-test/report.html
```

The test goes up to 500 users and keeps them for 3 minutes.
Each user creates, lists, updates and deletes a name.
The results are saved as an HTML dashboard in `load-test/report.html`.

### Crash test

```bash
kubectl get pods -n crud
kubectl exec deployment/crud-app -n crud -- sh -c "kill 1"
kubectl get pods -n crud
```

After the crash, the restart count goes up and the pod comes back to `1/1 Running`.

---

## Why I made these choices

- **Multi-stage Dockerfile:** the packages are installed in the full Python image, and only the result is copied into the slim image. The final image is smaller (about 226 MB) and has fewer things that could be attacked.
- **Non-root user:** the app runs as a normal user called `app`, not as root.
- **gunicorn:** a production web server, instead of the Flask development server.
- **Health checks on `/health`:** the readiness and liveness probes call `/health`, which also checks the database connection.
- **ClusterIP service:** the app is only reachable inside the cluster, which is safer.
- **Ingress:** gives the app a single entry point with a name (`crud.local`), so the service itself does not have to be exposed.
- **Saved data:** MariaDB keeps its data in a volume (Compose) and a PersistentVolumeClaim (Kubernetes), so the data is not lost when a container restarts.

---

## Results

- **Load test (500 users, 3 minutes):** about 88 requests per second, a p95 latency of 17.5 seconds, and 49.5% failed requests. The app used almost all of its CPU limit (475m of 500m), while memory stayed low (about 107Mi of 256Mi), so the app was CPU-bound. With only 2 gunicorn workers, requests queued up, the health probes timed out, and the liveness probe restarted the container twice during the test. A shorter 60-second run had only 0.75% failed requests, which shows that the problems build up under sustained load.
- **Crash test:** after stopping the main process, Kubernetes restarted the container automatically (the restart count went up by 1).

---

## Assumptions

- The app runs on port 5000.
- The database table is created automatically when the app starts, so no migration tool is used.
- The database port (3306) is only reachable inside Docker or Kubernetes, not from outside.
- Passwords are written in plain text because this is only for local testing. In a real setup I would use a `.env` file or Kubernetes Secrets.

---

## Author

Keerthana Kumbar – 100008764 IT Security Management & DevOps