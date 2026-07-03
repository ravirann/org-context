pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
  }

  environment {
    CE_DATABASE_URL = 'postgresql+asyncpg://ce:ce@localhost:5433/context_engine'
    CE_TEST_DATABASE_URL = 'postgresql+asyncpg://ce:ce@localhost:5433/context_engine_test'
  }

  stages {
    stage('Setup') {
      steps {
        sh 'make setup'
        sh 'docker compose up -d db redis'
      }
    }

    stage('Lint & Typecheck') {
      parallel {
        stage('Lint')      { steps { sh 'make lint' } }
        stage('Typecheck') { steps { sh 'make typecheck' } }
      }
    }

    stage('Backend tests (coverage gate 85%)') {
      // pytest is configured with --cov-fail-under=85: this stage FAILS below 85% coverage.
      steps { sh 'make test-api' }
      post {
        always {
          archiveArtifacts artifacts: 'backend/coverage.xml', allowEmptyArchive: true
        }
      }
    }

    stage('Frontend tests (coverage gate 85%)') {
      // vitest coverage thresholds are set to 85: this stage FAILS below 85% coverage.
      steps { sh 'make test-ui' }
      post {
        always {
          archiveArtifacts artifacts: 'frontend/coverage/coverage-summary.json', allowEmptyArchive: true
        }
      }
    }

    stage('Eval harness') {
      steps { sh 'make eval' }
    }

    stage('E2E') {
      steps { sh 'make test-e2e' }
      post {
        always {
          archiveArtifacts artifacts: 'frontend/playwright-report/**', allowEmptyArchive: true
        }
      }
    }
  }

  post {
    always { sh 'docker compose down -v || true' }
  }
}
