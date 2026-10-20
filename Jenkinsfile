// CI/CD pipeline for agrotrust-metrics.
// Jenkins checks the repository every 2 minutes, so every commit to main gets a build.
// The agent needs python3 (3.10+), docker and, for the deploy stage, minikube and kubectl.

pipeline {
    agent any

    triggers {
        pollSCM('H/2 * * * *')
    }

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    parameters {
        booleanParam(name: 'PUSH_IMAGE', defaultValue: false, description: 'Push the image to Docker Hub')
        booleanParam(name: 'DEPLOY', defaultValue: true, description: 'Run the analysis job in Kubernetes (Minikube)')
    }

    environment {
        // Homebrew tools and the Docker Desktop credential helper on a macOS agent; harmless on Linux
        PATH = "/opt/homebrew/opt/python@3.12/libexec/bin:/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:${env.PATH}"
        IMAGE = 'kozhanov7/agrotrust-metrics'
        TAG = "${env.BUILD_NUMBER}-${env.GIT_COMMIT?.take(7) ?: 'local'}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git log -1 --oneline'
            }
        }

        stage('Install') {
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --quiet --upgrade pip
                    pip install --quiet -e ".[dev]"
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '. .venv/bin/activate && ruff check . && ruff format --check .'
            }
        }

        stage('Unit tests') {
            steps {
                sh '''
                    . .venv/bin/activate
                    pytest --junitxml=reports/junit.xml \
                           --cov=agrotrust_metrics --cov-report=xml:reports/coverage.xml \
                           --cov-report=term
                '''
            }
            post {
                always {
                    junit 'reports/junit.xml'
                }
            }
        }

        stage('Build Docker image') {
            steps {
                sh 'docker build -t $IMAGE:$TAG -t $IMAGE:latest .'
            }
        }

        stage('Test the image') {
            steps {
                // run the tool inside the new image on a small simulated dataset
                sh '''
                    rm -rf results && mkdir -p results && chmod 777 results
                    docker run --rm $IMAGE:$TAG --version
                    docker run --rm -v "$WORKSPACE/results:/data" $IMAGE:$TAG \
                        simulate --nodes 6 --days 7 --seed 1 --out /data
                    docker run --rm -v "$WORKSPACE/results:/data" $IMAGE:$TAG \
                        summarize /data/readings.csv --events /data/events.csv --out /data/summary.csv \
                        | tee results/summary.txt
                '''
                archiveArtifacts artifacts: 'results/summary.*', fingerprint: true
            }
        }

        stage('Push to Docker Hub') {
            when {
                allOf {
                    expression { isMain() }
                    expression { params.PUSH_IMAGE }
                }
            }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub',
                                                  usernameVariable: 'DH_USER',
                                                  passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        docker push $IMAGE:$TAG
                        docker push $IMAGE:latest
                        docker logout
                    '''
                }
            }
        }

        stage('Deploy to Minikube') {
            when {
                allOf {
                    expression { isMain() }
                    expression { params.DEPLOY }
                }
            }
            steps {
                // Minikube runs its own container runtime inside Docker Desktop and does not
                // see host images, so the image is copied into the cluster without a registry
                sh '''
                    minikube image load $IMAGE:$TAG
                    kubectl apply -f k8s/namespace.yaml
                    kubectl -n agrotrust delete job agrotrust-analysis --ignore-not-found
                    sed "s|IMAGE_TAG|$IMAGE:$TAG|" k8s/job.yaml | kubectl apply -f -
                    kubectl -n agrotrust wait --for=condition=complete job/agrotrust-analysis --timeout=180s
                    kubectl -n agrotrust logs job/agrotrust-analysis | tail -n 25
                '''
            }
        }
    }

    post {
        always {
            sh 'docker image prune -f || true'
        }
        success {
            echo "Image $IMAGE:$TAG built and tested"
        }
        failure {
            echo 'Build failed, see the stage log above'
        }
    }
}

// works both in a plain Pipeline job (GIT_BRANCH = origin/main) and in a multibranch job
def isMain() {
    return env.BRANCH_NAME == 'main' || env.GIT_BRANCH in ['main', 'origin/main']
}
