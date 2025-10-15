#!/usr/bin/env groovy

node_name = 'default'
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
    def sqScannerHome = tool 'SonarQube Scanner'
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
        node(current_node) {
            dir(myworkspace) {
                stage('Prepare Tox Venv') {
                    if (!fileExists(toxEnvName)) {
                        echo 'Build Python Virtualenv for testing...'
                        sh """
                        python-latest -m venv ${toxEnvName}
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
                stage('Publish Coverage Report') {
                    recordCoverage(tools: [[parser: 'COBERTURA',
                                            pattern:  "${coverage_xml_path}"]],
                                   sourceCodeRetention: 'LAST_BUILD')
                }
            }
        }
    }
    tasks_1['Prepare Pylint, Run Analysis, Archive & Publish report'] = {
        node(current_node) {
            dir(myworkspace) {
                stage('Prepare Pylint Venv') {
                    if (!fileExists(pylintEnvName)) {
                        echo 'Build Python Virtualenv for linting...'
                        sh """
                        python-latest -m venv ${pylintEnvName}
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

    tasks_2['Run Tests py39'] = {
        node(current_node) {
            dir(myworkspace) {
                stage('Run Tests') {
                    sh """
                    . ./${toxEnvName}/bin/activate
                    tox -e py39
                    """
                }
            }
        }
    }
    tasks_2['Run Tests py310'] = {
        node(current_node) {
            dir(myworkspace) {
                stage('Run Tests') {
                    sh """
                    . ./${toxEnvName}/bin/activate
                    tox -e py310
                    """
                }
            }
        }
    }
    tasks_2['Run Tests py311'] = {
        node(current_node) {
            dir(myworkspace) {
                stage('Run Tests') {
                    sh """
                    . ./${toxEnvName}/bin/activate
                    tox -e py311
                    """
                }
            }
        }
    }
    tasks_2['Run Tests py312'] = {
        node(current_node) {
            dir(myworkspace) {
                stage('Run Tests') {
                    sh """
                    . ./${toxEnvName}/bin/activate
                    tox -e py312
                    """
                }
            }
        }
    }

    tasks_2['Initiate SonarQube Analysis'] = {
        node(current_node) {
            dir(myworkspace) {
                stage('Prepare sonar-project.properties') {
                    sh "echo sonar.projectVersion = \$(cat VERSION) >> ${sonar_properties_path}"
                }
                stage('Initiate SonarQube analysis') {
                    withSonarQubeEnv() {
                        sh "${sqScannerHome}bin/sonar-scanner"
                    }
                }
            }
        }
    }
    try {
        // run parallel tasks
        parallel tasks_1
        parallel tasks_2
    } catch (err) {
        currentBuild.result = 'FAILURE'
        sendmail('FAILURE')
    }
    try {
        node(current_node) {
            dir(myworkspace) {
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
