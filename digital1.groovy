job('Infra-Provisioning') {
    scm {
        git('https://github.com/technologypilot/dsl-test.git')
        }
    }
    triggers {
        scm('H/5 * * * *')
    }
    wrappers {
        nodejs('nodejs') // this is the name of the NodeJS installation in 
                         // Manage Jenkins -> Configure Tools -> NodeJS Installations -> Name
    }
    steps {
    
    }
}