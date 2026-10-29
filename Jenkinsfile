#!/usr/bin/env groovy

node_name = 'jnlp-himem'
email_recipient = ''
pylint_targets = 'cessda_skgif_api'

def sendmail(build_result) {
    stage('Send mail') {
        mail(to: email_recipient,
             subject: "Job '${env.JOB_NAME}' (${env.BUILD_NUMBER}) result is ${build_result}",
             body: "See info at ${env.BUILD_URL}")
    }
}

// Discard old builds
properties([buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '30'))])

// node reserves executor and workspace
node(node_name) {
    // Prepare
    // -------
    def sqScannerHome = tool 'sonar-scanner'
    def pylint_report_path = 'pylint_report.txt'
    def coverage_xml_path = 'coverage.xml'
    def sonar_properties_path = 'sonar-project.properties'
    def image_tag = "${DOCKER_ARTIFACT_REGISTRY}/skg-if-api:${env.BRANCH_NAME.toLowerCase().replaceAll('[^a-z0-9\\.\\_\\-]', '-')}-${env.BUILD_NUMBER}"

    // prepare workspace
    def myworkspace = ''
    // Get current node, to force concurrent steps to be run on the same node.
    def current_node = "${env.NODE_NAME}"

    // Parallelism causes stages to be run in different workspaces.
    // Before submitting to SonarQube we need to make sure pylint_report
    // coverage.xml and sonar-project.properties files are in-place.
    // tasks shall be run in parallel
    def tasks_1 = [:]
    def tasks_2 = [:]
    def tasks_3 = [:]
    def tasks_4 = [:]
    def tasks_5 = [:]

    myworkspace = "${WORKSPACE}"
    echo "My workspace is ${myworkspace}"
    deleteDir()

    // Get recipient from git commit author
    def scmVars = checkout scm
    email_recipient = sh (
        script: "git show -s --pretty=%ae",
        returnStdout: true
    )
    echo "Build result will be sent to ${email_recipient}"

    // Assign parallel tasks
    tasks_1['Run With Coverage & Publish Report'] = {
        docker.image('python:3.14').inside() {
            dir(myworkspace) {
                stage('Run Test Suite & Gather Coverage') {
                    sh """
                    python -m venv .venv-coverage
                    . ./.venv-coverage/bin/activate
                    pip install --upgrade pip tox
                    tox -e with-coverage
                    """
                }

                stage('Publish Coverage Report') {
                    recordCoverage(
                        tools: [[
                            parser: 'COBERTURA',
                            pattern: "${coverage_xml_path}"
                        ]],
                        sourceCodeRetention: 'LAST_BUILD'
                    )
                }
            }
        }
    }
    tasks_1['Run Pylint, Archive & Publish Report'] = {
        docker.image('python:3.14').inside() {
            dir(myworkspace) {
                stage('Run Pylint') {
                    sh """
                    python -m venv .venv-pylint
                    . ./.venv-pylint/bin/activate
                    pip install --upgrade pip
                    pip install -r ./requirements.txt
                    pip install .
                    pip install pylint
                    pylint -f parseable ${pylint_targets} | tee ${pylint_report_path}
                    """
                }

                stage('Archive Pylint Report') {
                    archiveArtifacts artifacts: pylint_report_path
                }

                stage('Publish Pylint Report') {
                    recordIssues tool: pyLint(pattern: pylint_report_path)
                }
            }
        }
    }

    tasks_2['Run Tests py311'] = {
        docker.image('python:3.11').inside() {
            dir(myworkspace) {
                stage('Run Tests py311') {
                    sh """
                    python -m venv .venv-py311
                    . ./.venv-py311/bin/activate
                    pip install --upgrade pip tox
                    tox -e py311
                    """
                }
            }
        }
    }
    tasks_3['Run Tests py313'] = {
        docker.image('python:3.13').inside() {
            dir(myworkspace) {
                stage('Run Tests py313') {
                    sh """
                    python -m venv .venv-py313
                    . ./.venv-py313/bin/activate
                    pip install --upgrade pip tox
                    tox -e py313
                    """
                }
            }
        }
    }
    tasks_4['Run Tests py315'] = {
        docker.image('python:3.15').inside() {
            dir(myworkspace) {
                stage('Run Tests py315') {
                    sh """
                    python -m venv .venv-py315
                    . ./.venv-py315/bin/activate
                    pip install --upgrade pip tox
                    tox -e py315
                    """
                }
            }
        }
    }

    tasks_5['Initiate SonarQube Analysis'] = {
        stage('Prepare sonar-project.properties') {
            sh "echo sonar.projectVersion = \$(cat VERSION) >> ${sonar_properties_path}"
        }
        stage('Initiate SonarQube analysis') {
            withSonarQubeEnv() {
                sh "${sqScannerHome}/bin/sonar-scanner"
            }
        }
    }
    try {
        // run parallel tasks
        parallel tasks_1
        parallel tasks_2
        parallel tasks_3
        parallel tasks_4
        parallel tasks_5
    } catch (err) {
        currentBuild.result = 'FAILURE'
        sendmail('FAILURE')
    }
    try {
        docker.image('python:3.14').inside() {
            dir(myworkspace) {
                stage('Run Ruff checks') {
                    sh """
                    python -m venv .venv-ruff
                    . ./.venv-ruff/bin/activate
                    pip install --upgrade pip tox
                    tox -e ruff-check
                    """
                }
            }
        }
    } catch (err) {
        currentBuild.result = 'UNSTABLE'
        sendmail('UNSTABLE')
    }
    try {
        stage('Build docker image') {
            withEnv(['DOCKER_BUILDKIT=1']) {
                sh "docker build -t ${image_tag} ."
            }
        }
        if (env.BRANCH_NAME == 'main') {
            stage('Push Docker image') {
                sh "gcloud auth configure-docker ${ARTIFACT_REGISTRY_HOST}"
                sh "docker push ${image_tag}"
                sh "gcloud artifacts docker tags add ${image_tag} ${DOCKER_ARTIFACT_REGISTRY}/skg-if-api:${env.BRANCH_NAME}-latest"
            }
        }
    } catch (err) {
        currentBuild.result = 'FAILURE'
        sendmail('FAILURE')
    }
}
// Wait for sonar quality gate
stage("Quality Gate") {
    timeout(time: 10, unit: 'MINUTES') { // Just in case something goes wrong, pipeline will be killed after a timeout
        def qg = waitForQualityGate() // Reuse taskId previously collected by withSonarQubeEnv
        if (qg.status != 'OK') {
            echo "Pipeline unstable due to quality gate failure: ${qg.status}"
            currentBuild.result = 'UNSTABLE'
            sendmail('UNSTABLE')
        }
    }
}
if (env.BRANCH_NAME == 'main') {
    stage('Deploy SKG-IF API') {
        build job: 'cessda.cdc.aggregator.deploy/main', parameters: [string(name: 'skgIfApiImageTag', value: "${env.BRANCH_NAME.toLowerCase().replaceAll('[^a-z0-9\\.\\_\\-]', '-')}-${env.BUILD_NUMBER}")], wait: false
    }
}
