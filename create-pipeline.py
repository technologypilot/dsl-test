import requests
from requests.auth import HTTPBasicAuth
import argparse
import subprocess
import logging
import os
import yaml
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Repository(object):
    def __init__(self, scm_username, scm_password):
        self._api_endpoint = 'http://api.github.com'
        self._scm_username = scm_username
        self._scm_password = scm_password
        self._scm_org = 'technologypilotcorp'

        # need to have a proper Jenkins cred ID
        self._scm_cred_id = 'Repo_Full_Hook_Full_Rogers_hook'

        self._output_groovy = 'out.groovy'

        self._onboard_list = None

        self._detected_repositories = []
        self._existing_repositories = []
        self._detected_subfolders = {}

    def __load_repo_list(self):
        with open('repos.yml', 'r') as f:
            return yaml.safe_load(f)

    def __get_repositories(self):
        repositories = []

        response = requests.get(self._api_endpoint + f'/orgs/{self._scm_org}/repos', auth=HTTPBasicAuth(self._scm_username, self._scm_password), verify=False)
        if response.status_code == 200:
            res_json = response.json()

            for repo in res_json:
                self._existing_repositories.append(repo['name'])
        else:
            logger.error(f'Error getting repositories from {self._scm_org}')
            exit(1)

        for repo in self._onboard_list['repos']:
            if repo['name'] in self._existing_repositories:
                repositories.append(repo['name'])

                if 'folders' in repo:
                    self._detected_subfolders[repo['name']] = repo['folders']

        return repositories

    def __get_clone_url(self, repository):
        return requests.get(self._api_endpoint + f'/repos/{self._scm_org}/{repository}', auth=HTTPBasicAuth(self._scm_username, self._scm_password), verify=False).json()['clone_url']

    def __create_PR_check_job(self, repository, folder = None):
        clone_url = self.__get_clone_url(repository)
        job_name = f"pr-check-{repository}" if folder is None else f"pr-check-{repository}-{folder}"
        dsl_string = f"""
job('{repository}/{job_name}') {{
    description('PR check pipeline for {repository}')
    logRotator {{
        daysToKeep(3)
        numToKeep(10)
    }}
    scm {{
        git {{
            remote {{
                url('{clone_url}')
                refspec('+refs/pull/${{ghprbPullId}}/*:refs/remotes/origin/pr/${{ghprbPullId}}/*')
                credentials('{self._scm_cred_id}')
            }}
            branch('${{ghprbActualCommit}}')
        }}
    }}
    triggers {{
        ghprbTrigger {{
            adminlist('')
            whitelist('')
            orgslist('')
            triggerPhrase('')
            onlyTriggerPhrase(false)
            autoCloseFailedPullRequests(false)
            displayBuildErrorsOnDownstreamBuilds(false)
            commentFilePath('')
            blackListCommitAuthor('')
            allowMembersOfWhitelistedOrgsAsAdmin(false)
            msgSuccess('Success')
            msgFailure('Failure')
            buildDescTemplate('')
            blackListLabels('')
            whiteListLabels('')
            includedRegions('')
            excludedRegions('')
            commitStatusContext('PR check')
            skipBuildPhrase('')
            cron('H/5 * * * *')
            useGitHubHooks(false)
            permitAll(true)
            gitHubAuthId('{self._scm_cred_id}')
            extensions {{
                ghprbSimpleStatus {{
                    commitStatusContext('PR check')
                    triggeredStatus('Check triggered')
                    startedStatus('Check started')
                    completedStatus {{
                        ghprbBuildResultMessage {{
                            message('PR check passed')
                            result('SUCCESS')
                        }}
                        ghprbBuildResultMessage {{
                            message('PR check failed')
                            result('ERROR')
                        }}
                        ghprbBuildResultMessage {{
                            message('PR check failed')
                            result('FAILURE')
                        }}
                    }}
                    addTestResults(false)
                    statusUrl('')
                    showMatrixStatus(false)
                }}
            }}
        }}
    }}
    steps {{
        shell('echo checking')
    }}
}}
"""
        return dsl_string

    def __create_ci_dsl_string(self, repository, folder = None):
        Jenkinsfile_path = "Jenkinsfile" if folder is None else f"{folder}/Jenkinsfile"
        job_name_postfix = f"{repository}" if folder is None else f"{repository}-{folder}"

        dsl_string = f"""
multibranchPipelineJob('{repository}/ci-{job_name_postfix}') {{
    description('ci pipeline for {job_name_postfix}')
    branchSources {{
        github {{
            buildForkPRMerge(false)
            buildOriginBranch(true)
            buildOriginBranchWithPR(false)
            buildOriginPRMerge(false)
            buildOriginPRHead(false)
            scanCredentialsId('{self._scm_cred_id}')
            checkoutCredentialsId('{self._scm_cred_id}')
            repoOwner('{self._scm_org}')
            repository('{repository}')
        }}
    }}
    orphanedItemStrategy {{
        discardOldItems {{
            daysToKeep(1)
        }}
    }}
    configure {{
        it / 'triggers' << 'com.cloudbees.hudson.plugins.folder.computed.PeriodicFolderTrigger'{{
            spec 'H/5 * * * *'
            interval "900000"
        }}
        it / factory(class: 'org.jenkinsci.plugins.workflow.multibranch.WorkflowBranchProjectFactory') {{
            owner(class: 'org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject', reference: '../..')
            scriptPath('{Jenkinsfile_path}')
        }}
    }}
}}
"""
        return dsl_string

    def __create_job_folder(self, repository):
        dsl_string = f"""
folder('{repository}') {{
    description('folder containing jobs for {repository}')
}}
"""
        return dsl_string

    def __create_groovy_file(self):
        with open(self._output_groovy, 'w+') as file:
            # create repo folders and pipeline
            for repository in self._detected_repositories:
                file.write(self.__create_job_folder(repository))

                # check if the repos is setup to do multi project sub folders
                if repository in self._detected_subfolders:
                    for folder in self._detected_subfolders[repository]:
                        file.write(self.__create_ci_dsl_string(repository, folder))
                        file.write(self.__create_PR_check_job(repository, folder))
                else:
                    file.write(self.__create_ci_dsl_string(repository))
                    file.write(self.__create_PR_check_job(repository))

    def scan_and_create_pipelines(self):
        self._onboard_list = self.__load_repo_list()

        self._detected_repositories = self.__get_repositories()

        # self.__create_groovy_file()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--scm-username', required=True, help='scm username')
    parser.add_argument('--scm-password', required=True, help='scm user passowrd')

    args = parser.parse_args()

    logger = logging.getLogger()
    logging.basicConfig(level=logging.INFO)
    fh = logging.FileHandler('output.log')
    logger.addHandler(fh)

    # repository = Repository(args.scm_username, args.scm_password)
    # repository.scan_and_create_pipelines()

    response = requests.get('https://api.github.com/user/repos', auth=HTTPBasicAuth('techpilot-token', '4ddb06f20667ffdab7a5612c8f4355c17cbea889'))
    if response.status_code == 200:
        res_json = response.json()
        #print(res_json)

        for repo in res_json:
            print(repo['name'])