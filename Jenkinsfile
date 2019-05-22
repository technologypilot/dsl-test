    
pipeline {
    agent any
    stages{
        stage('Fetch Project'){
            steps {
                echo 'testing...'
            }
        }
    }
        options {
        branchTearDownExecutor jobName:'teardown-job'
            }
}