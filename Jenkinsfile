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
    def toxEnvName = '.env-tox'
    def pylintEnvName = '.env-pylint'
    def sqScannerHome = tool 'sonar-scanner'
    def pylint_report_path = 'pylint_report.txt'
    def coverage_xml_path = 'coverage.xml'
    def sonar_properties_path = 'sonar-project.properties'

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
    tasks_1['Prepare Tox, Run With Coverage & Publish Report'] = {
        docker.image('python:3.12').inside() {
            dir(myworkspace) {
                stage('Prepare Tox Venv') {
                    if (!fileExists(toxEnvName)) {
                        echo 'Build Python Virtualenv for testing...'
                        sh """
                        python -m venv ${toxEnvName}
                        . ./${toxEnvName}/bin/activate
                        pip install --upgrade pip
                        pip install tox
                        """
                    }
                }
                stage('Run Test Suite & Gather Coverage') {
                    sh """
                    . ./${toxEnvName}/bin/activate
                    tox -e with-coverage
                    """
                }
                stage('Clean up tox-env') {
                    if (fileExists(toxEnvName)) {
                        sh "rm -r ${toxEnvName}"
                    }
                }
                stage('Publish Coverage Report') {
                    recordCoverage(tools: [[parser: 'COBERTURA',
                                            pattern:  "${coverage_xml_path}"]],
                                   sourceCodeRetention: 'LAST_BUILD')
                }
            }
        }
    }
    tasks_1['Prepare Pylint, Run Analysis, Archive & Publish report'] = {
        docker.image('python:3.12').inside() {
            dir(myworkspace) {
                stage('Prepare Pylint Venv') {
                    if (!fileExists(pylintEnvName)) {
                        echo 'Build Python Virtualenv for linting...'
                        sh """
                        python -m venv ${pylintEnvName}
                        . ./${pylintEnvName}/bin/activate
                        pip install --upgrade pip
                        pip install -r ./requirements.txt
                        pip install .
                        pip install pylint
                        """
                    }
                }
                stage('Run PyLint') {
                    echo 'Run pylint'
                    sh """
                    . ./${pylintEnvName}/bin/activate
                    pylint -f parseable ${pylint_targets} | tee ${pylint_report_path}
                    """
                }
                stage('Archive PyLint Report') {
                    archiveArtifacts artifacts: pylint_report_path
                }
                stage('Publish PyLint Report') {
                    recordIssues tool: pyLint(pattern: pylint_report_path)
                }
            }
        }
    }

    tasks_2['Run Tests py310'] = {
        docker.image('python:3.10').inside() {
            dir(myworkspace) {
                stage('Prepare Tox Venv') {
                    if (!fileExists(toxEnvName)) {
                        echo 'Build Python Virtualenv for testing...'
                        sh """
                        python -m venv ${toxEnvName}
                        . ./${toxEnvName}/bin/activate
                        pip install --upgrade pip
                        pip install tox
                        """
                    }
                }
                stage('Run Tests') {
                    sh """
                    . ./${toxEnvName}/bin/activate
                    tox -e py310
                    """
                }
                stage('Clean up tox-env') {
                    if (fileExists(toxEnvName)) {
                        sh "rm -r ${toxEnvName}"
                    }
                }
            }
        }
    }
    tasks_3['Run Tests py311'] = {
        docker.image('python:3.11').inside() {
            dir(myworkspace) {
                stage('Prepare Tox Venv') {
                    if (!fileExists(toxEnvName)) {
                        echo 'Build Python Virtualenv for testing...'
                        sh """
                        python -m venv ${toxEnvName}
                        . ./${toxEnvName}/bin/activate
                        pip install --upgrade pip
                        pip install tox
                        """
                    }
                }
                stage('Run Tests') {
                    sh """
                    . ./${toxEnvName}/bin/activate
                    tox -e py311
                    """
                }
                stage('Clean up tox-env') {
                    if (fileExists(toxEnvName)) {
                        sh "rm -r ${toxEnvName}"
                    }
                }
            }
        }
    }
    tasks_4['Run Tests py312'] = {
        docker.image('python:3.12').inside() {
            dir(myworkspace) {
                stage('Prepare Tox Venv') {
                    if (!fileExists(toxEnvName)) {
                        echo 'Build Python Virtualenv for testing...'
                        sh """
                        python -m venv ${toxEnvName}
                        . ./${toxEnvName}/bin/activate
                        pip install --upgrade pip
                        pip install tox
                        """
                    }
                }
                stage('Run Tests') {
                    sh """
                    . ./${toxEnvName}/bin/activate
                    tox -e py312
                    """
                }
                stage('Clean up tox-env') {
                    if (fileExists(toxEnvName)) {
                        sh "rm -r ${toxEnvName}"
                    }
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
        docker.image('python:3.12').inside() {
            dir(myworkspace) {
                stage('Prepare Tox Venv') {
                    if (!fileExists(toxEnvName)) {
                        echo 'Build Python Virtualenv for testing...'
                        sh """
                        python -m venv ${toxEnvName}
                        . ./${toxEnvName}/bin/activate
                        pip install --upgrade pip
                        pip install tox
                        """
                    }
                }
                stage('Run pep8 check') {
                    sh """
                    . ./${toxEnvName}/bin/activate
                    tox -e black-check
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
                sh "gcloud artifacts docker tags add ${image_tag} ${DOCKER_ARTIFACT_REGISTRY}/cdc-agg-docstore:${env.BRANCH_NAME}-latest"
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
